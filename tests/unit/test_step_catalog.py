from __future__ import annotations

from typing import Optional

import pytest

from agents.core import AgentConfig
from agents.core.agent_config_catalog import AgentConfigCatalog
from agents.core.pipeline_structure import PipelineStep
from agents.core.step_catalog import StepCatalog, StepExecutionType


class LLMStep(PipelineStep):
    @property
    def agent_config(self) -> AgentConfig:
        return AgentConfig(instructions="llm")


class BareLLMStep(PipelineStep):
    pass


class CodeStep(PipelineStep):
    def execute(self, payload: dict) -> dict:
        return {"ok": payload}


class NotAPipelineStep:
    pass


class FakePipeline:
    name = "fake"
    steps = {
        "llm": LLMStep,
        "code": CodeStep,
        "bare": BareLLMStep,
    }
    last_call: Optional[dict] = None

    def __init__(self, payload: dict, run_id: str):
        self.payload = payload
        self.run_id = run_id

    def execute_step(
        self,
        run_id,
        step_key,
        payload,
        order_index,
        parent_ids=None,
        agent_config=None,
    ):
        FakePipeline.last_call = {
            "run_id": run_id,
            "step_key": step_key,
            "payload": payload,
            "order_index": order_index,
            "parent_ids": parent_ids,
            "agent_config": agent_config,
        }
        return {"ran": True}


class MissingKeyPipeline:
    name = "missing"
    steps = {}


def test_register_rejects_duplicate_step_key() -> None:
    StepCatalog.register_step("llm", "fake", LLMStep, StepExecutionType.LLM)

    with pytest.raises(ValueError, match="Duplicate step key 'llm'."):
        StepCatalog.register_step("llm", "fake", LLMStep, StepExecutionType.LLM)


def test_validate_rejects_non_pipeline_step_class(monkeypatch) -> None:
    StepCatalog.register_step("bad", "fake", NotAPipelineStep, StepExecutionType.CODE)
    monkeypatch.setattr("agents.core.step_catalog.PipelineRegistry.get", lambda _name: FakePipeline)

    with pytest.raises(TypeError, match="must inherit PipelineStep"):
        StepCatalog.validate_registry()


def test_validate_rejects_missing_pipeline_mapping(monkeypatch) -> None:
    StepCatalog.register_step("llm", "missing", LLMStep, StepExecutionType.LLM)
    monkeypatch.setattr("agents.core.step_catalog.PipelineRegistry.get", lambda _name: MissingKeyPipeline)

    with pytest.raises(ValueError, match="missing from pipeline"):
        StepCatalog.validate_registry()


def test_validate_rejects_llm_without_config(monkeypatch) -> None:
    StepCatalog.register_step("bare", "fake", BareLLMStep, StepExecutionType.LLM)
    monkeypatch.setattr("agents.core.step_catalog.PipelineRegistry.get", lambda _name: FakePipeline)

    with pytest.raises(ValueError, match="requires agent_config_key or agent_config property"):
        StepCatalog.validate_registry()


def test_execute_step_rejects_pipeline_mismatch(monkeypatch) -> None:
    StepCatalog.register_step("llm", "fake", LLMStep, StepExecutionType.LLM)
    monkeypatch.setattr("agents.core.step_catalog.PipelineRegistry.get", lambda _name: FakePipeline)

    with pytest.raises(ValueError, match="belongs to 'fake', not 'other'"):
        StepCatalog.execute_step(
            run_id="run-1",
            pipeline_name="other",
            step_key="llm",
            order_index=1,
            payload={"a": 1},
        )


def test_execute_step_resolves_agent_config_from_catalog(monkeypatch) -> None:
    AgentConfigCatalog.register_agent_config("cfg", lambda: AgentConfig(instructions="from catalog"))
    StepCatalog.register_step(
        "llm",
        "fake",
        LLMStep,
        StepExecutionType.LLM,
        agent_config_key="cfg",
    )
    monkeypatch.setattr("agents.core.step_catalog.PipelineRegistry.get", lambda _name: FakePipeline)

    result = StepCatalog.execute_step(
        run_id="run-2",
        pipeline_name="fake",
        step_key="llm",
        order_index=5,
        payload={"x": 1},
    )

    assert result == {"ran": True}
    assert isinstance(FakePipeline.last_call["agent_config"], AgentConfig)
    assert FakePipeline.last_call["step_key"] == "llm"


def test_execute_step_for_code_step_has_no_agent_config(monkeypatch) -> None:
    StepCatalog.register_step("code", "fake", CodeStep, StepExecutionType.CODE)
    monkeypatch.setattr("agents.core.step_catalog.PipelineRegistry.get", lambda _name: FakePipeline)

    result = StepCatalog.execute_step(
        run_id="run-3",
        pipeline_name="fake",
        step_key="code",
        order_index=2,
        payload={"payload": True},
    )

    assert result == {"ran": True}
    assert FakePipeline.last_call["agent_config"] is None


def test_get_step_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unknown step key 'missing'."):
        StepCatalog.get_step("missing")
