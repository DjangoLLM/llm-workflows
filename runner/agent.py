"""Agent execution and managed persistence."""
from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from typing import Any

import django
from agents.core.agent import AgentConfig
from agents.core.json_safe import json_safe
from agents.handlers import agent_run_completed
from django.conf import settings
from django.utils import timezone
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.models.openai import (
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)

logger = logging.getLogger(__name__)

# Signal emitted when an agent run reaches a terminal state (SUCCEEDED or FAILED).
agent_run_finished = django.dispatch.Signal()


class Agent:
    """Agent definition wrapper around pydantic_ai; no persistence."""

    def __init__(self, config: AgentConfig | None = None, **kwargs):
        """
        Initialize the agent. If config is not provided, it attempts to load
        DEFAULT_AGENT_CONFIG from Django settings.

        Args:
            config: An AgentConfig instance.
            **kwargs: Individual config fields if config is not provided.
        """
        if config is None:
            if not kwargs:
                config = getattr(settings, 'DEFAULT_AGENT_CONFIG', None)
                if config is None:
                    raise ValueError('DEFAULT_AGENT_CONFIG is not defined in Django settings.')
            else:
                config = AgentConfig(
                    instructions=kwargs.get('instructions', 'You are a helpful assistant.'),
                    execution_backend=kwargs.get('execution_backend', 'pydantic_ai'),
                    model=kwargs.get('model'),
                    settings=kwargs.get('settings'),
                    result_type=kwargs.get('result_type'),
                    tools=kwargs.get('tools'),
                    toolsets=kwargs.get('toolsets'),
                    extra_kwargs=kwargs.get('extra_kwargs'),
                    questions=kwargs.get('questions'),
                )

        self.config = config
        if config.execution_backend == "codex_cli":
            from agents.runner.backends.codex import CodexRunner

            self._pydantic_agent = None
            self._runner = CodexRunner.from_config(config)
        elif config.execution_backend == "jev":
            from agents.runner.backends.jev import JevRunner

            self._pydantic_agent = None
            self._runner = JevRunner.from_config(config)
        else:
            self._pydantic_agent = self._create_pydantic_agent(config)
            self._runner = self._pydantic_agent

    def _create_pydantic_agent(self, config: AgentConfig) -> PydanticAgent:
        """Construct a configured `pydantic_ai.Agent` instance."""
        model = config.model
        if isinstance(model, str):
            model = OpenAIResponsesModel(model)
        elif model is None:
            model = OpenAIResponsesModel('gpt-5-mini')
        model_settings = (
            config.settings
            if config.settings
            else OpenAIResponsesModelSettings(openai_reasoning_effort='none')
        )

        all_tools: list[Callable[..., Any]] = list(config.tools or [])

        if config.toolsets:
            from agents.core.tools import default_registry
            from agents.runner.tools.pydantic_ai import build_pydantic_ai_tool
            for toolset_name in config.toolsets:
                for tool in default_registry.resolve_toolset(toolset_name):
                    all_tools.append(build_pydantic_ai_tool(tool))

        agent_kwargs: dict[str, Any] = {"instructions": config.instructions}
        if config.result_type is not None:
            agent_kwargs["output_type"] = config.result_type
        if all_tools:
            agent_kwargs["tools"] = all_tools
        if config.extra_kwargs:
            agent_kwargs.update(config.extra_kwargs)

        return PydanticAgent(model=model, model_settings=model_settings, **agent_kwargs)

    async def run(self, input_payload: dict[str, Any] | None = None) -> Any:
        """Execute without persistence (async); returns pydantic_ai run result."""
        import json

        logger.info("Running agent async with backend %s", self.config.execution_backend)
        if self.config.execution_backend != "pydantic_ai":
            return await self._runner.run(input_payload)
        return await self._pydantic_agent.run(json.dumps(input_payload))

    def run_sync(self, input_payload: dict[str, Any] | None = None) -> Any:
        """Execute without persistence; returns pydantic_ai run result."""
        import json

        logger.info("Running agent sync with backend %s", self.config.execution_backend)
        if self.config.execution_backend != "pydantic_ai":
            return self._runner.run_sync(input_payload)
        return self._pydantic_agent.run_sync(json.dumps(input_payload))


class ManagedAgent:
    """Orchestrates persistence around a plain Agent or pydantic_ai.Agent."""

    def __init__(
        self,
        agent: Agent | PydanticAgent | Any | None = None,
        *,
        config: AgentConfig | None = None,
        agent_label: str | None = None,
    ):
        if agent is None:
            agent = Agent(config)

        self._agent = agent
        self._pydantic_agent = (
            agent._pydantic_agent if isinstance(agent, Agent) else agent
        )
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
    agent: Agent | PydanticAgent | None = None,
    *,
    config: AgentConfig | None = None,
    input_payload: Any | None = None,
    agent_label: str | None = None,
    pipeline_name: str | None = None,
    step_name: str | None = None,
    on_complete: Any | None = None,
) -> uuid.UUID:
    """Helper for running agents with persistence."""
    managed = ManagedAgent(agent, config=config, agent_label=agent_label)
    return managed.run(
        input_payload=input_payload,
        agent_label=agent_label,
        pipeline_name=pipeline_name,
        step_name=step_name,
        on_complete=on_complete,
    )
