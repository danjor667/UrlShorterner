"""Module 7: ownership, tiers, and what the token is allowed to decide."""

from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from ..models import URL
from .support import AuthenticatedAPITestCase, Caller


class AuthenticationRequiredTests(AuthenticatedAPITestCase):
    def test_create_requires_a_token(self):
        response = self.client.post(
            '/api/v1/urls/create/', {'original_url': 'https://example.com'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_list_requires_a_token(self):
        self.assertEqual(self.client.get('/api/v1/urls/').status_code, 401)

    def test_redirect_stays_anonymous(self):
        """The one endpoint that must not require a token."""
        url = URL.objects.create(original_url='https://example.com/pub')
        with patch('shortener.views.record_click'):
            response = self.client.get(f'/{url.short_code}/')
        self.assertEqual(response.status_code, 302)


class OwnerAssignmentTests(AuthenticatedAPITestCase):
    def test_create_assigns_the_caller_as_owner(self):
        caller = self.authenticate()
        self.client.post(
            '/api/v1/urls/create/', {'original_url': 'https://example.com'},
            content_type='application/json',
        )
        self.assertEqual(URL.objects.get().owner_id, caller.id)

    def test_owner_id_is_not_client_settable(self):
        caller = self.authenticate()
        self.client.post(
            '/api/v1/urls/create/',
            {'original_url': 'https://example.com', 'owner_id': 9999},
            content_type='application/json',
        )
        self.assertEqual(URL.objects.get().owner_id, caller.id)

    def test_list_is_scoped_to_the_caller(self):
        mine = self.authenticate()
        URL.objects.create(original_url='https://example.com/mine', owner_id=mine.id)
        URL.objects.create(original_url='https://example.com/theirs', owner_id=mine.id + 500)

        codes = [row['short_code'] for row in self.client.get('/api/v1/urls/').json()]
        self.assertEqual(codes, [URL.objects.get(owner_id=mine.id).short_code])


class OwnershipPermissionTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.owner = Caller()
        self.url = URL.objects.create(original_url='https://example.com/t', owner_id=self.owner.id)
        self.path = f'/api/v1/urls/{self.url.short_code}/'

    def _patch(self, title='changed'):
        return self.client.patch(self.path, {'title': title}, content_type='application/json')

    def test_owner_can_update(self):
        self.authenticate(self.owner)
        self.assertEqual(self._patch().status_code, 200)
        self.url.refresh_from_db()
        self.assertEqual(self.url.title, 'changed')

    def test_non_owner_cannot_update(self):
        self.authenticate(Caller())
        self.assertEqual(self._patch().status_code, 403)

    def test_non_owner_can_read(self):
        """Reads are open by design; only writes are owner-gated."""
        self.authenticate(Caller())
        self.assertEqual(self.client.get(self.path).status_code, 200)

    def test_owner_can_delete(self):
        self.authenticate(self.owner)
        self.assertEqual(self.client.delete(self.path).status_code, 204)
        self.assertFalse(URL.objects.filter(pk=self.url.pk).exists())

    def test_non_owner_cannot_delete(self):
        self.authenticate(Caller())
        self.assertEqual(self.client.delete(self.path).status_code, 403)
        self.assertTrue(URL.objects.filter(pk=self.url.pk).exists())

    def test_ownerless_url_is_nobodys_to_edit(self):
        orphan = URL.objects.create(original_url='https://example.com/orphan')
        self.authenticate()
        response = self.client.patch(
            f'/api/v1/urls/{orphan.short_code}/', {'title': 'x'}, content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_can_edit_any_url(self):
        self.authenticate(Caller(is_staff=True))
        self.assertEqual(self._patch().status_code, 200)

    def test_ownership_survives_the_string_typed_user_id_claim(self):
        """`TokenUser.id` is a string; `owner_id` is an integer column.

        Compared raw they never match and the owner is locked out of their own
        URL. This asserts the coercion in `caller_id()` is actually applied.
        """
        self.authenticate(self.owner)
        self.assertEqual(self._patch().status_code, 200)


class TierLimitTests(AuthenticatedAPITestCase):
    url = '/api/v1/urls/create/'

    def _create(self, **payload):
        payload.setdefault('original_url', 'https://example.com')
        return self.client.post(self.url, payload, content_type='application/json')

    def test_free_tier_capped_at_the_limit(self):
        caller = self.authenticate(Caller(tier='free'))
        for i in range(settings.FREE_TIER_URL_LIMIT):
            URL.objects.create(original_url=f'https://example.com/{i}', owner_id=caller.id)

        response = self._create()
        self.assertEqual(response.status_code, 400)
        self.assertIn(str(settings.FREE_TIER_URL_LIMIT), str(response.json()))

    def test_free_tier_below_the_limit_succeeds(self):
        self.authenticate(Caller(tier='free'))
        self.assertEqual(self._create().status_code, 201)

    def test_premium_tier_is_uncapped(self):
        caller = self.authenticate(Caller(tier='premium'))
        for i in range(settings.FREE_TIER_URL_LIMIT):
            URL.objects.create(original_url=f'https://example.com/{i}', owner_id=caller.id)

        self.assertEqual(self._create().status_code, 201)

    def test_free_tier_cannot_use_a_custom_alias(self):
        self.authenticate(Caller(tier='free'))
        response = self._create(custom_alias='vip')
        self.assertEqual(response.status_code, 400)
        self.assertIn('custom_alias', response.json())

    def test_premium_tier_can_use_a_custom_alias(self):
        self.authenticate(Caller(tier='premium'))
        response = self._create(custom_alias='vip')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['custom_alias'], 'vip')

    def test_the_is_premium_flag_alone_unlocks_aliases(self):
        self.authenticate(Caller(tier='free', is_premium=True))
        self.assertEqual(self._create(custom_alias='vip').status_code, 201)

    def test_admin_tier_counts_as_premium(self):
        self.authenticate(Caller(tier='admin'))
        self.assertEqual(self._create(custom_alias='vip').status_code, 201)
