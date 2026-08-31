"""Base settings every service builds on.

There is only one service in Module 5, so this file looks like overhead today.
It exists because the alternative is worse: Module 6 stands up two more
services, and anything that must agree across all of them — the database
conventions, the DRF defaults, the middleware order — has to live somewhere
that is not one particular service.

A service does ``from common.base_settings import *`` and then adds only what
is genuinely its own: its apps, its URLconf, its database name.
"""

from pathlib import Path

from decouple import config, Csv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-only-do-not-deploy-this-key')

# Read from the environment rather than hardcoded, so a deployment is not one
# forgotten edit away from serving tracebacks. Module 8 replaces this with a
# single PRODUCTION_MODE switch that DEBUG is derived from.
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,shortener', cast=Csv())

RUNNING_TESTS = 'test' in __import__('sys').argv


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'drf_spectacular',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Gunicorn serves no static files, so admin and the Swagger UI would come
    # back unstyled behind the gateway without this.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ---------------------------------------------------------------------------
# Database — one per service, each in its own Postgres container.
#
# A service owns its data outright: nothing else holds a connection to it, so
# there is no cross-service join to accidentally rely on and no shared
# `django_migrations` table for three services to race on. `manage.py migrate`
# with no arguments is correct again — the built-in Django migrations are
# applied once per database, by the one service that owns it.
#
# The cost is that a query spanning services becomes an API call, and that
# `docker compose up` runs N Postgres containers. That is the trade the
# database-per-service pattern makes, and it is the point of it.
#
# There is deliberately no DATABASES here: base settings cannot know which
# database is yours. Each service declares it:
#
#     DATABASES = {'default': service_database('shortener')}
#
# Environment variables still win, which is how compose points the service at
# its container and how a deployment injects real credentials.
# ---------------------------------------------------------------------------

def service_database(name):
    """Return a DATABASES['default'] entry for the service's own database.

    `name` is the fallback for local, non-container development, where there
    is no compose file setting DB_* per container. In a container every one of
    these is set explicitly, so the defaults never apply.
    """
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default=name),
        'USER': config('DB_USER', default=name),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=0, cast=int),
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = config('STATIC_ROOT', default=str(REPO_ROOT / 'staticfiles'))
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}
