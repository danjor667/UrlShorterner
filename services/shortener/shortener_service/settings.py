"""Shortener service settings.

The only service in Module 5. It owns the `shortener` app; the database it
connects to is shared with every service added later, and comes from
`common.settings` unchanged.
"""

from common.settings import *  # noqa: F401,F403
from common.settings import INSTALLED_APPS

INSTALLED_APPS = INSTALLED_APPS + ['shortener']

ROOT_URLCONF = 'shortener_service.urls'
WSGI_APPLICATION = 'shortener_service.wsgi.application'

SERVICE_NAME = 'shortener'

SPECTACULAR_SETTINGS = {
    'TITLE': 'Shortener Service',
    'DESCRIPTION': 'Short URL creation, listing and public redirection.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
