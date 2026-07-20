from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or None


def required_env(name: str) -> str:
    value = env(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def resolve_path(raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


BASE_URL = required_env("BASE_URL").rstrip("/")
BASE_HOST = urlsplit(BASE_URL).hostname or "localhost"
ADMIN_HOST = env("ADMIN_HOST", f"admin.{BASE_HOST}") or f"admin.{BASE_HOST}"

SECRET_KEY = required_env("SECRET_KEY")
DEBUG = env("DJANGO_DEBUG") == "1"

extra_allowed_hosts = {
    host.strip()
    for host in (env("ALLOWED_HOSTS_EXTRA", "") or "").split(",")
    if host.strip()
}
ALLOWED_HOSTS = sorted(
    {"127.0.0.1", "localhost", BASE_HOST, ADMIN_HOST, *extra_allowed_hosts}
)

CSRF_TRUSTED_ORIGINS = sorted(
    {
        "http://127.0.0.1",
        "http://localhost",
        f"https://{BASE_HOST}",
        f"https://{ADMIN_HOST}",
    }
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "notepad",
    "redirects",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "personal_admin.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "personal_admin.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": resolve_path(required_env("DATABASE_PATH")),
        "OPTIONS": {"timeout": 5},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
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

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/admin/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/admin/notepad/files/"
MEDIA_ROOT = BASE_DIR / "data" / "uploads"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/admin/login/"

ADMIN_TITLE = env("TITLE", "Personal Admin") or "Personal Admin"
BOOTSTRAP_ADMIN_USERNAME = env("DJANGO_ADMIN_USERNAME")
BOOTSTRAP_ADMIN_PASSWORD = env("DJANGO_ADMIN_PASSWORD")
BOOTSTRAP_ADMIN_EMAIL = env("DJANGO_ADMIN_EMAIL", "") or ""
SITE_NAME = env("SITE_NAME", "Pujia") or "Pujia"
