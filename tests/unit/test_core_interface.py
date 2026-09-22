from __future__ import annotations

from agents.core import (
    AgentConfig,
    Step,
    StepExecutionType,
    ToolSet,
    Workflow,
    register_step,
    register_toolset,
    register_workflow,
    tool,
)
from agents.core.step_catalog import StepCatalog
from agents.core.tools import default_registry
from agents.core.workflow import WorkflowRegistry
from agents.runner import create_workflow_run
from pydantic import BaseModel
import pytest


class Input(BaseModel):
    value: str


class Output(BaseModel):
    value: str


class DemoTools(ToolSet):
    name = "core_interface_demo"

    @tool(input_model=Input, output_model=Output)
    def echo(self, input: Input) -> Output:
        return Output(value=input.value)


class DemoStep(Step):
    def execute(self, payload: dict) -> dict:
        return payload


class DemoWorkflow(Workflow):
    name = "core.interface.demo"
    steps = {"echo": DemoStep}


def test_core_registers_author_definitions(monkeypatch) -> None:
    registered_toolsets: list[tuple[type[ToolSet], str, bool]] = []

    def capture_toolset(toolset_cls, *, module, expose_mcp):
        registered_toolsets.append((toolset_cls, module, expose_mcp))

    monkeypatch.setattr(default_registry, "register_toolset", capture_toolset)

    register_toolset(DemoTools, module="demo", expose_mcp=True)
    register_workflow(DemoWorkflow)
    register_step(
        key="echo",
        workflow_name=DemoWorkflow.name,
        step_class=DemoStep,
        execution_type=StepExecutionType.CODE,
    )

    assert registered_toolsets == [(DemoTools, "demo", True)]
    assert WorkflowRegistry.get(DemoWorkflow.name) is DemoWorkflow
    assert StepCatalog.get_step("echo").step_class is DemoStep


def test_agent_config_is_a_definition_primitive() -> None:
    config = AgentConfig(instructions="Return the value.", toolsets=[DemoTools.name])

    assert config.toolsets == [DemoTools.name]


def test_runner_rejects_an_unregistered_workflow() -> None:
    with pytest.raises(ValueError, match="not found in registry"):
        create_workflow_run("missing.workflow", {})
