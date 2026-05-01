"""Feedback pipeline used by the demo project."""

from __future__ import annotations

import os
from typing import Optional

from agents.agent import AgentConfig
from agents.pipeline_structure import Pipeline, PipelineRegistry, PipelineStep
from agents.step_catalog import StepCatalog, StepExecutionType

PIPELINE_NAME = "feedback.pipeline"
CLEAN_STEP = "clean_text"
ANALYZE_STEP = "analyze"


class CleanFeedbackStep(PipelineStep):
    """Normalize raw feedback before sending it to the LLM step."""

    def execute(self, payload: dict) -> dict:
        raw_text = payload.get("text", "")
        cleaned_text = " ".join(str(raw_text).strip().split()).lower()
        return {
            "cleaned_text": cleaned_text,
            "original_text": raw_text,
        }


class AnalyzeFeedbackStep(PipelineStep):
    """Analyze cleaned feedback with a managed LLM agent."""

    @property
    def agent_config(self) -> Optional[AgentConfig]:
        return AgentConfig(
            instructions=(
                "You are a customer success AI. Read the customer feedback JSON. "
                "Return a JSON object with exactly these keys: sentiment, action_item, "
                "summary. sentiment must be one of positive, negative, or neutral. "
                "action_item and summary must be concise strings."
            ),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            result_type=dict,
        )


class FeedbackPipeline(Pipeline):
    name = PIPELINE_NAME
    steps = {
        CLEAN_STEP: CleanFeedbackStep,
        ANALYZE_STEP: AnalyzeFeedbackStep,
    }


def register_feedback_pipeline() -> None:
    """Register the demo pipeline and its steps once per process."""
    try:
        PipelineRegistry.get(PIPELINE_NAME)
    except ValueError:
        PipelineRegistry.register(FeedbackPipeline)

    existing_keys = set(StepCatalog.list_step_keys())
    if CLEAN_STEP not in existing_keys:
        StepCatalog.register_step(
            key=CLEAN_STEP,
            pipeline_name=PIPELINE_NAME,
            step_class=CleanFeedbackStep,
            execution_type=StepExecutionType.CODE,
        )

    if ANALYZE_STEP not in existing_keys:
        StepCatalog.register_step(
            key=ANALYZE_STEP,
            pipeline_name=PIPELINE_NAME,
            step_class=AnalyzeFeedbackStep,
            execution_type=StepExecutionType.LLM,
        )
