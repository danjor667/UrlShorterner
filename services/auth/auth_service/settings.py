"""Auth service settings.

Owns the `account` app and the `auth` database. It is the only service that
defines a custom AUTH_USER_MODEL, and the only one whose `auth_user` table
means anything: the other two services still install `django.contrib.auth`
for the admin, but their user tables are local to them and unrelated to a
real account here.
"""

from common.base_settings import *  # noqa: F401,F403
from common.base_settings import INSTALLED_APPS, service_database

INSTALLED_APPS = INSTALLED_APPS + ['account']

DATABASES = {'default': service_database('auth')}

# The custom user has to be declared before the first migration runs against
# this database, which is why the account app ships its own 0001_initial.
AUTH_USER_MODEL = 'account.User'

ROOT_URLCONF = 'auth_service.urls'
WSGI_APPLICATION = 'auth_service.wsgi.application'

SERVICE_NAME = 'auth'

SPECTACULAR_SETTINGS = {
    'TITLE': 'Auth Service',
    'DESCRIPTION': 'Accounts and tiering. Registration and login arrive in Module 7.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
