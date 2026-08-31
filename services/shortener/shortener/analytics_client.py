"""The shortener's one outbound dependency: the analytics service.

Click history lives in another service's database, so recording a click is an
HTTP call rather than an INSERT. The call is synchronous and its failure is
not swallowed — see `record_click`.
"""

import requests
from django.conf import settings


class AnalyticsUnavailable(Exception):
    """Analytics did not durably record the click."""


def record_click(url_id, request):
    """Report one click to the analytics service.

    Raises `AnalyticsUnavailable` on a timeout, a connection error or any
    non-2xx response. The caller turns that into a 502 rather than redirecting:
    the click log is the source of truth for analytics, and a redirect that
    quietly loses events would leave the two services permanently disagreeing.

    The trade is that analytics is on the critical path of every public
    redirect. Module 8 moves this onto a Celery task, which is what makes the
    dependency optional again.
    """
    payload = {
        'url_id': url_id,
        'ip_address': request.META.get('REMOTE_ADDR') or None,
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:1000],
        'referrer': request.META.get('HTTP_REFERER', '')[:2048],
    }
    endpoint = f"{settings.ANALYTICS_URL.rstrip('/')}/internal/clicks/"

    try:
        response = requests.post(endpoint, json=payload, timeout=settings.ANALYTICS_TIMEOUT)
    except requests.RequestException as exc:
        raise AnalyticsUnavailable(str(exc)) from exc

    if not 200 <= response.status_code < 300:
        raise AnalyticsUnavailable(
            f'analytics returned {response.status_code}: {response.text[:200]}'
        )
    return response
