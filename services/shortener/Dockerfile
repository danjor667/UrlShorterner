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
    && mkdir -p /app/libs /app/services/shortener /app/staticfiles \
    && chown -R appuser:appuser /app

WORKDIR /app/services/shortener

# Build context is the repo root so the shared settings base in libs/ can be
# copied in (see .dockerignore); requirements are copied first to keep the pip
# layer cached. pip runs as root so packages land in /usr/local, not /app.
COPY --chown=appuser:appuser services/shortener/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser libs /app/libs
COPY --chown=appuser:appuser services/shortener /app/services/shortener

# Re-copied after the source tree so the explicit mode wins over whatever the
# host happens to have on the file.
COPY --chown=appuser:appuser --chmod=0755 services/shortener/entrypoint.sh ./entrypoint.sh

USER appuser

EXPOSE 8000

# The entrypoint runs migrate + collectstatic, then execs this CMD. compose no
# longer overrides `command:`, so this is the single definition of how the
# service starts.
ENTRYPOINT ["/app/services/shortener/entrypoint.sh"]
CMD ["gunicorn", "shortener_service.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
