"""PiWorkerModel: a pydantic_ai Model that dispatches inference to the pi-worker.

Single-turn translator: receives pydantic_ai messages + tool / output schemas,
encodes them into the pi-worker payload, runs `PiInferenceTurnWorkflow` on the
host Temporal worker, and decodes the response back into a `ModelResponse`.
pydantic_ai's agent graph owns the multi-turn loop and tool dispatch.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable, Optional

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RequestUsage


DEFAULT_TASK_QUEUE_SETTING = "AGENTS_PI_WORKER_HOST_TASK_QUEUE"
PI_INFERENCE_WORKFLOW_NAME = "agents.PiInferenceTurnWorkflow"


TemporalClientFactory = Callable[[], Awaitable[Any]]


async def _default_temporal_client_factory() -> Any:
    """Resolve a Temporal client from Django settings."""
    from django.conf import settings as django_settings
    from temporalio.client import Client

    url = getattr(django_settings, "TEMPORAL_SERVER_URL", "localhost:7233")
    return await Client.connect(url)


def _jsonable(value: Any) -> Any:
    """Coerce tool-return content into a JSON-serializable form."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


def _default_task_queue() -> str:
    from django.conf import settings as django_settings

    queue = getattr(django_settings, DEFAULT_TASK_QUEUE_SETTING, None)
    if not queue:
        queue = getattr(django_settings, "AGENTS_TEMPORAL_TASK_QUEUE", "agents")
    return str(queue)


class PiWorkerModel(Model):
    """pydantic_ai Model whose inference round-trips through the pi-worker."""

    def __init__(
        self,
        *,
        provider: str,
        model_name: str,
        temporal_client_factory: Optional[TemporalClientFactory] = None,
        task_queue: Optional[str] = None,
        activity_timeout_seconds: int = 60,
        settings: ModelSettings | None = None,
        profile: ModelProfile | None = None,
    ) -> None:
        if profile is None:
            profile = ModelProfile(
                supports_tools=True,
                supports_json_schema_output=True,
                supports_json_object_output=True,
            )
        super().__init__(settings=settings, profile=profile)
        if not provider:
            raise ValueError("PiWorkerModel requires a non-empty provider.")
        if not model_name:
            raise ValueError("PiWorkerModel requires a non-empty model_name.")
        self._provider = provider
        self._model_name = model_name
        self._temporal_client_factory = temporal_client_factory
        self._task_queue = task_queue
        self._activity_timeout_seconds = activity_timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def system(self) -> str:
        return "pi_worker"

    @property
    def provider_name(self) -> str:
        return self._provider

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        model_settings, model_request_parameters = self.prepare_request(
            model_settings, model_request_parameters
        )

        payload = self._build_payload(messages, model_request_parameters)

        client_factory = self._temporal_client_factory or _default_temporal_client_factory
        client = await client_factory()
        task_queue = self._task_queue or _default_task_queue()

        workflow_id = f"pi-inference-{uuid.uuid4().hex[:12]}"
        result = await client.execute_workflow(
            PI_INFERENCE_WORKFLOW_NAME,
            payload,
            id=workflow_id,
            task_queue=task_queue,
        )

        return self._translate_response(result)

    # ------------------------------------------------------------------
    # Payload translation
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        messages: list[ModelMessage],
        params: ModelRequestParameters,
    ) -> dict[str, Any]:
        system_prompts: list[str] = []
        pi_messages: list[dict[str, str]] = []
        for message in messages:
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    if isinstance(part, SystemPromptPart):
                        system_prompts.append(part.content)
                    elif isinstance(part, UserPromptPart):
                        content = part.content
                        if not isinstance(content, str):
                            raise NotImplementedError(
                                "PiWorkerModel only supports string UserPromptPart content."
                            )
                        pi_messages.append({"role": "user", "content": content})
                    elif isinstance(part, ToolReturnPart):
                        encoded = json.dumps(
                            {
                                "tool": part.tool_name,
                                "tool_call_id": part.tool_call_id,
                                "result": _jsonable(part.content),
                            }
                        )
                        pi_messages.append(
                            {"role": "user", "content": f"<tool_result>{encoded}</tool_result>"}
                        )
                    else:
                        raise NotImplementedError(
                            f"PiWorkerModel does not support request part kind {type(part).__name__}"
                        )
            elif isinstance(message, ModelResponse):
                for part in message.parts:
                    if isinstance(part, TextPart):
                        pi_messages.append({"role": "assistant", "content": part.content})
                    elif isinstance(part, ToolCallPart):
                        encoded = json.dumps(
                            {
                                "tool_call": part.tool_name,
                                "tool_call_id": part.tool_call_id,
                                "args": part.args_as_json_str() if part.args is not None else "{}",
                            }
                        )
                        pi_messages.append({"role": "assistant", "content": encoded})
                    else:
                        raise NotImplementedError(
                            f"PiWorkerModel does not support response part kind {type(part).__name__}"
                        )
            else:
                raise NotImplementedError(
                    f"PiWorkerModel does not support message type {type(message).__name__}"
                )

        tools: list[dict[str, Any]] = [
            {
                "name": td.name,
                "description": td.description or "",
                "input_schema": td.parameters_json_schema,
            }
            for td in params.function_tools
        ]

        output_object_payload: dict[str, Any] | None = None
        if params.output_mode == "tool":
            for td in params.output_tools:
                tools.append(
                    {
                        "name": td.name,
                        "description": td.description or "",
                        "input_schema": td.parameters_json_schema,
                    }
                )
        elif params.output_mode in ("native", "prompted") and params.output_object is not None:
            output_object_payload = {
                "name": params.output_object.name,
                "description": params.output_object.description or "",
                "jsonSchema": params.output_object.json_schema,
            }

        payload: dict[str, Any] = {
            "provider": self._provider,
            "model": self._model_name,
            "systemPrompt": "\n\n".join(system_prompts),
            "messages": pi_messages,
            "tools": tools,
            "activity_timeout_seconds": self._activity_timeout_seconds,
        }
        if output_object_payload is not None:
            payload["outputObject"] = output_object_payload
        return payload

    def _translate_response(self, result: dict[str, Any]) -> ModelResponse:
        if not isinstance(result, dict):
            raise ValueError(
                f"PiInferenceTurnWorkflow returned non-dict result: {type(result).__name__}"
            )
        final_text = result.get("finalText", "") or ""
        tool_calls = result.get("toolCalls") or []
        usage_raw = result.get("usage") or {}

        parts: list[Any] = []
        if tool_calls:
            if final_text:
                parts.append(TextPart(content=final_text))
            for call in tool_calls:
                args = call.get("arguments")
                if isinstance(args, str):
                    args_value: Any = args
                else:
                    args_value = args if args is not None else {}
                parts.append(
                    ToolCallPart(
                        tool_name=call["name"],
                        args=args_value,
                        tool_call_id=call.get("id") or call.get("tool_call_id") or uuid.uuid4().hex,
                    )
                )
        else:
            parts.append(TextPart(content=final_text))

        usage = RequestUsage(
            input_tokens=int(usage_raw.get("inputTokens", 0) or 0),
            output_tokens=int(usage_raw.get("outputTokens", 0) or 0),
        )

        return ModelResponse(parts=parts, model_name=self.model_name, usage=usage)
