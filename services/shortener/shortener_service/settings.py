"""Shortener service settings.

Owns the `shortener` app and, with it, the `shortener` database — its own
Postgres container, which nothing else connects to. Users live in the auth
service and clicks in the analytics service, so neither is reachable from here
by a query; see `owner_id` in shortener/models.py and ANALYTICS_URL below.
"""

from decouple import config

from common.base_settings import *  # noqa: F401,F403
from common.base_settings import INSTALLED_APPS, service_database

INSTALLED_APPS = INSTALLED_APPS + ['shortener']

# Declared here, not in base settings: the database a service owns is one of
# the few things that is genuinely its own. DB_* environment variables
# override, which is how compose points this at the db-shortener container.
DATABASES = {'default': service_database('shortener')}

# The analytics service, reached over the compose network. This is the only
# service the shortener calls: click history is not in its database, so
# recording a click is an HTTP request. See shortener/analytics_client.py.
ANALYTICS_URL = config('ANALYTICS_URL', default='http://analytics:8000')
ANALYTICS_TIMEOUT = config('ANALYTICS_TIMEOUT', default=3.0, cast=float)

ROOT_URLCONF = 'shortener_service.urls'
WSGI_APPLICATION = 'shortener_service.wsgi.application'

SERVICE_NAME = 'shortener'

SPECTACULAR_SETTINGS = {
    'TITLE': 'Shortener Service',
    'DESCRIPTION': 'Short URL creation, listing and public redirection.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
