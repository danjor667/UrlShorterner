"""Registration, login and the token contract.

The claims asserted here are an interface: the shortener and analytics services
have no user table and read `tier`, `is_premium`, `is_staff` and `username`
straight off the token. Changing what this service puts in a token silently
changes what those two services are able to decide.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

User = get_user_model()

PASSWORD = 'corr3ct-horse-9'


class RegisterAPITests(TestCase):
    url = '/api/v1/auth/register/'

    def _register(self, **payload):
        payload.setdefault('username', 'alice')
        payload.setdefault('email', 'alice@example.com')
        payload.setdefault('password', PASSWORD)
        payload.setdefault('password_confirm', PASSWORD)
        return self.client.post(self.url, payload, content_type='application/json')

    def test_returns_a_token_pair_on_the_free_tier(self):
        response = self._register()
        body = response.json()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(body['access'])
        self.assertTrue(body['refresh'])
        self.assertEqual(body['user']['tier'], User.Tier.FREE)
        self.assertNotIn('password', body['user'])

    def test_password_is_hashed(self):
        self._register()
        user = User.objects.get(email='alice@example.com')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_mismatched_passwords_rejected(self):
        response = self._register(password_confirm='something-else-9')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password_confirm', response.json())

    def test_weak_password_rejected(self):
        response = self._register(password='123', password_confirm='123')
        self.assertEqual(response.status_code, 400)

    def test_duplicate_email_rejected_case_insensitively(self):
        self._register()
        response = self._register(username='alice2', email='ALICE@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json())

    def test_tier_is_not_client_settable(self):
        """Registering premium would otherwise be a self-service upgrade."""
        response = self._register(tier=User.Tier.PREMIUM, is_premium=True)
        self.assertEqual(response.status_code, 201)

        user = User.objects.get(email='alice@example.com')
        self.assertEqual(user.tier, User.Tier.FREE)
        self.assertFalse(user.is_premium)


class LoginAPITests(TestCase):
    url = '/api/v1/auth/login/'

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(
            username='alice', email='alice@example.com', password=PASSWORD,
            tier=User.Tier.PREMIUM,
        )

    def _login(self, **payload):
        # USERNAME_FIELD is `email`, so that is the credential simplejwt wants
        # — posting `username` here silently 400s.
        payload.setdefault('email', 'alice@example.com')
        payload.setdefault('password', PASSWORD)
        return self.client.post(self.url, payload, content_type='application/json')

    def test_valid_credentials_return_tokens(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['access'])

    def test_invalid_credentials_rejected(self):
        self.assertEqual(self._login(password='wrong-one-8').status_code, 401)

    def test_access_token_carries_the_claims_other_services_read(self):
        access = AccessToken(self._login().json()['access'])

        self.assertEqual(access['tier'], User.Tier.PREMIUM)
        self.assertTrue(access['is_premium'])
        self.assertEqual(access['username'], 'alice')
        self.assertIs(access['is_staff'], False)

    def test_admin_tier_reaches_downstream_as_premium(self):
        """`is_premium` carries has_premium_access, not the raw column."""
        self.user.tier = User.Tier.ADMIN
        self.user.is_premium = False
        self.user.save()

        access = AccessToken(self._login().json()['access'])
        self.assertTrue(access['is_premium'])

    def test_refresh_returns_a_new_access_token(self):
        refresh = self._login().json()['refresh']
        response = self.client.post(
            '/api/v1/auth/refresh/', {'refresh': refresh}, content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['access'])

    def test_login_is_rate_limited(self):
        # DRF binds THROTTLE_RATES at import, so override_settings would not
        # reach it. Read the live rate instead.
        limit = int(ScopedRateThrottle().THROTTLE_RATES['login'].split('/')[0])
        for _ in range(limit):
            self._login(password='wrong-one-8')

        # Even correct credentials are refused once the burst is spent.
        self.assertEqual(self._login().status_code, 429)


class MeAPITests(TestCase):
    url = '/api/v1/auth/me/'

    def test_requires_a_token(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_returns_the_token_holder(self):
        user = User.objects.create_user(
            username='alice', email='alice@example.com', password=PASSWORD
        )
        token = RefreshToken.for_user(user).access_token
        response = self.client.get(self.url, HTTP_AUTHORIZATION=f'Bearer {token}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'alice@example.com')


class UpgradeAPITests(TestCase):
    url = '/api/v1/auth/upgrade/'

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(
            username='alice', email='alice@example.com', password=PASSWORD
        )
        token = RefreshToken.for_user(self.user).access_token
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def test_requires_authentication(self):
        self.assertEqual(self.client.post(self.url).status_code, 401)

    def test_moves_the_caller_to_premium(self):
        response = self.client.post(self.url, **self.auth)

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.tier, User.Tier.PREMIUM)
        self.assertTrue(self.user.has_premium_access)

    def test_returns_a_token_that_already_says_premium(self):
        """The reissue is the point.

        Without it the caller keeps presenting the token that still says
        `free`, and every premium feature in the other services keeps refusing
        them until they happen to log in again.
        """
        body = self.client.post(self.url, **self.auth).json()

        access = AccessToken(body['access'])
        self.assertEqual(access['tier'], User.Tier.PREMIUM)
        self.assertTrue(access['is_premium'])
        self.assertTrue(body['refresh'])

    def test_upgrading_twice_is_not_an_error(self):
        self.client.post(self.url, **self.auth)
        response = self.client.post(self.url, **self.auth)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['tier'], User.Tier.PREMIUM)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url, **self.auth).status_code, 405)
