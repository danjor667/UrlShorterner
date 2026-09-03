"""Turning a click's IP address into a country.

Uses the DB-IP Lite database, which is the same `.mmdb` format MaxMind's
GeoLite2 uses and is read by the same `geoip2` library — but needs no account
and no licence key, so nothing has to be fetched by hand before the stack runs.
The file is baked into the image at build time; see the Dockerfile.

    IP Geolocation by DB-IP — https://db-ip.com
    Licensed CC-BY 4.0, which requires that attribution.

Nothing here raises. A click is worth recording even when it cannot be placed,
so every failure — no database, a private address, a malformed value — comes
back as blanks and the row is stored anyway.
"""

import ipaddress
import logging
import threading

import geoip2.database
import geoip2.errors
from django.conf import settings

logger = logging.getLogger(__name__)

BLANK = {'country': '', 'city': ''}

_reader = None
_reader_lock = threading.Lock()
_load_failed = False


def _get_reader():
    """Open the database once and keep it.

    The file is memory-mapped and the reader is safe for concurrent reads, so
    a single shared instance is both correct and cheaper than opening one per
    click. A missing file is logged once rather than on every request.
    """
    global _reader, _load_failed

    if _reader is not None or _load_failed:
        return _reader

    with _reader_lock:
        if _reader is not None or _load_failed:
            return _reader
        try:
            _reader = geoip2.database.Reader(str(settings.GEOIP_DB_PATH))
        except (OSError, ValueError) as exc:
            _load_failed = True
            logger.warning(
                'geolocation disabled — could not open %s: %s', settings.GEOIP_DB_PATH, exc
            )
        return _reader


def lookup(ip):
    """Return {'country': ..., 'city': ...} for an IP, blanks if unknown."""
    if not ip:
        return dict(BLANK)

    try:
        # Private and loopback ranges are simply not in the database. Checking
        # first turns the common local-development case into a cheap no-op
        # instead of an exception on every click.
        if ipaddress.ip_address(str(ip)).is_global is False:
            return dict(BLANK)
    except ValueError:
        return dict(BLANK)

    reader = _get_reader()
    if reader is None:
        return dict(BLANK)

    try:
        # A country-only database has no city data and raises if asked for it.
        # Choosing the call from the file's own metadata means swapping in the
        # larger City database is a change of URL, not a change of code.
        if 'City' in reader.metadata().database_type:
            response = reader.city(str(ip))
            return {
                'country': response.country.iso_code or '',
                'city': (response.city.name or '')[:100],
            }
        response = reader.country(str(ip))
        return {'country': response.country.iso_code or '', 'city': ''}
    except geoip2.errors.AddressNotFoundError:
        return dict(BLANK)
    except (ValueError, geoip2.errors.GeoIP2Error) as exc:
        logger.warning('geolocation failed for %s: %s', ip, exc)
        return dict(BLANK)
