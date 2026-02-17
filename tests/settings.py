"""Django settings for the agents test harness."""

from __future__ import annotations

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = "agents-test-secret-key"
DEBUG = False
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "agents",
]

MIDDLEWARE = []
ROOT_URLCONF = "agents.urls"
TEMPLATES: list[dict[str, object]] = []

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL must be set for agents tests. "
        "Use the Postgres harness script to run the suite."
    )

DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL, conn_max_age=0),
}

# The historical agents migrations reference legacy app dependencies that are out
# of scope for this harness. Use model-state table creation for isolated tests.
MIGRATION_MODULES = {
    "agents": None,
}

# Keep tests isolated from project-specific registration side effects.
AGENTS_STEP_REGISTRARS: list[str] = []
AGENTS_TEMPORAL_PLUGIN_MODULES: list[str] = []

TEMPORAL_SERVER_URL = os.environ.get("TEMPORAL_SERVER_URL", "localhost:7233")
TEMPORAL_TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "ai-pipeline-queue")

LOGGING_CONFIG = None
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
