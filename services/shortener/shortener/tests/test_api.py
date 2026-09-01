"""Shortener service tests — Module 7.

Create a short URL, list the active ones, redirect, and tag. As of Module 7
every endpoint but the public redirect needs a token, so these tests
authenticate as a caller that exists only as JWT claims — see tests/support.py
for why that is not a shortcut.

The redirect now calls the analytics service, so every test that follows a
short link patches `record_click`. That is the point of isolating it behind
one function: a unit test of the shortener should not need a second service
running. The real call is exercised end-to-end against a live stack instead.
"""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from ..analytics_client import AnalyticsUnavailable
from ..models import URL, Tag
from .support import AuthenticatedAPITestCase, Caller


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


class URLCreateAPITests(AuthenticatedAPITestCase):
    url = '/api/v1/urls/create/'

    def setUp(self):
        # Premium: several of these exercise custom aliases, which Module 7
        # made a paid feature. The tier gate itself is covered in
        # test_auth_api.py rather than incidentally here.
        self.caller = self.authenticate(Caller(tier='premium'))

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


class URLListAPITests(AuthenticatedAPITestCase):
    def test_lists_only_active_urls(self):
        caller = self.authenticate()
        live = URL.objects.create(original_url='https://example.com/live', owner_id=caller.id)
        URL.objects.create(
            original_url='https://example.com/off', owner_id=caller.id, is_active=False
        )

        codes = [item['short_code'] for item in self.client.get('/api/v1/urls/').json()]
        self.assertEqual(codes, [live.short_code])


class RedirectViewTests(TestCase):
    def setUp(self):
        self.url = URL.objects.create(original_url='https://example.com/target')
        # Analytics is a hard dependency of the redirect path; stub it so
        # these tests describe the shortener's behaviour, not the network's.
        patcher = patch('shortener.views.record_click')
        self.record_click = patcher.start()
        self.addCleanup(patcher.stop)

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

    def test_click_is_reported_to_analytics(self):
        self.client.get(f'/{self.url.short_code}/', HTTP_USER_AGENT='pytest-agent')

        self.record_click.assert_called_once()
        url_id, request = self.record_click.call_args.args
        self.assertEqual(url_id, self.url.pk)
        self.assertEqual(request.META.get('HTTP_USER_AGENT'), 'pytest-agent')

    def test_redirect_still_works_when_analytics_is_down(self):
        """A reporting outage must never break a link.

        This is the whole point of the click write being best effort: every
        short URL in the system would otherwise stop resolving whenever a
        non-critical service went down.
        """
        self.record_click.side_effect = AnalyticsUnavailable('connection refused')

        response = self.client.get(f'/{self.url.short_code}/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://example.com/target')

    def test_counter_still_advances_when_analytics_is_down(self):
        """click_count records redirects served, not rows analytics holds.

        After an outage it reads higher than the analytics row count, and the
        difference is exactly what was lost. That is a reported gap rather than
        a silent one.
        """
        self.record_click.side_effect = AnalyticsUnavailable('connection refused')

        self.client.get(f'/{self.url.short_code}/')

        self.url.refresh_from_db()
        self.assertEqual(self.url.click_count, 1)

    def test_lost_click_is_logged(self):
        """The gap has to be visible to an operator; nothing else records it."""
        self.record_click.side_effect = AnalyticsUnavailable('connection refused')

        with self.assertLogs('shortener.views', level='ERROR') as logs:
            self.client.get(f'/{self.url.short_code}/')

        self.assertIn('click lost', logs.output[0])

    def test_expired_url_is_not_reported_as_a_click(self):
        self.url.expires_at = timezone.now() - timedelta(days=1)
        self.url.save()

        self.client.get(f'/{self.url.short_code}/')

        self.record_click.assert_not_called()


class RoutingTests(AuthenticatedAPITestCase):
    """The redirect catch-all must not swallow the routes above it."""

    def test_api_routes_win_over_the_catch_all(self):
        self.authenticate()
        URL.objects.create(original_url='https://example.com', custom_alias='api')
        self.assertEqual(self.client.get('/api/v1/urls/').status_code, 200)

    def test_schema_is_served(self):
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
