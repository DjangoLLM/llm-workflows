from __future__ import annotations

import asyncio
import enum
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pytest

from agents.inferences.agents import AgentDefinition
from agents.runner import Agent
from agents.runner.json_safe import json_safe as _json_safe_value


def test_agent_runs_without_api_provider_libraries() -> None:
    script = '''
import importlib.abc
import sys

class BlockProviders(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"pydantic_ai", "openai", "anthropic"}:
            raise AssertionError("Removed provider dependency imported: " + fullname)

sys.meta_path.insert(0, BlockProviders())
import django
django.setup()
from types import SimpleNamespace
from unittest.mock import patch
from agents.inferences.agents import AgentDefinition
from agents.runner import Agent

with patch("agents.adapters.inference.codex.CodexRunner.from_definition") as factory:
    factory.return_value.run_sync.return_value = SimpleNamespace(output={"ok": True})
    assert Agent(AgentDefinition(instructions="test")).run_sync({}).output == {"ok": True}
'''
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    assert result.returncode == 0, result.stderr


class DemoEnum(enum.Enum):
    VALUE = "value"


@dataclass
class DemoData:
    value: int


def test_agent_requires_definition_or_default(settings) -> None:
    settings.DEFAULT_AGENT_DEFINITION = None

    with pytest.raises(ValueError, match="DEFAULT_AGENT_DEFINITION"):
        Agent()


def test_agent_builds_codex_definition_from_kwargs_by_default() -> None:
    with mock.patch("agents.adapters.inference.codex.CodexRunner.from_definition") as factory:
        Agent(instructions="from kwargs", result_type=DemoData)

    assert factory.call_args.args[0].execution_backend == "codex_cli"
    assert factory.call_args.args[0].instructions == "from kwargs"


def test_agent_builds_codex_backend_from_kwargs() -> None:
    runner = mock.Mock()
    with mock.patch(
        "agents.adapters.inference.codex.CodexRunner.from_definition", return_value=runner
    ) as from_definition:
        agent = Agent(
            instructions="typed",
            execution_backend="codex_cli",
            result_type=DemoData,
        )

    assert agent._runner is runner
    assert from_definition.call_args.args[0].execution_backend == "codex_cli"


def test_agent_uses_configured_codex_default(settings) -> None:
    configured = AgentDefinition(
        instructions="typed",
        execution_backend="codex_cli",
        result_type=DemoData,
    )
    settings.DEFAULT_AGENT_DEFINITION = configured
    runner = mock.Mock()

    with mock.patch(
        "agents.adapters.inference.codex.CodexRunner.from_definition", return_value=runner
    ):
        agent = Agent()

    assert agent.definition is configured
    assert agent._runner is runner


def test_agent_delegates_sync_and_async_to_adapter() -> None:
    result = SimpleNamespace(output={"ok": True})
    runner = mock.Mock()
    runner.run_sync.return_value = result
    runner.run = mock.AsyncMock(return_value=result)
    with mock.patch("agents.adapters.inference.codex.CodexRunner.from_definition", return_value=runner):
        agent = Agent(definition=AgentDefinition(instructions="x"))

    payload = {"value": 1}
    assert agent.run_sync(payload) is result
    assert asyncio.run(agent.run(payload)) is result
    runner.run_sync.assert_called_once_with(payload)
    runner.run.assert_awaited_once_with(payload)


def test_agent_definition_default_execution_backend() -> None:
    definition = AgentDefinition(instructions="test")
    assert definition.execution_backend == "codex_cli"


@pytest.mark.parametrize("backend", ["pydantic_ai", "jev", "pi_worker", "invalid"])
def test_agent_definition_rejects_unsupported_backend(backend: str) -> None:
    with pytest.raises(ValueError, match="execution_backend"):
        AgentDefinition(instructions="test", execution_backend=backend)


def test_json_safe_value_normalizes_nested_values() -> None:
    value = _json_safe_value(
        {
            "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "at": datetime(2026, 5, 1, 12, 0, 0),
            "enum": DemoEnum.VALUE,
            "data": DemoData(value=3),
            "items": (DemoData(value=4),),
        }
    )

    assert value == {
        "id": "12345678-1234-5678-1234-567812345678",
        "at": "2026-05-01T12:00:00",
        "enum": "value",
        "data": {"value": 3},
        "items": [{"value": 4}],
    }
