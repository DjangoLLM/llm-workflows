from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from typing import Any, Callable

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from temporalio.activity import _Definition as ActivityDefinition
from temporalio.workflow import _Definition as WorkflowDefinition

CORE_TEMPORAL_PLUGIN_MODULE = "agents.adapters.temporal.plugins.core"
TEMPORAL_PLUGIN_ENTRYPOINT = "get_temporal_worker_plugin"
TEMPORAL_PLUGIN_MODULES_SETTING = "AGENTS_TEMPORAL_PLUGIN_MODULES"


@dataclass(frozen=True)
class TemporalActivityRegistration:
    activity_name: str
    activity_callable: Callable[..., Any]


@dataclass(frozen=True)
class TemporalWorkerPlugin:
    plugin_slug: str
    workflows: list[type]
    activities: list[TemporalActivityRegistration]


@dataclass(frozen=True)
class TemporalWorkerComposition:
    plugin_modules: list[str]
    plugin_slugs: list[str]
    workflow_names: list[str]
    workflows: list[type]
    activity_names: list[str]
    activities: list[Callable[..., Any]]


def _get_configured_plugin_modules() -> list[str]:
    configured_modules = getattr(settings, TEMPORAL_PLUGIN_MODULES_SETTING, [])
    if configured_modules is None:
        return []
    if not isinstance(configured_modules, (list, tuple)):
        raise ImproperlyConfigured(
            f"{TEMPORAL_PLUGIN_MODULES_SETTING} must be a list or tuple of module paths."
        )

    normalized_modules: list[str] = []
    for module_path in configured_modules:
        if not isinstance(module_path, str) or not module_path.strip():
            raise ImproperlyConfigured(
                f"{TEMPORAL_PLUGIN_MODULES_SETTING} entries must be non-empty module path strings."
            )
        normalized_modules.append(module_path.strip())
    return normalized_modules


def _build_plugin_module_paths() -> list[str]:
    ordered_paths = [CORE_TEMPORAL_PLUGIN_MODULE, *_get_configured_plugin_modules()]
    seen_paths: set[str] = set()
    deduped_paths: list[str] = []
    for module_path in ordered_paths:
        if module_path in seen_paths:
            raise ImproperlyConfigured(
                f"Duplicate Temporal plugin module '{module_path}' in worker configuration."
            )
        seen_paths.add(module_path)
        deduped_paths.append(module_path)
    return deduped_paths


def _load_plugin(module_path: str) -> TemporalWorkerPlugin:
    try:
        plugin_module = importlib.import_module(module_path)
    except Exception as exc:  # noqa: BLE001
        raise ImproperlyConfigured(
            f"Failed to import Temporal plugin module '{module_path}'."
        ) from exc

    entrypoint = getattr(plugin_module, TEMPORAL_PLUGIN_ENTRYPOINT, None)
    if entrypoint is None or not callable(entrypoint):
        raise ImproperlyConfigured(
            f"Temporal plugin module '{module_path}' must expose callable "
            f"'{TEMPORAL_PLUGIN_ENTRYPOINT}()'."
        )

    try:
        plugin = entrypoint()
    except Exception as exc:  # noqa: BLE001
        raise ImproperlyConfigured(
            f"Temporal plugin module '{module_path}' failed while building plugin payload."
        ) from exc

    if not isinstance(plugin, TemporalWorkerPlugin):
        raise ImproperlyConfigured(
            f"Temporal plugin module '{module_path}' returned "
            f"{type(plugin).__name__}, expected TemporalWorkerPlugin."
        )
    return plugin


def _validate_plugin_shape(plugin: TemporalWorkerPlugin, module_path: str) -> None:
    if not isinstance(plugin.plugin_slug, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", plugin.plugin_slug):
        raise ImproperlyConfigured(
            f"Plugin '{module_path}' has invalid plugin_slug '{plugin.plugin_slug}'. "
            "Use lowercase slug format [a-z][a-z0-9_]*."
        )
    if not isinstance(plugin.workflows, (list, tuple)):
        raise ImproperlyConfigured(
            f"Plugin '{module_path}' has invalid workflows payload; expected list[type]."
        )
    if not isinstance(plugin.activities, (list, tuple)):
        raise ImproperlyConfigured(
            f"Plugin '{module_path}' has invalid activities payload; "
            "expected list[TemporalActivityRegistration]."
        )

    for registration in plugin.activities:
        if not isinstance(registration, TemporalActivityRegistration):
            raise ImproperlyConfigured(
                f"Plugin '{module_path}' contains invalid activity registration "
                f"'{type(registration).__name__}'."
            )


def _workflow_name(workflow_cls: type, module_path: str) -> str:
    try:
        return WorkflowDefinition.must_from_class(workflow_cls).name
    except Exception as exc:  # noqa: BLE001
        raise ImproperlyConfigured(
            f"Plugin '{module_path}' includes invalid workflow '{workflow_cls}'."
        ) from exc


def _activity_definition_name(activity_callable: Callable[..., Any], module_path: str) -> str:
    try:
        return ActivityDefinition.must_from_callable(activity_callable).name
    except Exception as exc:  # noqa: BLE001
        raise ImproperlyConfigured(
            f"Plugin '{module_path}' includes invalid activity callable '{activity_callable}'."
        ) from exc


def compose_temporal_worker(
    plugins: list[TemporalWorkerPlugin],
    plugin_modules: list[str],
) -> TemporalWorkerComposition:
    if len(plugins) != len(plugin_modules):
        raise ImproperlyConfigured("Plugin payload and module path counts do not match.")

    workflow_names: list[str] = []
    workflows: list[type] = []
    seen_workflow_names: set[str] = set()

    activity_names: list[str] = []
    activities: list[Callable[..., Any]] = []
    seen_activity_names: set[str] = set()

    for plugin, module_path in zip(plugins, plugin_modules):
        _validate_plugin_shape(plugin, module_path)

        for workflow_cls in plugin.workflows:
            workflow_name = _workflow_name(workflow_cls, module_path)
            if workflow_name in seen_workflow_names:
                raise ImproperlyConfigured(
                    f"Duplicate workflow name '{workflow_name}' found while loading "
                    f"Temporal plugins (latest from '{module_path}')."
                )
            seen_workflow_names.add(workflow_name)
            workflow_names.append(workflow_name)
            workflows.append(workflow_cls)

        expected_prefix = f"{plugin.plugin_slug}."
        for registration in plugin.activities:
            if not isinstance(registration.activity_name, str) or not registration.activity_name.strip():
                raise ImproperlyConfigured(
                    f"Plugin '{module_path}' has activity with empty 'activity_name'."
                )
            if not callable(registration.activity_callable):
                raise ImproperlyConfigured(
                    f"Plugin '{module_path}' activity '{registration.activity_name}' is not callable."
                )
            if not registration.activity_name.startswith(expected_prefix):
                raise ImproperlyConfigured(
                    f"Plugin '{module_path}' activity '{registration.activity_name}' must start "
                    f"with '{expected_prefix}'."
                )

            defined_name = _activity_definition_name(registration.activity_callable, module_path)
            if defined_name != registration.activity_name:
                raise ImproperlyConfigured(
                    f"Plugin '{module_path}' activity registration mismatch for "
                    f"'{registration.activity_name}': callable is decorated as '{defined_name}'."
                )

            if registration.activity_name in seen_activity_names:
                raise ImproperlyConfigured(
                    f"Duplicate activity name '{registration.activity_name}' found while "
                    f"loading Temporal plugins (latest from '{module_path}')."
                )

            seen_activity_names.add(registration.activity_name)
            activity_names.append(registration.activity_name)
            activities.append(registration.activity_callable)

    return TemporalWorkerComposition(
        plugin_modules=plugin_modules,
        plugin_slugs=[plugin.plugin_slug for plugin in plugins],
        workflow_names=workflow_names,
        workflows=workflows,
        activity_names=activity_names,
        activities=activities,
    )


def build_temporal_worker_composition() -> TemporalWorkerComposition:
    plugin_modules = _build_plugin_module_paths()
    plugins = [_load_plugin(module_path) for module_path in plugin_modules]
    return compose_temporal_worker(plugins=plugins, plugin_modules=plugin_modules)
