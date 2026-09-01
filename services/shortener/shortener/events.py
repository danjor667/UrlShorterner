"""Publishing URL metadata to the analytics service.

Analytics cannot join to this service's `url` table, so it keeps a local copy
of the few fields its reporting endpoint needs. This module keeps that copy
current.

Unlike `analytics_client.record_click`, these publishes are **best effort**: a
failure is logged and the write here still succeeds. The two are different
kinds of data. A dropped click is gone for good, so the redirect refuses to
serve rather than lose it. A stale projection is a read model that has fallen
behind — recoverable, and not worth failing a URL creation over.

"Recoverable" needs something to recover it, though. Without Celery to retry
(that arrives in Module 8), the backstop is `manage.py republish_urls`.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _endpoint(path):
    return f"{settings.ANALYTICS_URL.rstrip('/')}/internal/urls/{path}"


def projection_payload(url):
    """The subset of a URL that analytics is allowed to know about."""
    return {
        'url_id': url.pk,
        'short_code': url.short_code,
        'custom_alias': url.custom_alias,
        'original_url': url.original_url,
        'owner_id': url.owner_id,
        'is_active': url.is_active,
    }


def publish_url_upsert(url, raise_on_error=False):
    """Tell analytics what this URL looks like now."""
    try:
        response = requests.post(
            _endpoint(''), json=projection_payload(url), timeout=settings.ANALYTICS_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        if raise_on_error:
            raise
        logger.warning('projection not published for url %s: %s', url.pk, exc)
        return False
    return True


def publish_url_deleted(url_id, raise_on_error=False):
    """Tell analytics to drop its copy."""
    try:
        response = requests.delete(_endpoint(f'{url_id}/'), timeout=settings.ANALYTICS_TIMEOUT)
        # A projection that was never published is already in the desired state.
        if response.status_code != 404:
            response.raise_for_status()
    except requests.RequestException as exc:
        if raise_on_error:
            raise
        logger.warning('deletion not published for url %s: %s', url_id, exc)
        return False
    return True
