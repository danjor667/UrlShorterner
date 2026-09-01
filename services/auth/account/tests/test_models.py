"""Auth service tests — the custom user and its tiering."""

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.test import TestCase

User = get_user_model()


class UserModelTests(TestCase):
    def test_the_custom_model_is_installed_as_auth_user_model(self):
        self.assertEqual(User._meta.label, 'account.User')

    def test_defaults_to_free_tier(self):
        user = User.objects.create_user(username='a', email='a@example.com', password='pw')
        self.assertEqual(user.tier, User.Tier.FREE)
        self.assertFalse(user.is_premium)
        self.assertFalse(user.has_premium_access)

    def test_email_is_unique(self):
        User.objects.create_user(username='a', email='dup@example.com', password='pw')
        with self.assertRaises(IntegrityError):
            User.objects.create_user(username='b', email='dup@example.com', password='pw')

    def test_has_premium_access_for_premium_and_admin_tiers(self):
        premium = User.objects.create_user(
            username='p', email='p@example.com', password='pw', tier=User.Tier.PREMIUM
        )
        admin = User.objects.create_user(
            username='ad', email='ad@example.com', password='pw', tier=User.Tier.ADMIN
        )
        flagged = User.objects.create_user(
            username='f', email='f@example.com', password='pw', is_premium=True
        )

        self.assertTrue(premium.has_premium_access)
        self.assertTrue(admin.has_premium_access)
        self.assertTrue(flagged.has_premium_access)

    def test_free_tier_without_the_flag_has_no_premium_access(self):
        user = User.objects.create_user(username='n', email='n@example.com', password='pw')
        self.assertFalse(user.has_premium_access)


class RoutingTests(TestCase):
    def test_schema_is_served_under_the_service_prefix(self):
        """Not the bare /api/schema/ — the shortener owns that behind the
        gateway, so only one of the three can publish there."""
        self.assertEqual(self.client.get('/api/schema/auth/').status_code, 200)
        self.assertEqual(self.client.get('/api/schema/').status_code, 404)

    def test_swagger_ui_is_served_under_the_service_prefix(self):
        self.assertEqual(self.client.get('/api/docs/auth/').status_code, 200)

    def test_admin_is_mounted_under_the_service_prefix(self):
        """Not the bare /admin/ — the shortener owns that behind the gateway."""
        self.assertEqual(self.client.get('/admin/auth/').status_code, 302)  # -> login
        self.assertEqual(self.client.get('/admin/').status_code, 404)
