"""Shortener service tests — Module 5.

Everything the service does at this point: create a short URL, list the active
ones, and redirect. There is no authentication yet, so every endpoint here is
deliberately exercised anonymously.
"""

from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from ..models import URL


class URLModelTests(TestCase):
    def test_short_code_is_generated(self):
        url = URL.objects.create(original_url='https://example.com')
        self.assertEqual(len(url.short_code), 6)

    def test_active_code_prefers_custom_alias(self):
        url = URL.objects.create(original_url='https://example.com', custom_alias='promo')
        self.assertEqual(url.active_code, 'promo')

    def test_active_code_falls_back_to_short_code(self):
        url = URL.objects.create(original_url='https://example.com')
        self.assertEqual(url.active_code, url.short_code)


class URLCreateAPITests(TestCase):
    url = '/api/v1/urls/create/'

    def _create(self, **payload):
        payload.setdefault('original_url', 'https://example.com')
        return self.client.post(self.url, payload, content_type='application/json')

    def test_creates_and_returns_the_generated_code(self):
        response = self._create()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body['original_url'], 'https://example.com')
        self.assertEqual(len(body['short_code']), 6)
        self.assertEqual(body['click_count'], 0)

    def test_short_url_is_absolute(self):
        body = self._create().json()
        self.assertTrue(body['short_url'].endswith(f"/{body['short_code']}/"))

    @override_settings(ALLOWED_HOSTS=['short.example.com'])
    def test_short_url_keeps_the_port_from_the_host_header(self):
        """The returned link has to be one the caller can actually follow.

        `short_url` is built from the Host header, so a non-default port has to
        survive into it. This pins the Django half only: it cannot catch a proxy
        that strips the port before Django ever sees it, which is what nginx's
        `$host` does and why the gateway sends `$http_host` instead.
        """
        response = self.client.post(
            self.url,
            {'original_url': 'https://example.com', 'custom_alias': 'ported'},
            content_type='application/json',
            HTTP_HOST='short.example.com:8000',
        )
        self.assertEqual(
            response.json()['short_url'], 'http://short.example.com:8000/ported/'
        )

    def test_accepts_a_custom_alias(self):
        body = self._create(custom_alias='vanity').json()
        self.assertEqual(body['custom_alias'], 'vanity')
        self.assertIn('/vanity/', body['short_url'])

    def test_rejects_an_alias_already_taken(self):
        self._create(custom_alias='taken')
        response = self._create(custom_alias='taken')
        self.assertEqual(response.status_code, 400)
        self.assertIn('custom_alias', response.json())

    def test_rejects_an_alias_that_collides_with_a_generated_code(self):
        """A code is reachable by either column, so this would be ambiguous."""
        existing = URL.objects.create(original_url='https://example.com/1')
        response = self._create(custom_alias=existing.short_code)
        self.assertEqual(response.status_code, 400)
        self.assertIn('custom_alias', response.json())

    def test_rejects_a_malformed_url(self):
        self.assertEqual(self._create(original_url='not-a-url').status_code, 400)


class URLListAPITests(TestCase):
    def test_lists_only_active_urls(self):
        live = URL.objects.create(original_url='https://example.com/live')
        URL.objects.create(original_url='https://example.com/off', is_active=False)

        codes = [item['short_code'] for item in self.client.get('/api/v1/urls/').json()]
        self.assertEqual(codes, [live.short_code])


class RedirectViewTests(TestCase):
    def setUp(self):
        self.url = URL.objects.create(original_url='https://example.com/target')

    def test_redirects_by_short_code(self):
        response = self.client.get(f'/{self.url.short_code}/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://example.com/target')

    def test_redirects_by_custom_alias(self):
        URL.objects.create(original_url='https://example.com/alias', custom_alias='go')
        response = self.client.get('/go/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://example.com/alias')

    def test_increments_the_click_counter(self):
        for _ in range(3):
            self.client.get(f'/{self.url.short_code}/')

        self.url.refresh_from_db()
        self.assertEqual(self.url.click_count, 3)

    def test_expired_url_returns_410(self):
        self.url.expires_at = timezone.now() - timedelta(days=1)
        self.url.save()
        self.assertEqual(self.client.get(f'/{self.url.short_code}/').status_code, 410)

    def test_url_expiring_in_the_future_still_redirects(self):
        self.url.expires_at = timezone.now() + timedelta(days=1)
        self.url.save()
        self.assertEqual(self.client.get(f'/{self.url.short_code}/').status_code, 302)

    def test_inactive_url_returns_404(self):
        self.url.is_active = False
        self.url.save()
        self.assertEqual(self.client.get(f'/{self.url.short_code}/').status_code, 404)

    def test_unknown_code_returns_404(self):
        self.assertEqual(self.client.get('/nosuch/').status_code, 404)


class RoutingTests(TestCase):
    """The redirect catch-all must not swallow the routes above it."""

    def test_api_routes_win_over_the_catch_all(self):
        URL.objects.create(original_url='https://example.com', custom_alias='api')
        self.assertEqual(self.client.get('/api/v1/urls/').status_code, 200)

    def test_schema_is_served(self):
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
