from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):


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


    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
