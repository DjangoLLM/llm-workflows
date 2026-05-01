"""ASGI entrypoint for the feedback demo project."""

from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "feedback_demo.settings")

application = get_asgi_application()
