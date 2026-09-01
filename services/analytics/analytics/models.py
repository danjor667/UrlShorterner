"""The analytics service's own tables.

Two models, and no foreign key leaving the service. `Click` is the event log
this service owns outright. `URLProjection` is a local read model: analytics
cannot join to the shortener's `url` table, so it keeps the few fields its
endpoint needs and the shortener keeps them current by publishing on save.

The projection is eventually consistent by construction. A URL created a moment
ago may not be here yet, and that is the trade for answering a report without a
synchronous call to another service.
"""

from django.db import models


class URLProjection(models.Model):
    """A local copy of the shortener's URL, maintained by published events.
    """

    url_id = models.BigIntegerField(primary_key=True)
    short_code = models.CharField(max_length=10, db_index=True)
    custom_alias = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    original_url = models.URLField(max_length=2048)
    owner_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.active_code} -> {self.original_url}"

    @property
    def active_code(self):
        return self.custom_alias or self.short_code

    @classmethod
    def for_code(cls, code):
        return cls.objects.filter(models.Q(short_code=code) | models.Q(custom_alias=code))


class Click(models.Model):
    url_id = models.BigIntegerField(db_index=True)
    clicked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(max_length=2048, blank=True)

    class Meta:
        ordering = ['-clicked_at']
        indexes = [
            models.Index(fields=['url_id', '-clicked_at'], name='click_url_time_idx'),
        ]

    def __str__(self):
        return f"url {self.url_id} @ {self.clicked_at:%Y-%m-%d %H:%M}"
