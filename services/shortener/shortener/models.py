import random
import string

from django.db import models
from django.db.models import Q
from django.utils import timezone

from .managers import URLManager

SHORT_CODE_LENGTH = 6
SHORT_CODE_ALPHABET = string.ascii_letters + string.digits


def generate_short_code():
    return ''.join(random.choices(SHORT_CODE_ALPHABET, k=SHORT_CODE_LENGTH))


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class URL(models.Model):
    original_url = models.URLField(max_length=2048)
    short_code = models.CharField(max_length=10, unique=True, db_index=True, default=generate_short_code)
    custom_alias = models.CharField(max_length=10, unique=True, null=True, blank=True)
    # Not a ForeignKey: the user table belongs to the auth service and this
    # service does not install its app. Nothing at the database level enforces
    # that this points at a real user, and deleting one no longer cascades here.
    owner_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    # Tags, by contrast, are entirely this service's own — no boundary is
    # crossed, so a real ManyToManyField is still the right thing.
    tags = models.ManyToManyField(Tag, related_name='urls', blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    # A denormalized count of what analytics holds. The redirect only
    # increments it once analytics has durably recorded the click.
    click_count = models.PositiveIntegerField(default=0)

    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    favicon = models.URLField(max_length=2048, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = URLManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'expires_at'], name='url_active_expiry_idx'),
            models.Index(fields=['owner_id', '-created_at'], name='url_owner_created_idx'),
        ]

    def __str__(self):
        return f"{self.short_code} -> {self.original_url}"

    @property
    def active_code(self):
        return self.custom_alias or self.short_code

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    def save(self, *args, **kwargs):
        """Retry code generation so a collision is not a 500.

        The generated code must dodge existing custom aliases too, otherwise
        `for_code()` would match two rows and every lookup on it would 500.
        """
        if not self.short_code:
            self.short_code = generate_short_code()
        while self._state.adding and URL.objects.filter(
            Q(short_code=self.short_code) | Q(custom_alias=self.short_code)
        ).exists():
            self.short_code = generate_short_code()
        return super().save(*args, **kwargs)
