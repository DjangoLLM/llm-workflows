"""Agent execution and managed persistence."""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Any

import django
from agents.inferences.agents import AgentDefinition
from agents.core.inference.adapter import InferenceAdapter
from agents.core.inference.runner import InferenceRunner
from agents.runner.json_safe import json_safe
from agents.handlers import agent_run_completed
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Signal emitted when an agent run reaches a terminal state (SUCCEEDED or FAILED).
agent_run_finished = django.dispatch.Signal()


class Agent(InferenceRunner[Any]):
    """Execute an agent definition through Codex without persistence."""

    def __init__(self, definition: AgentDefinition | None = None, **kwargs):
        """
        Initialize the agent. If definition is not provided, it attempts to load
        DEFAULT_AGENT_DEFINITION from Django settings.

        Args:
            definition: An AgentDefinition instance.
            **kwargs: Individual definition fields if definition is not provided.
        """
        if definition is None:
            if not kwargs:
                definition = getattr(settings, 'DEFAULT_AGENT_DEFINITION', None)
                if definition is None:
                    raise ValueError('DEFAULT_AGENT_DEFINITION is not defined in Django settings.')
            else:
                definition = AgentDefinition(
                    instructions=kwargs.get('instructions', 'You are a helpful assistant.'),
                    execution_backend=kwargs.get('execution_backend', 'codex_cli'),
                    model=kwargs.get('model'),
                    settings=kwargs.get('settings'),
                    result_type=kwargs.get('result_type'),
                    tools=kwargs.get('tools'),
                    toolsets=kwargs.get('toolsets'),
                    extra_kwargs=kwargs.get('extra_kwargs'),
                )

        self.definition = definition
        if definition.execution_backend != "codex_cli":
            raise ValueError(f"Unsupported execution_backend: {definition.execution_backend!r}")
        from agents.adapters.inference.codex import CodexRunner

        super().__init__(CodexRunner.from_definition(definition))


class ManagedAgent:
    """Orchestrate persistence around an Agent or inference adapter."""

    def __init__(
        self,
        agent: InferenceRunner[Any] | InferenceAdapter[Any] | None = None,
        *,
        definition: AgentDefinition | None = None,
        agent_label: str | None = None,
    ):
        if agent is None:
            agent = Agent(definition)

        self._agent = agent
        label_source = agent._runner if isinstance(agent, Agent) else agent
        self._agent_label = agent_label or getattr(label_source, "name", None)
        self._started = False

        from agents.models import AgentRun, AgentRunStatus

        run = AgentRun.objects.create(
            agent_label=self._agent_label or "agent",
            status=AgentRunStatus.PENDING,
        )
        self.run_id = run.id

    def run(
        self,
        input_payload: Any | None = None,
        *,
        agent_label: str | None = None,
        pipeline_name: str | None = None,
        step_name: str | None = None,
        on_complete: Any | None = None,
    ) -> uuid.UUID:
        """Persist and trigger an async run for the underlying agent."""
        from agents.models import AgentRun, AgentRunStatus

        if self._started:
            raise RuntimeError("ManagedAgent.run called more than once for the same instance")

        run = AgentRun.objects.get(pk=self.run_id)
        run.agent_label = agent_label or self._agent_label or "agent"
        run.input = input_payload
        run.status = AgentRunStatus.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["agent_label", "input", "status", "started_at", "updated_at"])

        thread = threading.Thread(
            target=self._execute_run,
            args=(run.id, input_payload, pipeline_name, step_name, on_complete),
            daemon=False,
        )
        thread.start()
        self._started = True
        return run.id

    def run_sync(
        self,
        input_payload: Any | None = None,
        *,
        agent_label: str | None = None,
        pipeline_name: str | None = None,
        step_name: str | None = None,
        on_complete: Any | None = None,
    ) -> Any:
        """Persist and execute synchronously, returning the result output."""
        from agents.models import AgentRun, AgentRunStatus

        if self._started:
            raise RuntimeError("ManagedAgent.run_sync called more than once for the same instance")

        run = AgentRun.objects.get(pk=self.run_id)
        run.agent_label = agent_label or self._agent_label or "agent"
        run.input = input_payload
        run.status = AgentRunStatus.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["agent_label", "input", "status", "started_at", "updated_at"])

        self._execute_run(run.id, input_payload, pipeline_name, step_name, on_complete)
        run.refresh_from_db()
        self._started = True
        return run.output

    def _execute_run(
        self,
        run_id: uuid.UUID,
        input_payload: Any | None,
        pipeline_name: str | None,
        step_name: str | None,
        on_complete: Any | None,
    ) -> None:
        """Mutate run row through RUNNING -> terminal states."""
        from agents.models import AgentRun, AgentRunStatus

        run = AgentRun.objects.get(pk=run_id)
        run.status = AgentRunStatus.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at", "updated_at"])

        try:
            result = self._agent.run_sync(input_payload)
            output = getattr(result, "output", getattr(result, "data", None))
            output = json_safe(output)
            run.output = output
            run.status = AgentRunStatus.SUCCEEDED
        except Exception as exc:
            logger.exception("Agent run failed", extra={"run_id": run_id})
            run.error_message = str(exc)
            run.status = AgentRunStatus.FAILED
        finally:
            run.ended_at = timezone.now()
            run.save(
                update_fields=[
                    "status",
                    "output",
                    "error_message",
                    "ended_at",
                    "updated_at",
                ]
            )

            payload = {
                "run_id": run.id,
                "agent_label": run.agent_label,
                "status": run.status,
                "output": run.output,
                "error_message": run.error_message,
                "pipeline_name": pipeline_name,
                "step_name": step_name,
                "input_payload": input_payload,
            }

            if on_complete:
                try:
                    on_complete(payload)
                except Exception:
                    logger.exception("on_complete callback failed", extra={"run_id": run_id})

            agent_run_finished.send(
                sender=AgentRun,
                run_id=run.id,
                status=run.status,
                output=run.output,
                error_message=run.error_message,
                input_payload=input_payload,
            )
            agent_run_completed.send(
                sender=AgentRun,
                **payload,
            )

def run_agent(
    agent: InferenceRunner[Any] | InferenceAdapter[Any] | None = None,
    *,
    definition: AgentDefinition | None = None,
    input_payload: Any | None = None,
    agent_label: str | None = None,
    pipeline_name: str | None = None,
    step_name: str | None = None,
    on_complete: Any | None = None,
) -> uuid.UUID:
    """Helper for running agents with persistence."""
    managed = ManagedAgent(agent, definition=definition, agent_label=agent_label)
    return managed.run(
        input_payload=input_payload,
        agent_label=agent_label,
        pipeline_name=pipeline_name,
        step_name=step_name,
        on_complete=on_complete,
    )
