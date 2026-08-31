"""Analytics service settings.

Owns the `analytics` app and the `analytics` database — the click event log.
It holds no foreign key to the shortener's `url` table, because that table is
in another database entirely; see analytics/models.py.
"""

from common.base_settings import *  # noqa: F401,F403
from common.base_settings import INSTALLED_APPS, service_database

INSTALLED_APPS = INSTALLED_APPS + ['analytics']

DATABASES = {'default': service_database('analytics')}

ROOT_URLCONF = 'analytics_service.urls'
WSGI_APPLICATION = 'analytics_service.wsgi.application'

SERVICE_NAME = 'analytics'

SPECTACULAR_SETTINGS = {
    'TITLE': 'Analytics Service',
    'DESCRIPTION': 'Click event log. The public reporting endpoint arrives in Module 7.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
