"""Minimal Django settings for the focused Codex live acceptance test."""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

SECRET_KEY = "agents-codex-live-test"
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "agents",
]
MIDDLEWARE: list[str] = []
ROOT_URLCONF = "feedback_demo.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "examples" / "feedback_demo" / "feedback" / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

MIGRATION_MODULES = {
    "agents": None,
}

AGENTS_STEP_REGISTRARS: list[str] = []
AGENTS_TEMPORAL_PLUGIN_MODULES: list[str] = []

LOGGING_CONFIG = None
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
