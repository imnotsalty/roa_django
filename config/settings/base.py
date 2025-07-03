import os
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

import dj_database_url

# General
# ------------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
APPS_DIR = ROOT_DIR / "apps"
SECRET_KEY = "django-insecure-&3s#_f9e*6*f40&7im%$r4_t&#vl2urwp)k$%_+zw(gcd)l7^!"
DEBUG = True
ALLOWED_HOSTS = ["*"]

# CSRF
# ------------------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = ["http://localhost"]

# Environment Helpers
# ------------------------------------------------------------------------------
env = environ.Env()
env.read_env(str(ROOT_DIR / ".env"))

# Timezone & Localization
# ------------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = False

# Apps
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # "django_crontab", # Not needed for the AI agent API.
]

THIRD_PARTY_APPS = [
    # rest api
    "rest_framework",
    "rest_framework.authtoken",
    # Phone Number Field
    # "phonenumber_field", # Not used by the AI agent application.
    # For Static files
]

CUSTOM_APPS = [
    "apps.common",
    "apps.access",
    "apps.ai_designer",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + CUSTOM_APPS

# Middlewares
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Urls
# ------------------------------------------------------------------------------
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = True

# Templates
# ------------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [APPS_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# Media
# ------------------------------------------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = str(APPS_DIR / "media")

# Static
# ------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(ROOT_DIR, "staticfiles")
STATICFILES_DIRS = [str(APPS_DIR / "static")]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# Database
# ------------------------------------------------------------------------------
# NOTE: Django requires a database to run. You can simplify this to use SQLite
# for local development if you don't want to set up PostgreSQL.
# However, the AUTH_USER_MODEL depends on the 'access' app which may have
# migrations that require PostgreSQL. We will leave this as is.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

#DATABASES = {
#    # default database user and credentials | others are added on runtime
#    "default": {
#        "ENGINE": "django.db.backends.postgresql",
#        "NAME": env.str("DATABASE_DB", default=""),
#        "USER": env.str("DATABASE_USER", default=""),
#        "PASSWORD": env.str("DATABASE_PASSWORD", default=""),
#        "HOST": env.str("DATABASE_HOST", default=""),
#        "PORT": env.str("DATABASE_PORT", default=""),
#    }
#}

DATABASES = {
    'default': dj_database_url.config(default=os.environ.get('DATABASE_URL'))
}

# App Super Admin
# ------------------------------------------------------------------------------
AUTH_USER_MODEL = "access.User"
ADMIN_URL = env.str("DJANGO_ADMIN_URL", default="django-admin/")

# Authentication
# ------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Api & Rest Framework
# ------------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        # Switched to AllowAny for easier testing of the AI endpoint.
        # "rest_framework.permissions.IsAuthenticated",
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
}

# Not needed for the AI agent functionality.
# PASSWORD_RESET_TIMEOUT = 300

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [*default_headers]

# Celery
# ------------------------------------------------------------------------------
# Not needed for the AI agent as it operates synchronously via API calls.
# if USE_TZ:
#    CELERY_TIMEZONE = TIME_ZONE
# CELERY_BROKER_URL = env.str("CELERY_BROKER_URL")
# CELERY_RESULT_BACKEND = CELERY_BROKER_URL
# CELERY_ACCEPT_CONTENT = ["json"]
# CELERY_TASK_SERIALIZER = "json"
# CELERY_RESULT_SERIALIZER = "json"
# CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# App Configurations
# ------------------------------------------------------------------------------
APP_DATE_FORMAT = "%Y-%m-%d"
APP_TIME_FORMAT = "%H:%M:%S"
APP_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

# AWS S3 Storage Bucket
# -------------------------------------------------------------------------------
# Not needed as the AI agent does not store files directly using Django's storage backend.
# AWS_ACCESS_KEY_ID = env.str("AWS_ACCESS_KEY")
# AWS_SECRET_ACCESS_KEY = env.str("AWS_SECRET_KEY")
# AWS_STORAGE_BUCKET_NAME = env.str("AWS_BUCKET_NAME")

# AWS_QUERYSTRING_AUTH = False
# STORAGES = {
#     "staticfiles": {
#         "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
#     },
#     "default": {
#         "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
#     },
# }