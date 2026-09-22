from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from agents.core import AgentConfig
from agents.core.pipeline_structure import Pipeline, PipelineStep


@dataclass
class DataclassOutput:
    message: str


class FakeAgentSuccess:
    def __init__(self, output: Any = None):
        self._output = output if output is not None else {"ok": True}

    def run_sync(self, payload: dict | None):
        return SimpleNamespace(output=self._output)


class FakeAgentFailure:
    def run_sync(self, payload: dict | None):
        raise RuntimeError("boom")


class FakeLLMStep(PipelineStep):
    @property
    def agent_config(self) -> AgentConfig:
        return AgentConfig(instructions="stub llm")


class FakeCodeStep(PipelineStep):
    def execute(self, payload: dict) -> dict:
        return {"processed": payload}


class FakePipeline(Pipeline):
    name = "fake_pipeline"
    steps = {
        "llm_step": FakeLLMStep,
        "code_step": FakeCodeStep,
    }
