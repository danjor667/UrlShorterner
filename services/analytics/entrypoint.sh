#!/bin/sh
# Startup sequence for the analytics service. This lives here rather than in
# docker-compose.yml's `command:` so the image boots the same way under
# `docker run` as it does under compose — there is one definition, not two
# that drift apart.
#
# Both steps are idempotent, so re-running them on every container start is
# safe for this single-replica service. If the service is ever scaled out,
# migrate belongs in a separate one-shot job instead: concurrent migrate
# processes race.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# exec so gunicorn becomes PID 1 and receives SIGTERM directly on shutdown.
exec "$@"
