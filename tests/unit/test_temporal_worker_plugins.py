from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured
from temporalio import activity, workflow

from agents.runner.temporal.worker_plugins import (
    TemporalActivityRegistration,
    TemporalWorkerPlugin,
    _build_plugin_module_paths,
    _get_configured_plugin_modules,
    _load_plugin,
    build_temporal_worker_composition,
    compose_temporal_worker,
)


@activity.defn(name="agents.core_activity")
def core_activity() -> dict:
    return {"ok": True}


@activity.defn(name="personal.extra_activity")
def extra_activity() -> dict:
    return {"ok": True}


@activity.defn(name="personal.mismatch_callable")
def mismatch_activity() -> dict:
    return {"ok": False}


@workflow.defn(name="personal.workflow")
class PersonalWorkflow:
    @workflow.run
    async def run(self) -> None:
        return None


@workflow.defn(name="shared.workflow")
class SharedWorkflowA:
    @workflow.run
    async def run(self) -> None:
        return None


@workflow.defn(name="shared.workflow")
class SharedWorkflowB:
    @workflow.run
    async def run(self) -> None:
        return None


def test_get_configured_plugin_modules_accepts_empty(settings) -> None:
    settings.AGENTS_TEMPORAL_PLUGIN_MODULES = None

    assert _get_configured_plugin_modules() == []


def test_get_configured_plugin_modules_rejects_non_sequence(settings) -> None:
    settings.AGENTS_TEMPORAL_PLUGIN_MODULES = "bad"

    with pytest.raises(ImproperlyConfigured, match="must be a list or tuple"):
        _get_configured_plugin_modules()


def test_get_configured_plugin_modules_rejects_empty_entry(settings) -> None:
    settings.AGENTS_TEMPORAL_PLUGIN_MODULES = [""]

    with pytest.raises(ImproperlyConfigured, match="non-empty module path strings"):
        _get_configured_plugin_modules()


def test_build_plugin_module_paths_rejects_duplicates(settings) -> None:
    settings.AGENTS_TEMPORAL_PLUGIN_MODULES = ["agents.runner.temporal.plugins.core"]

    with pytest.raises(ImproperlyConfigured, match="Duplicate Temporal plugin module"):
        _build_plugin_module_paths()


def test_load_plugin_rejects_missing_entrypoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "agents.runner.temporal.worker_plugins.importlib.import_module",
        lambda _module_path: object(),
    )

    with pytest.raises(ImproperlyConfigured, match="must expose callable"):
        _load_plugin("fake.module")


def test_load_plugin_rejects_wrong_return_type(monkeypatch) -> None:
    module = SimpleNamespace(get_temporal_worker_plugin=lambda: object())
    monkeypatch.setattr(
        "agents.runner.temporal.worker_plugins.importlib.import_module",
        lambda _module_path: module,
    )

    with pytest.raises(ImproperlyConfigured, match="expected TemporalWorkerPlugin"):
        _load_plugin("fake.module")


def test_compose_temporal_worker_success() -> None:
    plugin = TemporalWorkerPlugin(
        plugin_slug="personal",
        workflows=[PersonalWorkflow],
        activities=[
            TemporalActivityRegistration(
                activity_name="personal.extra_activity",
                activity_callable=extra_activity,
            )
        ],
    )

    composition = compose_temporal_worker([plugin], ["module.path"])

    assert composition.plugin_modules == ["module.path"]
    assert composition.plugin_slugs == ["personal"]
    assert composition.workflow_names == ["personal.workflow"]
    assert composition.activity_names == ["personal.extra_activity"]


def test_compose_temporal_worker_rejects_mismatched_counts() -> None:
    plugin = TemporalWorkerPlugin(plugin_slug="agents", workflows=[], activities=[])

    with pytest.raises(ImproperlyConfigured, match="counts do not match"):
        compose_temporal_worker([plugin], [])


def test_compose_temporal_worker_rejects_bad_activity_prefix() -> None:
    plugin = TemporalWorkerPlugin(
        plugin_slug="personal",
        workflows=[],
        activities=[
            TemporalActivityRegistration(
                activity_name="wrong.prefix",
                activity_callable=extra_activity,
            )
        ],
    )

    with pytest.raises(ImproperlyConfigured, match="must start with 'personal.'"):
        compose_temporal_worker([plugin], ["module.path"])


def test_compose_temporal_worker_rejects_activity_name_mismatch() -> None:
    plugin = TemporalWorkerPlugin(
        plugin_slug="personal",
        workflows=[],
        activities=[
            TemporalActivityRegistration(
                activity_name="personal.registered_name",
                activity_callable=mismatch_activity,
            )
        ],
    )

    with pytest.raises(ImproperlyConfigured, match="registration mismatch"):
        compose_temporal_worker([plugin], ["module.path"])


def test_compose_temporal_worker_rejects_duplicate_activity_name() -> None:
    plugin = TemporalWorkerPlugin(
        plugin_slug="agents",
        workflows=[],
        activities=[
            TemporalActivityRegistration("agents.core_activity", core_activity),
            TemporalActivityRegistration("agents.core_activity", core_activity),
        ],
    )

    with pytest.raises(ImproperlyConfigured, match="Duplicate activity name"):
        compose_temporal_worker([plugin], ["module.path"])


def test_compose_temporal_worker_rejects_duplicate_workflow_name() -> None:
    plugin_a = TemporalWorkerPlugin(plugin_slug="agents", workflows=[SharedWorkflowA], activities=[])
    plugin_b = TemporalWorkerPlugin(plugin_slug="personal", workflows=[SharedWorkflowB], activities=[])

    with pytest.raises(ImproperlyConfigured, match="Duplicate workflow name"):
        compose_temporal_worker([plugin_a, plugin_b], ["a.module", "b.module"])


def test_build_temporal_worker_composition_loads_core_and_custom(settings, monkeypatch) -> None:
    core_plugin = TemporalWorkerPlugin(
        plugin_slug="agents",
        workflows=[],
        activities=[
            TemporalActivityRegistration(
                activity_name="agents.core_activity",
                activity_callable=core_activity,
            )
        ],
    )
    custom_plugin = TemporalWorkerPlugin(
        plugin_slug="personal",
        workflows=[PersonalWorkflow],
        activities=[
            TemporalActivityRegistration(
                activity_name="personal.extra_activity",
                activity_callable=extra_activity,
            )
        ],
    )

    modules = {
        "agents.runner.temporal.plugins.core": SimpleNamespace(get_temporal_worker_plugin=lambda: core_plugin),
        "custom.plugin": SimpleNamespace(get_temporal_worker_plugin=lambda: custom_plugin),
    }

    settings.AGENTS_TEMPORAL_PLUGIN_MODULES = ["custom.plugin"]
    monkeypatch.setattr(
        "agents.runner.temporal.worker_plugins.importlib.import_module",
        lambda module_path: modules[module_path],
    )

    composition = build_temporal_worker_composition()

    assert composition.plugin_modules == ["agents.runner.temporal.plugins.core", "custom.plugin"]
    assert composition.plugin_slugs == ["agents", "personal"]
