from __future__ import annotations

import contextlib
import os
import shutil
import socket
from dataclasses import dataclass
from typing import Any

import pytest
from django.conf import settings
from django.db import connection

import agents.agent_config_registrations as agent_config_registrations
import agents.step_registrations as step_registrations
from agents.agent_config_catalog import AgentConfigCatalog
from agents.pipeline_structure import PipelineRegistry
from agents.step_catalog import StepCatalog
from agents.temporal import activities as temporal_activities


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
    monkeypatch.setattr("agents.agent.threading.Thread", InlineThread)
    return InlineThread


def _parse_temporal_host_port(url: str) -> tuple[str, int]:
    if "://" in url:
        url = url.split("://", 1)[1]
    host_port = url.split("/", 1)[0]
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        return host, int(port)
    return host_port, 7233


def _check_temporal_reachable(url: str) -> bool:
    host, port = _parse_temporal_host_port(url)
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(2)
        try:
            sock.connect((host, port))
        except OSError:
            return False
        return True


@pytest.fixture(autouse=True)
def fail_fast_live_prerequisites(request):
    if "live" not in request.keywords:
        return

    missing: list[str] = []

    required_binaries = ["codex", "gemini"]
    for binary in required_binaries:
        if shutil.which(binary) is None:
            missing.append(f"binary:{binary}")

    required_env = ["OPENAI_API_KEY", "GEMINI_API_KEY", "CODEX_API_KEY", "DATABASE_URL"]
    for key in required_env:
        if not os.environ.get(key):
            missing.append(f"env:{key}")

    temporal_url = getattr(settings, "TEMPORAL_SERVER_URL", "localhost:7233")
    if not _check_temporal_reachable(temporal_url):
        missing.append(f"temporal:{temporal_url}")

    if missing:
        pytest.fail(
            "Live test prerequisites missing: " + ", ".join(missing),
            pytrace=False,
        )
