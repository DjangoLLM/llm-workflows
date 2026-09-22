from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any

import pytest
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from django.db import connection

import agents.core.agent_config_registrations as agent_config_registrations
import agents.core.step_registrations as step_registrations
from agents.core.agent_config_catalog import AgentConfigCatalog
from agents.core.pipeline_structure import PipelineRegistry
from agents.core.step_catalog import StepCatalog
from agents.runner.temporal import activities as temporal_activities


class InlineThread:
    """Thread stub that executes work immediately for deterministic tests."""

    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self) -> None:
        self.target(*self.args, **self.kwargs)


@dataclass
class ModelDumpResult:
    value: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return self.value


@pytest.fixture(scope="session", autouse=True)
def ensure_vector_extension(django_db_setup, django_db_blocker) -> None:
    """Enable pgvector extension in the active test database."""
    with django_db_blocker.unblock():
        if connection.vendor != "postgresql":
            return
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")


@pytest.fixture(autouse=True)
def reset_catalog_singletons() -> None:
    """Keep singleton registries isolated between tests."""
    step_snapshot = dict(StepCatalog._steps)
    config_snapshot = dict(AgentConfigCatalog._resolvers)
    pipeline_snapshot = dict(PipelineRegistry._pipelines)
    activity_snapshot = dict(temporal_activities._TRANSFORMED_STEP_ACTIVITIES)
    step_registered_snapshot = step_registrations._REGISTERED
    config_registered_snapshot = agent_config_registrations._REGISTERED

    StepCatalog._steps.clear()
    AgentConfigCatalog._resolvers.clear()
    PipelineRegistry._pipelines.clear()
    temporal_activities._TRANSFORMED_STEP_ACTIVITIES.clear()
    step_registrations._REGISTERED = False
    agent_config_registrations._REGISTERED = False

    yield

    StepCatalog._steps.clear()
    StepCatalog._steps.update(step_snapshot)

    AgentConfigCatalog._resolvers.clear()
    AgentConfigCatalog._resolvers.update(config_snapshot)

    PipelineRegistry._pipelines.clear()
    PipelineRegistry._pipelines.update(pipeline_snapshot)

    temporal_activities._TRANSFORMED_STEP_ACTIVITIES.clear()
    temporal_activities._TRANSFORMED_STEP_ACTIVITIES.update(activity_snapshot)

    step_registrations._REGISTERED = step_registered_snapshot
    agent_config_registrations._REGISTERED = config_registered_snapshot


@pytest.fixture
def inline_thread(monkeypatch):
    monkeypatch.setattr("agents.runner.agent.threading.Thread", InlineThread)
    return InlineThread


@pytest.fixture(autouse=True)
def fail_fast_live_prerequisites(request):
    if "codex_live" not in request.keywords:
        return

    missing: list[str] = []

    if shutil.which("codex") is None:
        missing.append("binary:codex")
    database = settings.DATABASES.get(DEFAULT_DB_ALIAS, {})
    if not database.get("ENGINE"):
        missing.append(f"database:{DEFAULT_DB_ALIAS}")

    if missing:
        pytest.fail(
            "Codex live test prerequisites missing: " + ", ".join(missing),
            pytrace=False,
        )
