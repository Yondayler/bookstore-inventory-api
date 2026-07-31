"""
Django settings for the Bookstore Inventory API.

Every environment-specific value is read from environment variables so the same
image can run locally (docker-compose) and in the cloud (Render + Supabase)
without code changes. See `.env.example` for the full list.
"""
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

from config.env import env_bool, env_csv, env_decimal_map, env_int, env_str

BASE_DIR = Path(__file__).resolve().parent.parent

# Local development convenience: load a .env file if it exists.
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env_str("SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_csv("ALLOWED_HOSTS", ["*"])
CSRF_TRUSTED_ORIGINS = env_csv("CSRF_TRUSTED_ORIGINS", [])

# Render exposes the public hostname of the service through this variable.
RENDER_EXTERNAL_HOSTNAME = env_str("RENDER_EXTERNAL_HOSTNAME", "")
if RENDER_EXTERNAL_HOSTNAME:
    if "*" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "books",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Production (Render) points DATABASE_URL at the managed Supabase Postgres.
# Without DATABASE_URL we fall back to SQLite so the test-suite and a bare
# `python manage.py runserver` work with zero setup.
DATABASE_URL = env_str("DATABASE_URL", "")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=env_int("DB_CONN_MAX_AGE", 0),
            ssl_require=env_bool("DB_SSL_REQUIRE", True),
        )
    }
    # Supabase is reached through PgBouncer (transaction pooling), which does
    # not support server-side cursors or long-lived prepared statements.
    if env_bool("DB_USE_PGBOUNCER", True):
        DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
        DATABASES["default"].setdefault("OPTIONS", {})
        DATABASES["default"]["OPTIONS"]["prepare_threshold"] = None
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# I18N / static files
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["core.permissions.WriteRequiresApiKey"],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": env_int("DEFAULT_PAGE_SIZE", 20),
    "EXCEPTION_HANDLER": "core.exception_handler.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    # Emit prices as JSON numbers (15.99) instead of strings ("15.99"), which
    # is the shape the specification asks for.
    "COERCE_DECIMAL_TO_STRING": False,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Bookstore Inventory API",
    "DESCRIPTION": (
        "Inventory management for a bookstore chain, with real-time price "
        "validation against USD exchange rates."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "core.schema.strip_trailing_slashes",
    ],
}

CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", True)

# ---------------------------------------------------------------------------
# Business rules / pricing
# ---------------------------------------------------------------------------
# Currency the stores sell in. Can be overridden per request.
DEFAULT_LOCAL_CURRENCY = env_str("DEFAULT_LOCAL_CURRENCY", "EUR").upper()
# Profit margin applied on top of the local cost, in percent.
DEFAULT_MARGIN_PERCENTAGE = env_str("DEFAULT_MARGIN_PERCENTAGE", "40")
# Reject ISBNs that are well-formed but whose check digit is wrong.
ISBN_VALIDATE_CHECKSUM = env_bool("ISBN_VALIDATE_CHECKSUM", False)

# Optional write protection. While empty (the default) the API is fully open,
# which is what the evaluation environment needs. Set API_KEY to any value and
# POST/PUT/PATCH/DELETE start requiring the `X-API-Key` header; reads stay
# public either way.
API_KEY = env_str("API_KEY", "")

# ---------------------------------------------------------------------------
# Exchange rate integration
# ---------------------------------------------------------------------------
EXCHANGE_RATE_API_URL = env_str(
    "EXCHANGE_RATE_API_URL", "https://api.exchangerate-api.com/v4/latest/USD"
)
EXCHANGE_RATE_TIMEOUT = env_int("EXCHANGE_RATE_TIMEOUT", 5)
EXCHANGE_RATE_CACHE_TTL = env_int("EXCHANGE_RATE_CACHE_TTL", 600)  # seconds
# Used when the external API is unreachable (business rule: "si la API de
# cambio falla, usar tasa por defecto"). Snapshot taken from the provider on
# 2026-07-31; override with the FALLBACK_EXCHANGE_RATES environment variable to
# refresh them without touching the code.
FALLBACK_EXCHANGE_RATES = env_decimal_map(
    "FALLBACK_EXCHANGE_RATES",
    {
        "USD": "1",
        "EUR": "0.869",
        "GBP": "0.745",
        "MXN": "17.36",
        "COP": "3200.63",
        "ARS": "1490.84",
        "CLP": "933.41",
        "PEN": "3.39",
        "BRL": "5.09",
        "DOP": "58.03",
        "VES": "746.63",
    },
)

# gunicorn runs several worker processes, and an in-memory cache would be
# private to each one (so the same rate would be fetched once per worker).
# With a database available we use it as a shared cache instead; the table is
# created by the `books.0002_exchange_rate_cache_table` migration.
if DATABASE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "exchange_rate_cache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "bookstore-inventory-api",
        }
    }

# ---------------------------------------------------------------------------
# Security (only enforced outside DEBUG)
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": env_str("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
