from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict

from agents import AgentRunStatus
from agents.core.agent import Agent, AgentConfig, ManagedAgent
from agents.models import AgentRun


class _LiveDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: list[str]
    note: str | None


class _LiveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marker: Literal["codex-live-ok"]
    count: int
    details: _LiveDetails


_EXPECTED = _LiveResult(
    marker="codex-live-ok",
    count=7,
    details=_LiveDetails(values=["direct", "managed"], note=None),
)


def _config(working_dir: Path) -> AgentConfig:
    return AgentConfig(
        instructions=(
            "Return exactly the requested values. Set marker to codex-live-ok, "
            "count to 7, details.values to [direct, managed], and details.note to null."
        ),
        execution_backend="codex_cli",
        model=os.environ.get("CODEX_LIVE_MODEL"),
        result_type=_LiveResult,
        extra_kwargs={
            "codex_working_dir": working_dir,
            "codex_timeout_seconds": 180,
        },
    )


@pytest.mark.live
@pytest.mark.codex_live
@pytest.mark.django_db
def test_real_codex_typed_acceptance_across_direct_and_managed_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    working_dir = Path.cwd()

    async_result = asyncio.run(Agent(config=_config(working_dir)).run({"mode": "async"}))
    sync_result = Agent(config=_config(working_dir)).run_sync({"mode": "sync"})
    managed = ManagedAgent(config=_config(working_dir), agent_label="codex-live")
    managed_output = managed.run_sync({"mode": "managed"})

    assert type(async_result.output) is _LiveResult
    assert async_result.output == _EXPECTED
    assert type(sync_result.output) is _LiveResult
    assert sync_result.output == _EXPECTED
    assert managed_output == _EXPECTED.model_dump(mode="json")

    run = AgentRun.objects.get(pk=managed.run_id)
    assert run.status == AgentRunStatus.SUCCEEDED
    assert run.output == _EXPECTED.model_dump(mode="json")
    assert run.error_message in (None, "")
    assert not list(tmp_path.glob("freedom-agents-codex-*"))
