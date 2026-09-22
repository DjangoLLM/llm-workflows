"""Managed bounded-choice execution helpers.

A primitive beside ``ManagedAgent`` and ``PipelineStep``. It needs no ``PipelineRun``; the
decision is ledgered as an ``AgentRun`` through ``ManagedAgent``. Workflows call it through
``agents.jev_if_activity`` and branch on ``result``. Jev supplies the judgement, Temporal owns
the branch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from types import SimpleNamespace

from agents.core.inference.runner import InferenceRunner

from agents.runner.agent import ManagedAgent
from agents.adapters.inference.jev import JevRunner

HEAD = "condition"
CRITERIA = {"true": "The condition holds for this state.", "false": "The condition does not hold."}


def collapse(output: dict) -> dict:
    """Turn Jev's validated choice for the single head into a bool with its confidence."""
    return {
        "result": output["choices"][HEAD] == "true",
        "confidence": output["confidence"][HEAD],
        "probabilities": output["probabilities"][HEAD],
    }


@dataclass(frozen=True, slots=True)
class JevIf:
    """``JevIf("The segment refers to a tracked task.").decide(state)["result"]``"""

    condition: str
    model: Optional[str] = None
    label: str = "jev_if"

    def __post_init__(self) -> None:
        if not self.condition:
            raise ValueError("JevIf requires a non-empty `condition`")

    @property
    def runner(self) -> InferenceRunner[SimpleNamespace]:
        adapter = JevRunner(
            instructions=self.condition,
            model=self.model,
            questions={HEAD: {"criteria": CRITERIA}},
        )
        return InferenceRunner(adapter)

    def decide(self, state: Any) -> dict:
        """Ask Jev once; return ``{"result": bool, "confidence": float, "probabilities": {...}}``."""
        from agents.models import AgentRun, AgentRunStatus

        managed = ManagedAgent(agent=self.runner, agent_label=self.label)
        output = managed.run_sync(input_payload=state, agent_label=self.label)
        run = AgentRun.objects.get(pk=managed.run_id)
        if run.status != AgentRunStatus.SUCCEEDED:
            raise RuntimeError(run.error_message or "JevIf decision failed")
        return collapse(output)
