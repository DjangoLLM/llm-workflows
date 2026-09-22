from __future__ import annotations

from typing import Optional

import pytest

from agents.inferences.agents import AgentDefinition
from agents.catalog.agent_definition_catalog import AgentDefinitionCatalog
from agents.runner.pipeline_structure import PipelineStep
from agents.runner.step_dispatch import StepDispatcher
from agents.catalog.step_catalog import StepCatalog, StepExecutionType


class LLMStep(PipelineStep):
    @property
    def agent_definition(self) -> AgentDefinition:
        return AgentDefinition(instructions="llm")


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
        agent_definition=None,
    ):
        FakePipeline.last_call = {
            "run_id": run_id,
            "step_key": step_key,
            "payload": payload,
            "order_index": order_index,
            "parent_ids": parent_ids,
            "agent_definition": agent_definition,
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
    monkeypatch.setattr("agents.catalog.step_catalog.WorkflowRegistry.get", lambda _name: FakePipeline)

    with pytest.raises(TypeError, match="must inherit Step"):
        StepCatalog.validate_registry()


def test_validate_rejects_missing_pipeline_mapping(monkeypatch) -> None:
    StepCatalog.register_step("llm", "missing", LLMStep, StepExecutionType.LLM)
    monkeypatch.setattr("agents.catalog.step_catalog.WorkflowRegistry.get", lambda _name: MissingKeyPipeline)

    with pytest.raises(ValueError, match="missing from pipeline"):
        StepCatalog.validate_registry()


def test_validate_rejects_llm_without_config(monkeypatch) -> None:
    StepCatalog.register_step("bare", "fake", BareLLMStep, StepExecutionType.LLM)
    monkeypatch.setattr("agents.catalog.step_catalog.WorkflowRegistry.get", lambda _name: FakePipeline)

    with pytest.raises(ValueError, match="requires agent_definition_key or agent_definition property"):
        StepCatalog.validate_registry()


def test_execute_step_rejects_pipeline_mismatch(monkeypatch) -> None:
    StepCatalog.register_step("llm", "fake", LLMStep, StepExecutionType.LLM)
    monkeypatch.setattr("agents.catalog.step_catalog.WorkflowRegistry.get", lambda _name: FakePipeline)

    with pytest.raises(ValueError, match="belongs to 'fake', not 'other'"):
        StepDispatcher.execute_step(
            run_id="run-1",
            pipeline_name="other",
            step_key="llm",
            order_index=1,
            payload={"a": 1},
        )


def test_execute_step_resolves_agent_definition_from_catalog(monkeypatch) -> None:
    AgentDefinitionCatalog.register_agent_definition("cfg", lambda: AgentDefinition(instructions="from catalog"))
    StepCatalog.register_step(
        "llm",
        "fake",
        LLMStep,
        StepExecutionType.LLM,
        agent_definition_key="cfg",
    )
    monkeypatch.setattr("agents.catalog.step_catalog.WorkflowRegistry.get", lambda _name: FakePipeline)

    result = StepDispatcher.execute_step(
        run_id="run-2",
        pipeline_name="fake",
        step_key="llm",
        order_index=5,
        payload={"x": 1},
    )

    assert result == {"ran": True}
    assert isinstance(FakePipeline.last_call["agent_definition"], AgentDefinition)
    assert FakePipeline.last_call["step_key"] == "llm"


def test_execute_step_for_code_step_has_no_agent_definition(monkeypatch) -> None:
    StepCatalog.register_step("code", "fake", CodeStep, StepExecutionType.CODE)
    monkeypatch.setattr("agents.catalog.step_catalog.WorkflowRegistry.get", lambda _name: FakePipeline)

    result = StepDispatcher.execute_step(
        run_id="run-3",
        pipeline_name="fake",
        step_key="code",
        order_index=2,
        payload={"payload": True},
    )

    assert result == {"ran": True}
    assert FakePipeline.last_call["agent_definition"] is None


def test_get_step_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unknown step key 'missing'."):
        StepCatalog.get_step("missing")
