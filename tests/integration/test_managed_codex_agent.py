from __future__ import annotations

import json
import os
import threading
from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from agents import AgentRunStatus
from agents.inferences.agents import AgentDefinition
from agents.runner import ManagedAgent, agent_run_finished
from agents.adapters.inference.codex.schema import CodexSchemaError
from agents.handlers import agent_run_completed
from agents.models import AgentRun


class _Verdict(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"


class _Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[str]
    note: str | None


class _ManagedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: _Verdict
    score: int
    evidence: _Evidence


_VALID_RESPONSE = {
    "verdict": "accept",
    "score": 7,
    "evidence": {"sources": ["alpha", "beta"], "note": None},
}


def _install_fake_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: object = _VALID_RESPONSE,
    exit_code: int = 0,
) -> None:
    executable = tmp_path / "codex"
    executable.write_text(
        """#!/usr/bin/env python3
import os
import pathlib
import sys

args = sys.argv[1:]
sys.stdin.read()
final_path = pathlib.Path(args[args.index("--output-last-message") + 1])
if os.environ.get("FAKE_CODEX_RESPONSE") is not None:
    final_path.write_text(os.environ["FAKE_CODEX_RESPONSE"], encoding="utf-8")
print('{"type":"turn.completed"}')
print("fake stderr must not be persisted", file=sys.stderr)
raise SystemExit(int(os.environ.get("FAKE_CODEX_EXIT_CODE", "0")))
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    response_text = response if isinstance(response, str) else json.dumps(response)
    monkeypatch.setenv("FAKE_CODEX_RESPONSE", response_text)
    monkeypatch.setenv("FAKE_CODEX_EXIT_CODE", str(exit_code))
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")


def _config(tmp_path: Path) -> AgentDefinition:
    return AgentDefinition(
        instructions="Return the requested managed answer.",
        execution_backend="codex_cli",
        model="test-model",
        result_type=_ManagedAnswer,
        extra_kwargs={"codex_working_dir": tmp_path},
    )


@pytest.mark.django_db
def test_managed_codex_sync_persists_nested_json_and_completion_notifications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_codex(tmp_path, monkeypatch)
    completed: list[dict] = []
    finished: list[dict] = []

    def completed_receiver(sender, **kwargs):
        completed.append(kwargs)

    def finished_receiver(sender, **kwargs):
        finished.append(kwargs)

    agent_run_completed.connect(completed_receiver)
    agent_run_finished.connect(finished_receiver)
    try:
        managed = ManagedAgent(definition=_config(tmp_path), agent_label="codex-pipeline")
        output = managed.run_sync(
            {"request": "classify"},
            pipeline_name="review-pipeline",
            step_name="classify",
        )
    finally:
        agent_run_completed.disconnect(completed_receiver)
        agent_run_finished.disconnect(finished_receiver)

    run = AgentRun.objects.get(pk=managed.run_id)
    assert output == _VALID_RESPONSE
    assert run.output == _VALID_RESPONSE
    assert run.status == AgentRunStatus.SUCCEEDED
    assert run.agent_label == "codex-pipeline"
    assert run.started_at is not None
    assert run.ended_at is not None
    assert run.ended_at >= run.started_at
    assert run.error_message in (None, "")
    assert len(completed) == 1
    assert completed[0]["run_id"] == run.id
    assert completed[0]["agent_label"] == "codex-pipeline"
    assert completed[0]["status"] == AgentRunStatus.SUCCEEDED
    assert completed[0]["output"] == _VALID_RESPONSE
    assert completed[0]["error_message"] == run.error_message
    assert completed[0]["pipeline_name"] == "review-pipeline"
    assert completed[0]["step_name"] == "classify"
    assert completed[0]["input_payload"] == {"request": "classify"}
    assert finished[0]["run_id"] == run.id
    assert finished[0]["status"] == AgentRunStatus.SUCCEEDED
    assert finished[0]["output"] == _VALID_RESPONSE


@pytest.mark.django_db(transaction=True)
def test_managed_codex_background_run_reaches_succeeded_with_default_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_codex(tmp_path, monkeypatch)
    terminal = threading.Event()
    notifications: list[dict] = []

    def receiver(sender, **kwargs):
        notifications.append(kwargs)
        terminal.set()

    agent_run_completed.connect(receiver)
    try:
        managed = ManagedAgent(definition=_config(tmp_path))
        run_id = managed.run({"request": "background"})
        assert terminal.wait(5), "managed Codex run did not emit completion notification"
    finally:
        agent_run_completed.disconnect(receiver)

    run = AgentRun.objects.get(pk=run_id)
    assert run.status == AgentRunStatus.SUCCEEDED
    assert run.agent_label == "agent"
    assert run.output == _VALID_RESPONSE
    assert run.started_at is not None
    assert run.ended_at is not None
    assert notifications[0]["run_id"] == run.id
    assert notifications[0]["status"] == AgentRunStatus.SUCCEEDED
    assert notifications[0]["output"] == _VALID_RESPONSE


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("response", "exit_code", "expected_error"),
    [
        (_VALID_RESPONSE, 17, "Codex CLI exited unsuccessfully with status 17"),
        (
            {
                "verdict": "accept",
                "score": "not-an-integer",
                "evidence": {"sources": [], "note": None},
            },
            0,
            "Codex final response failed strict validation",
        ),
    ],
    ids=("cli-failure", "response-validation-failure"),
)
def test_managed_codex_failures_persist_terminal_state_and_notify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    response: object,
    exit_code: int,
    expected_error: str,
) -> None:
    _install_fake_codex(
        tmp_path,
        monkeypatch,
        response=response,
        exit_code=exit_code,
    )
    completed: list[dict] = []
    finished: list[dict] = []

    def completed_receiver(sender, **kwargs):
        completed.append(kwargs)

    def finished_receiver(sender, **kwargs):
        finished.append(kwargs)

    agent_run_completed.connect(completed_receiver)
    agent_run_finished.connect(finished_receiver)
    try:
        managed = ManagedAgent(definition=_config(tmp_path), agent_label="codex-failure")
        output = managed.run_sync({"secret": "must-not-leak"})
    finally:
        agent_run_completed.disconnect(completed_receiver)
        agent_run_finished.disconnect(finished_receiver)

    run = AgentRun.objects.get(pk=managed.run_id)
    assert output is None
    assert run.status == AgentRunStatus.FAILED
    assert run.output is None
    assert expected_error in (run.error_message or "")
    assert "must-not-leak" not in (run.error_message or "")
    assert "fake stderr" not in (run.error_message or "")
    assert run.started_at is not None
    assert run.ended_at is not None
    assert run.ended_at >= run.started_at
    assert completed[0]["run_id"] == run.id
    assert completed[0]["status"] == AgentRunStatus.FAILED
    assert completed[0]["output"] is None
    assert completed[0]["error_message"] == run.error_message
    assert finished[0]["run_id"] == run.id
    assert finished[0]["status"] == AgentRunStatus.FAILED
    assert finished[0]["output"] is None
    assert finished[0]["error_message"] == run.error_message


@pytest.mark.django_db
def test_managed_codex_configuration_failure_precedes_run_creation(
    tmp_path: Path,
) -> None:
    before = AgentRun.objects.count()
    definition = _config(tmp_path)
    definition.result_type = dict

    with pytest.raises(CodexSchemaError):
        ManagedAgent(definition=definition)

    assert AgentRun.objects.count() == before
