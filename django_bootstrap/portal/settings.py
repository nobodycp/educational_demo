"""
Minimal Django settings for the optional Nginx /d/ sub-site.
Override via environment (Docker).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "change-me-in-production-min-50-chars-xxxxxxxx")
DEBUG = (os.environ.get("DJANGO_DEBUG", "0").lower() in ("1", "true", "yes"))

raw_hosts = (os.environ.get("DJANGO_ALLOWED_HOSTS") or "*").strip()
if raw_hosts == "*":
    ALLOWED_HOSTS: list[str] = ["*"]
else:
    ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "portal.urls"
WSGI_APPLICATION = "portal.wsgi.application"

# Optional Postgres in Docker (Django system tables; no heavy app needed)
_postgres_host = (os.environ.get("POSTGRES_HOST") or "").strip()
_db_engine = (os.environ.get("DJANGO_DB_ENGINE") or ("postgres" if _postgres_host else "sqlite3")).lower()
if _postgres_host or _db_engine == "postgres" or "postgresql" in _db_engine:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "lab"),
            "USER": os.environ.get("POSTGRES_USER", "lab"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "postgres"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = (os.environ.get("DJANGO_STATIC_URL") or "/d/static/").rstrip("/") + "/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
