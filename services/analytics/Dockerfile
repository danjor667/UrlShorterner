FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/libs

# Never run as root: a container escape should not land on uid 0. The user and
# the directory tree are created up front so each COPY can land already-owned
# (--chown) instead of a recursive chown afterwards duplicating the tree in a
# new layer. staticfiles/ is pre-created because collectstatic writes there at
# runtime as appuser, who cannot mkdir under a root-owned /app.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/libs /app/services/analytics /app/staticfiles \
    && chown -R appuser:appuser /app

WORKDIR /app/services/analytics

# Build context is the repo root so the shared settings base in libs/ can be
# copied in (see .dockerignore); requirements are copied first to keep the pip
# layer cached. pip runs as root so packages land in /usr/local, not /app.
COPY --chown=appuser:appuser services/analytics/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The IP geolocation database, baked in rather than mounted so `docker compose
# up --build` needs no setup step and nothing lands in git.
#
#   IP Geolocation by DB-IP — https://db-ip.com  (CC-BY 4.0, attribution required)
#
# Same .mmdb format as MaxMind's GeoLite2 and read by the same library, but
# free of an account and a licence key. Two things this has to work around:
# the slim image has no curl, and the CDN answers 403 without a User-Agent.
# The current month's file is not published on the 1st, hence the fallback.
RUN mkdir -p /app/geoip && python - <<'PYEOF'
import gzip, pathlib, urllib.request
from datetime import date, timedelta

today = date.today()
months = [today.strftime('%Y-%m'), (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')]
target = pathlib.Path('/app/geoip/dbip-country-lite.mmdb')

for month in months:
    url = f'https://download.db-ip.com/free/dbip-country-lite-{month}.mmdb.gz'
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'urlshortener-build'})
        with urllib.request.urlopen(request, timeout=180) as response:
            target.write_bytes(gzip.decompress(response.read()))
        print(f'geoip: fetched {month} ({target.stat().st_size // 1024} KiB)')
        break
    except Exception as exc:
        print(f'geoip: {month} unavailable ({exc})')
else:
    # Failing here rather than shipping an image that silently records no
    # country. The build already needs the network for pip.
    raise SystemExit('geoip: could not download the database from any month')
PYEOF
RUN chown -R appuser:appuser /app/geoip

COPY --chown=appuser:appuser libs /app/libs
COPY --chown=appuser:appuser services/analytics /app/services/analytics

# Re-copied after the source tree so the explicit mode wins over whatever the
# host happens to have on the file.
COPY --chown=appuser:appuser --chmod=0755 services/analytics/entrypoint.sh ./entrypoint.sh

USER appuser

EXPOSE 8000

# The entrypoint runs migrate + collectstatic, then execs this CMD. compose no
# longer overrides `command:`, so this is the single definition of how the
# service starts.
ENTRYPOINT ["/app/services/analytics/entrypoint.sh"]
CMD ["gunicorn", "analytics_service.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
