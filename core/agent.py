"""Agent definition wrapper plus managed persistence helper."""
from __future__ import annotations
from typing import Dict

import logging
import dataclasses
import enum
import threading
import uuid
from collections.abc import Mapping as ABCMapping, Sequence as ABCSequence
from datetime import date, datetime
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Mapping, Optional

import django
from django.conf import settings
from django.utils import timezone
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel, OpenAIResponsesModelSettings

from agents.handlers import agent_run_completed

logger = logging.getLogger(__name__)

# Signal emitted when an agent run reaches a terminal state (SUCCEEDED or FAILED).
agent_run_finished = django.dispatch.Signal()


def _json_safe_value(value: Any) -> Any:
    """Recursively coerce values into JSON-serializable primitives."""
    if dataclasses.is_dataclass(value):
        return _json_safe_value(dataclasses.asdict(value))
    if hasattr(value, "model_dump"):
        return _json_safe_value(value.model_dump())
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, ABCMapping):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, ABCSequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, enum.Enum):
        return value.value
    return value


@dataclass(slots=True)
class AgentConfig:
    """Configuration inputs for constructing a Pydantic AI agent."""
    instructions: str
    execution_backend: Literal["pydantic_ai"] = "pydantic_ai"
    model: OpenAIChatModel | OpenAIResponsesModel | str | None = None
    settings: OpenAIResponsesModelSettings | None = None
    result_type: type[Any] | None = None
    tools: Iterable[Callable[..., Any]] | None = None
    toolsets: Iterable[str] | None = None
    extra_kwargs: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.execution_backend != "pydantic_ai":
            raise ValueError(
                "execution_backend must be 'pydantic_ai'; "
                f"got {self.execution_backend!r}"
            )


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
                )

        self.config = config
        self._pydantic_agent = self._create_pydantic_agent(config)

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
            from agents.core.tools.pydantic_ai_adapter import build_pydantic_ai_tool
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

    async def run(self, input_payload: Optional[Dict[str, Any]] = None) -> Any:
        """Execute without persistence (async); returns pydantic_ai run result."""
        import json

        logger.info("Running agent async with payload: %s", input_payload)
        logger.info("Instructions: %s", self.config.instructions)
        output = await self._pydantic_agent.run(json.dumps(input_payload))
        logger.info("Output: %s", output)
        return output

    def run_sync(self, input_payload: Optional[Dict[str, Any]] = None) -> Any:
        """Execute without persistence; returns pydantic_ai run result."""
        import json

        logger.info("Running agent sync with payload: %s", input_payload)
        logger.info("Instructions: %s", self.config.instructions)
        output = self._pydantic_agent.run_sync(json.dumps(input_payload))
        logger.info("Output: %s", output)
        return output


class ManagedAgent:
    """Orchestrates persistence around a plain Agent or pydantic_ai.Agent."""

    def __init__(
        self,
        agent: Agent | PydanticAgent | Any | None = None,
        *,
        config: AgentConfig | None = None,
        agent_label: Optional[str] = None,
    ):
        if agent is None:
            agent = Agent(config)

        self._agent = agent
        self._pydantic_agent = (
            agent._pydantic_agent if isinstance(agent, Agent) else agent
        )
        self._agent_label = agent_label or getattr(self._pydantic_agent, "name", None)
        self._started = False

        from agents.models import AgentRun, AgentRunStatus

        run = AgentRun.objects.create(
            agent_label=self._agent_label or "agent",
            status=AgentRunStatus.PENDING,
        )
        self.run_id = run.id

    def run(
        self,
        input_payload: Optional[Any] = None,
        *,
        agent_label: Optional[str] = None,
        pipeline_name: Optional[str] = None,
        step_name: Optional[str] = None,
        on_complete: Optional[Any] = None,
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
        input_payload: Optional[Any] = None,
        *,
        agent_label: Optional[str] = None,
        pipeline_name: Optional[str] = None,
        step_name: Optional[str] = None,
        on_complete: Optional[Any] = None,
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
        input_payload: Optional[Any],
        pipeline_name: Optional[str],
        step_name: Optional[str],
        on_complete: Optional[Any],
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
            output = _json_safe_value(output)
            run.output = output
            run.status = AgentRunStatus.SUCCEEDED
        except Exception as exc:  # noqa: BLE001
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
                except Exception:  # noqa: BLE001
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
    input_payload: Optional[Any] = None,
    agent_label: Optional[str] = None,
    pipeline_name: Optional[str] = None,
    step_name: Optional[str] = None,
    on_complete: Optional[Any] = None,
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
