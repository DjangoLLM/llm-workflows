from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured

import agents.step_registrations as step_registrations


def test_register_all_steps_rejects_non_sequence(settings) -> None:
    settings.AGENTS_STEP_REGISTRARS = "not-a-list"

    with pytest.raises(ImproperlyConfigured, match="must be a list or tuple"):
        step_registrations.register_all_steps()


def test_register_all_steps_rejects_empty_path(settings) -> None:
    settings.AGENTS_STEP_REGISTRARS = [""]

    with pytest.raises(ImproperlyConfigured, match="non-empty dotted paths"):
        step_registrations.register_all_steps()


def test_register_all_steps_rejects_non_callable_entry(settings, monkeypatch) -> None:
    settings.AGENTS_STEP_REGISTRARS = ["x.y.z"]
    monkeypatch.setattr("agents.step_registrations.import_string", lambda _path: object())

    with pytest.raises(ImproperlyConfigured, match="not callable"):
        step_registrations.register_all_steps()


def test_register_all_steps_is_idempotent(settings, monkeypatch) -> None:
    calls: list[str] = []

    def registrar() -> None:
        calls.append("called")

    settings.AGENTS_STEP_REGISTRARS = ["test.registrar"]
    monkeypatch.setattr("agents.step_registrations.import_string", lambda _path: registrar)

    step_registrations.register_all_steps()
    step_registrations.register_all_steps()

    assert calls == ["called"]
