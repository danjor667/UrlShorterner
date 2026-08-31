FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/libs

WORKDIR /app/services/shortener

# Build context is the repo root so the shared settings base in libs/ can be
# copied in; requirements are copied first to keep the pip layer cached.
COPY services/shortener/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs /app/libs
COPY services/shortener /app/services/shortener

# Never run as root: a container escape should not land on uid 0.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "shortener_service.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
