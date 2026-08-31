"""Shortener service settings.

The only service in Module 5. It owns the `shortener` app and, with it, the
`shortener` database — its own Postgres container, which nothing else connects
to. Everything else comes from `common.base_settings` unchanged.
"""

from common.base_settings import *  # noqa: F401,F403
from common.base_settings import INSTALLED_APPS, service_database

INSTALLED_APPS = INSTALLED_APPS + ['shortener']

# Declared here, not in base settings: the database a service owns is one of
# the few things that is genuinely its own. DB_* environment variables
# override, which is how compose points this at the db-shortener container.
DATABASES = {'default': service_database('shortener')}

ROOT_URLCONF = 'shortener_service.urls'
WSGI_APPLICATION = 'shortener_service.wsgi.application'

SERVICE_NAME = 'shortener'

SPECTACULAR_SETTINGS = {
    'TITLE': 'Shortener Service',
    'DESCRIPTION': 'Short URL creation, listing and public redirection.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
