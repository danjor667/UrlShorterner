"""Auth service settings.

Owns the `account` app and the `auth` database. It is the only service that
defines a custom AUTH_USER_MODEL, and the only one whose `auth_user` table
means anything: the other two services still install `django.contrib.auth`
for the admin, but their user tables are local to them and unrelated to a
real account here.
"""

from common.base_settings import *  # noqa: F401,F403
from common.base_settings import INSTALLED_APPS, REST_FRAMEWORK, service_database

INSTALLED_APPS = INSTALLED_APPS + [
    'rest_framework_simplejwt',
    # Needs a user table to record blacklisted tokens, so it can only live here.
    'rest_framework_simplejwt.token_blacklist',
    'account',
]


REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}

DATABASES = {'default': service_database('auth')}


AUTH_USER_MODEL = 'account.User'

ROOT_URLCONF = 'auth_service.urls'
WSGI_APPLICATION = 'auth_service.wsgi.application'

SERVICE_NAME = 'auth'

SPECTACULAR_SETTINGS = {
    'TITLE': 'Auth Service',
    'DESCRIPTION': 'Registration, login, tiering and token issuance.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
