"""The shortener's one outbound dependency: the analytics service.

Click history lives in another service's database, so recording a click is an
HTTP call rather than an INSERT. The call is synchronous and its failure is
not swallowed — see `record_click`.
"""

import requests
from django.conf import settings


class AnalyticsUnavailable(Exception):
    """Analytics did not durably record the click."""


def client_ip(request):
    """The visitor's address, not the proxy's.

    Behind the gateway `REMOTE_ADDR` is nginx, so every click would otherwise
    be recorded as the gateway's container address — which is what was
    happening, and why no geolocation could ever resolve.

    `X-Real-IP` is set by nginx with `$remote_addr` and *overwrites* whatever
    arrived, so a visitor cannot forge it. `X-Forwarded-For` is deliberately
    not used: nginx appends to that one, leaving any client-supplied value at
    the front where a naive reader would trust it.

    Falls back to `REMOTE_ADDR` for direct access that does not pass through
    the gateway — docker-compose.local.yml, and tests.
    """
    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR') or None


def record_click(url_id, request):
    """Report one click to the analytics service.

    Raises `AnalyticsUnavailable` on a timeout, a connection error or any
    non-2xx response. The caller logs that and redirects anyway — a report with
    a gap is a much smaller failure than a short link that does not resolve.

    Raising rather than swallowing the error here is still the right shape: the
    decision about what an unreachable analytics service means belongs to the
    caller, not to the transport. Module 8 changes that answer again by putting
    the click on a queue that survives the outage entirely.
    """
    payload = {
        'url_id': url_id,
        'ip_address': client_ip(request),
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
