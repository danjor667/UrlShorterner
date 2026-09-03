"""Query logic for the URL model.

Kept out of models.py so the model file describes the shape of the data and
this one describes how it is queried. The split matters more here than it
looks: two of these methods only make sense once you know the click table
lives in another service's database, and that reasoning is easier to keep
straight in one place than scattered through a model definition.

Nothing here imports the model. A QuerySet operates on `self`, so this module
stays free of the circular import that `from .models import URL` would create.
"""

from django.db import models
from django.db.models import Q
from django.utils import timezone


class URLQuerySet(models.QuerySet):

    def active(self):
        return self.filter(
            Q(is_active=True) & (Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        )

    def expired(self):
        return self.filter(expires_at__isnull=False, expires_at__lte=timezone.now())

    def popular(self):
        """Rank by the denormalized counter.
        """
        return self.order_by('-click_count')

    def for_code(self, code):
        """Resolve either the generated code or a custom alias in one query."""
        return self.filter(Q(short_code=code) | Q(custom_alias=code))

    def with_related(self):
        return self.prefetch_related('tags')


class URLManager(models.Manager):

    def get_queryset(self):
        return URLQuerySet(self.model, using=self._db)

    def active_urls(self):
        return self.get_queryset().active()

    def expired_urls(self):
        return self.get_queryset().expired()

    def popular_urls(self, limit=None):
        qs = self.get_queryset().active().popular()
        return qs[:limit] if limit else qs
