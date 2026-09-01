"""The premium reporting endpoint, answered from this service's own tables."""

from django.test import TestCase

from ..models import Click, URLProjection
from .support import AuthenticatedAPITestCase, Caller


def project(url_id=1, owner_id=1, short_code='abc123', **kwargs):
    kwargs.setdefault('original_url', 'https://example.com/target')
    return URLProjection.objects.create(
        url_id=url_id, owner_id=owner_id, short_code=short_code, **kwargs
    )


class AnalyticsAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        self.owner = Caller(tier='premium')
        self.url = project(url_id=1, owner_id=self.owner.id)
        self.path = f'/api/v1/analytics/{self.url.short_code}/'

        Click.objects.create(url_id=1, ip_address='10.0.0.1', country='NG')
        Click.objects.create(url_id=1, ip_address='10.0.0.1', country='NG')
        Click.objects.create(url_id=1, ip_address='10.0.0.2', country='US')
        # A different URL's clicks must not leak into this report.
        Click.objects.create(url_id=2, ip_address='10.0.0.3', country='US')

    def test_premium_owner_sees_the_breakdown(self):
        self.authenticate(self.owner)
        body = self.client.get(self.path).json()

        self.assertEqual(body['total_clicks'], 3)
        self.assertEqual(body['unique_visitors'], 2)
        self.assertEqual(body['clicks_by_country'], {'NG': 2, 'US': 1})
        self.assertEqual(len(body['recent_clicks']), 3)
        self.assertEqual(body['original_url'], 'https://example.com/target')

    def test_ownership_survives_the_string_typed_user_id_claim(self):
        """`TokenUser.id` is a string; `owner_id` is an integer column.

        Compared raw they never match and the owner is locked out of their own
        analytics. `caller_id()` is what makes this pass.
        """
        self.authenticate(self.owner)
        self.assertEqual(self.client.get(self.path).status_code, 200)

    def test_resolves_a_custom_alias_too(self):
        aliased = project(url_id=3, owner_id=self.owner.id, short_code='xyz789',
                          custom_alias='promo')
        self.authenticate(self.owner)
        response = self.client.get('/api/v1/analytics/promo/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['short_code'], aliased.active_code)

    def test_free_tier_is_denied(self):
        self.authenticate(Caller(tier='free'))
        self.assertEqual(self.client.get(self.path).status_code, 403)

    def test_premium_non_owner_is_denied(self):
        """IsPremium alone would let any premium caller read anyone's report."""
        self.authenticate(Caller(tier='premium'))
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 403)
        self.assertIn('do not own', response.json()['detail'])

    def test_staff_may_read_any_url(self):
        self.authenticate(Caller(tier='premium', is_staff=True))
        self.assertEqual(self.client.get(self.path).status_code, 200)

    def test_anonymous_is_denied(self):
        self.assertEqual(self.client.get(self.path).status_code, 401)

    def test_unknown_code_is_404(self):
        self.authenticate(self.owner)
        self.assertEqual(self.client.get('/api/v1/analytics/nosuch/').status_code, 404)


class ProjectionInternalAPITests(TestCase):
    """The shortener's writes into the read model."""

    url = '/internal/urls/'

    def _payload(self, **kwargs):
        payload = {
            'url_id': 1, 'short_code': 'abc123', 'custom_alias': None,
            'original_url': 'https://example.com/', 'owner_id': 7, 'is_active': True,
        }
        payload.update(kwargs)
        return payload

    def test_creates_a_projection(self):
        response = self.client.post(self.url, self._payload(), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(URLProjection.objects.get().short_code, 'abc123')

    def test_republishing_updates_rather_than_duplicating(self):
        """`manage.py republish_urls` replays the whole table; it must be safe."""
        self.client.post(self.url, self._payload(), content_type='application/json')
        response = self.client.post(
            self.url, self._payload(original_url='https://example.com/moved'),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(URLProjection.objects.count(), 1)
        self.assertEqual(URLProjection.objects.get().original_url, 'https://example.com/moved')

    def test_delete_removes_the_projection_but_keeps_the_clicks(self):
        self.client.post(self.url, self._payload(), content_type='application/json')
        Click.objects.create(url_id=1)

        response = self.client.delete('/internal/urls/1/')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(URLProjection.objects.exists())
        # Deleting a short link should not rewrite the history of what
        # happened while it existed.
        self.assertEqual(Click.objects.filter(url_id=1).count(), 1)

    def test_deleting_an_unknown_projection_is_404(self):
        self.assertEqual(self.client.delete('/internal/urls/999/').status_code, 404)

    def test_the_internal_api_needs_no_token(self):
        """It is protected by the network boundary, not by authentication."""
        response = self.client.post(self.url, self._payload(), content_type='application/json')
        self.assertEqual(response.status_code, 201)
