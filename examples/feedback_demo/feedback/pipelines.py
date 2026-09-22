"""Feedback pipeline used by the demo project."""

from __future__ import annotations

import os
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from agents.inferences.agents import AgentDefinition
from agents.steps import Step
from agents.workflows import Workflow
from agents.catalog.step_catalog import StepExecutionType, register_step
from agents.catalog.workflow_catalog import register_workflow
from agents.catalog.step_catalog import StepCatalog
from agents.runner.tools import default_registry
from agents.catalog.workflow_catalog import WorkflowRegistry

PIPELINE_NAME = "feedback.pipeline"
CLEAN_STEP = "clean_text"
ECHO_STEP = "echo_tool"
ANALYZE_STEP = "analyze"


class CleanFeedbackStep(Step):
    """Normalize raw feedback before sending it to the LLM step."""

    def execute(self, payload: dict) -> dict:
        raw_text = payload.get("text", "")
        cleaned_text = " ".join(str(raw_text).strip().split()).lower()
        return {
            "cleaned_text": cleaned_text,
            "original_text": raw_text,
        }


class EchoToolStep(Step):
    """Invoke the echo tool from default_registry to demonstrate the tool call path."""

    def execute(self, payload: dict) -> dict:
        text = payload.get("cleaned_text", payload.get("text", ""))
        result = default_registry.run("echo", {"text": text})
        return {**payload, "tool_result": result.model_dump()}


class FeedbackAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentiment: Literal["positive", "negative", "neutral"]
    action_item: str
    summary: str


class AnalyzeFeedbackStep(Step):
    """Analyze cleaned feedback with a managed LLM agent."""

    @property
    def agent_definition(self) -> Optional[AgentDefinition]:
        return AgentDefinition(
            instructions=(
                "You are a customer success AI. Read the customer feedback JSON. "
                "Return a JSON object with exactly these keys: sentiment, action_item, "
                "summary. sentiment must be one of positive, negative, or neutral. "
                "action_item and summary must be concise strings."
            ),
            model=os.environ.get("CODEX_MODEL") or None,
            result_type=FeedbackAnalysis,
        )


class FeedbackWorkflow(Workflow):
    name = PIPELINE_NAME
    steps = {
        CLEAN_STEP: CleanFeedbackStep,
        ECHO_STEP: EchoToolStep,
        ANALYZE_STEP: AnalyzeFeedbackStep,
    }


def register_feedback_pipeline() -> None:
    """Register the demo pipeline and its steps once per process."""
    try:
        WorkflowRegistry.get(PIPELINE_NAME)
    except ValueError:
        register_workflow(FeedbackWorkflow)

    existing_keys = set(StepCatalog.list_step_keys())
    if CLEAN_STEP not in existing_keys:
        register_step(
            key=CLEAN_STEP,
            workflow_name=PIPELINE_NAME,
            step_class=CleanFeedbackStep,
            execution_type=StepExecutionType.CODE,
        )

    if ECHO_STEP not in existing_keys:
        register_step(
            key=ECHO_STEP,
            workflow_name=PIPELINE_NAME,
            step_class=EchoToolStep,
            execution_type=StepExecutionType.CODE,
        )

    if ANALYZE_STEP not in existing_keys:
        register_step(
            key=ANALYZE_STEP,
            workflow_name=PIPELINE_NAME,
            step_class=AnalyzeFeedbackStep,
            execution_type=StepExecutionType.LLM,
        )
