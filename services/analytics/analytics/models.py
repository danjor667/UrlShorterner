"""The analytics service's own tables.

One model, and no foreign key leaving the service. `Click` is the event log
this service owns outright: the shortener writes to it over HTTP and never
touches the table directly.
"""

from django.db import models


class Click(models.Model):
    # Not a ForeignKey: the url table belongs to the shortener service and
    # lives in a different database, so nothing here can reference it. Nothing
    # at the database level enforces that this points at a live URL, and
    # deleting one does not cascade. Module 7 adds the reporting endpoint that
    # reads these rows; Module 8 makes the write asynchronous.
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
