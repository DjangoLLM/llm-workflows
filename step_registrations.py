"""
Centralized StepCatalog registration entrypoint.
"""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

_REGISTERED = False


def register_all_steps() -> None:
    """
    Register all known pipeline steps exactly once.

    :return: None.
    """
    global _REGISTERED
    if _REGISTERED:
        return

    registrar_paths = getattr(settings, "AGENTS_STEP_REGISTRARS", [])
    if registrar_paths is None:
        registrar_paths = []

    if not isinstance(registrar_paths, (list, tuple)):
        raise ImproperlyConfigured(
            "AGENTS_STEP_REGISTRARS must be a list or tuple of dotted paths."
        )

    for path in registrar_paths:
        if not isinstance(path, str) or not path.strip():
            raise ImproperlyConfigured(
                "AGENTS_STEP_REGISTRARS entries must be non-empty dotted paths."
            )
        registrar = import_string(path.strip())
        if not callable(registrar):
            raise ImproperlyConfigured(
                f"AGENTS_STEP_REGISTRARS entry '{path}' is not callable."
            )
        casted_registrar: Callable[[], None] = registrar
        casted_registrar()

    _REGISTERED = True
