#!/bin/sh
set -e

python manage.py makemigrations
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# exec so gunicorn becomes PID 1 and receives SIGTERM directly on shutdown.
exec "$@"
