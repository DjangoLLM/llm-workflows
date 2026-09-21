from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from agents.core.agent import AgentConfig
from agents.core.agent_config_catalog import AgentConfigCatalog
from agents.core.pipeline_structure import Pipeline, PipelineRegistry, PipelineStep
from agents.core.step_catalog import StepCatalog, StepExecutionType
from agents.core.temporal.activities import execute_pipeline_step_activity
from agents.models import AgentRunStatus, PipelineStep as PipelineStepModel, PipelineStatus


class _Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    score: int


class _ActivityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    evidence: _Evidence
    tags: list[str]


class _TypedCodexStep(PipelineStep):
    pass


class _TypedCodexPipeline(Pipeline):
    name = "tests.typed-codex-activity"
    steps = {"infer": _TypedCodexStep}


def _install_fake_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    executable = tmp_path / "codex"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

args = sys.argv[1:]
schema_path = pathlib.Path(args[args.index("--output-schema") + 1])
final_path = pathlib.Path(args[args.index("--output-last-message") + 1])
pathlib.Path(os.environ["CODEX_ACTIVITY_CAPTURE"]).write_text(json.dumps({
    "schema": json.loads(schema_path.read_text()),
    "stdin": sys.stdin.read(),
}))
final_path.write_text(json.dumps({
    "summary": "typed activity result",
    "evidence": {"source": "fake-cli", "score": 9},
    "tags": ["managed", "temporal"],
}))
print('{"type":"turn.completed"}')
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)

    capture_path = tmp_path / "activity-capture.json"
    monkeypatch.setenv("CODEX_ACTIVITY_CAPTURE", str(capture_path))
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    return capture_path


@pytest.mark.django_db
def test_codex_pipeline_activity_returns_and_persists_structured_dict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_path = _install_fake_codex(tmp_path, monkeypatch)
    config = AgentConfig(
        instructions="Return a typed inference result.",
        execution_backend="codex_cli",
        result_type=_ActivityResult,
        extra_kwargs={"codex_working_dir": tmp_path},
    )
    AgentConfigCatalog.register_agent_config("tests.typed-codex", lambda: config)
    PipelineRegistry.register(_TypedCodexPipeline)
    StepCatalog.register_step(
        "infer",
        _TypedCodexPipeline.name,
        _TypedCodexStep,
        StepExecutionType.LLM,
        agent_config_key="tests.typed-codex",
    )
    StepCatalog.validate_registry()
    run_id = _TypedCodexPipeline.create_run({"question": "What happened?"})

    result = execute_pipeline_step_activity(
        run_id=run_id,
        pipeline_name=_TypedCodexPipeline.name,
        step_key="infer",
        order_index=0,
        payload={"question": "What happened?"},
    )

    expected = {
        "summary": "typed activity result",
        "evidence": {"source": "fake-cli", "score": 9},
        "tags": ["managed", "temporal"],
    }
    assert type(result) is dict
    assert result == expected
    assert config.result_type is _ActivityResult

    step = PipelineStepModel.objects.select_related("agent_run").get(
        run_id=run_id,
        step_name="infer",
    )
    assert step.status == PipelineStatus.SUCCEEDED
    assert step.output_payload == expected
    assert step.agent_run is not None
    assert step.agent_run.status == AgentRunStatus.SUCCEEDED
    assert step.agent_run.output == expected
    assert step.agent_run.agent_label == "infer"

    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    assert capture["schema"]["properties"]["evidence"]["$ref"] == "#/$defs/_Evidence"
    assert set(capture["schema"]["required"]) == {"summary", "evidence", "tags"}
    assert '"question": "What happened?"' in capture["stdin"]
