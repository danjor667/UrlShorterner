from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with tiering, used as AUTH_USER_MODEL.

    This table lives in the auth service's database and nothing else joins to
    it. The shortener stores an `owner_id` integer pointing here; that is a
    reference the database does not enforce, so deleting a user does not
    cascade to their URLs the way a ForeignKey would.
    """

    class Tier(models.TextChoices):
        FREE = 'free', 'Free'
        PREMIUM = 'premium', 'Premium'
        ADMIN = 'admin', 'Admin'

    email = models.EmailField(unique=True)
    is_premium = models.BooleanField(default=False)
    tier = models.CharField(max_length=10, choices=Tier.choices, default=Tier.FREE)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.username

    @property
    def has_premium_access(self):
        """Single place for Module 7 tier checks to hang off."""
        return self.is_premium or self.tier in (self.Tier.PREMIUM, self.Tier.ADMIN)
