from __future__ import annotations

import asyncio
import enum
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pytest

from agents.core.agent import Agent, AgentConfig
from agents.core.agent import _json_safe_value


class DemoEnum(enum.Enum):
    VALUE = "value"


@dataclass
class DemoData:
    value: int


def _patch_openai_model_construction(monkeypatch) -> None:
    monkeypatch.setattr("agents.core.agent.OpenAIResponsesModel", lambda model: f"model:{model}")
    monkeypatch.setattr(
        "agents.core.agent.OpenAIResponsesModelSettings",
        lambda **kwargs: {"settings": kwargs},
    )


def test_agent_requires_config_or_default(settings) -> None:
    settings.DEFAULT_AGENT_CONFIG = None

    with pytest.raises(ValueError, match="DEFAULT_AGENT_CONFIG"):
        Agent()


def test_agent_uses_explicit_config_with_string_model(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.core.agent.PydanticAgent") as pydantic_agent:
        Agent(config=AgentConfig(instructions="test", model="gpt-5-mini"))

    assert pydantic_agent.call_count == 1


def test_agent_builds_config_from_kwargs(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.core.agent.PydanticAgent") as pydantic_agent:
        Agent(instructions="from kwargs", model="gpt-5-mini")

    assert pydantic_agent.call_count == 1


def test_agent_run_sync_serializes_payload_json(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.core.agent.PydanticAgent"):
        agent = Agent(config=AgentConfig(instructions="x"))

    fake = mock.Mock()
    fake.run_sync.return_value = SimpleNamespace(output={"ok": True})
    agent._pydantic_agent = fake

    result = agent.run_sync({"a": 1})

    assert result.output == {"ok": True}
    fake.run_sync.assert_called_once_with('{"a": 1}')


def test_agent_run_async_serializes_payload_json(monkeypatch) -> None:
    _patch_openai_model_construction(monkeypatch)
    with mock.patch("agents.core.agent.PydanticAgent"):
        agent = Agent(config=AgentConfig(instructions="x"))

    class FakeAsync:
        async def run(self, payload):
            assert payload == '{"b": 2}'
            return SimpleNamespace(output={"ok": True})

    agent._pydantic_agent = FakeAsync()

    result = asyncio.run(agent.run({"b": 2}))

    assert result.output == {"ok": True}


def test_agent_config_default_execution_backend() -> None:
    config = AgentConfig(instructions="test")
    assert config.execution_backend == "pydantic_ai"


def test_agent_config_pi_worker_backend_valid() -> None:
    config = AgentConfig(instructions="test", execution_backend="pi_worker")
    assert config.execution_backend == "pi_worker"


def test_agent_config_invalid_backend_raises() -> None:
    with pytest.raises(ValueError, match="execution_backend"):
        AgentConfig(instructions="test", execution_backend="invalid")


def test_agent_pi_worker_constructs_with_pi_worker_model(monkeypatch) -> None:
    from agents.core.tools.mcp.pi_model import PiWorkerModel

    captured: dict[str, object] = {}

    def _fake_pydantic_agent(model=None, **kwargs):
        captured["model"] = model
        captured["kwargs"] = kwargs
        return SimpleNamespace(model=model)

    monkeypatch.setattr("agents.core.agent.PydanticAgent", _fake_pydantic_agent)

    agent = Agent(
        config=AgentConfig(
            instructions="test",
            execution_backend="pi_worker",
            model="gpt-4o-mini",
        )
    )

    assert isinstance(captured["model"], PiWorkerModel)
    assert captured["model"].model_name == "gpt-4o-mini"
    assert captured["model"].provider_name == "openai"
    assert agent.config.execution_backend == "pi_worker"


def test_agent_pi_worker_passes_registry_toolset(monkeypatch) -> None:
    from agents.core.tools.contracts import Tool
    from pydantic import BaseModel

    captured: dict[str, object] = {}

    def _fake_pydantic_agent(model=None, **kwargs):
        captured["tools"] = kwargs.get("tools", [])
        return SimpleNamespace(model=model)

    monkeypatch.setattr("agents.core.agent.PydanticAgent", _fake_pydantic_agent)

    class _Input(BaseModel):
        text: str

    class _Output(BaseModel):
        echoed: str

    def _bound(payload: _Input) -> _Output:
        return _Output(echoed=payload.text)

    fake_tool = Tool(
        name="_pi_worker_echo",
        input_model=_Input,
        output_model=_Output,
        mcp_safe=True,
        toolset_name="_pi_worker_set",
        bound_method=_bound,
    )

    def _resolve(name):
        assert name == "_pi_worker_set"
        return [fake_tool]

    monkeypatch.setattr(
        "agents.core.tools.default_registry.resolve_toolset",
        _resolve,
    )

    Agent(
        config=AgentConfig(
            instructions="test",
            execution_backend="pi_worker",
            toolsets=["_pi_worker_set"],
        )
    )

    tool_names = [getattr(t, "__name__", None) for t in captured["tools"]]
    assert "_pi_worker_echo" in tool_names


def test_agent_pi_worker_forwards_config_instructions_with_system_prompt() -> None:
    captured: dict[str, object] = {}

    class _FakeClient:
        async def execute_workflow(self, workflow, payload, *, id, task_queue):
            captured["payload"] = payload
            return {"finalText": "ok", "toolCalls": [], "usage": {}}

    async def _factory():
        return _FakeClient()

    agent = Agent(
        config=AgentConfig(
            instructions="Follow the configured agent instructions.",
            execution_backend="pi_worker",
            model="stub-model",
            extra_kwargs={
                "provider": "stub",
                "system_prompt": "Keep the explicit system prompt.",
                "pi_worker_temporal_client_factory": _factory,
            },
        )
    )

    result = asyncio.run(agent.run({"prompt": "hello"}))

    assert result.output == "ok"
    assert captured["payload"]["systemPrompt"] == (
        "Keep the explicit system prompt.\n\nFollow the configured agent instructions."
    )


def test_pi_worker_model_request_translates_text_response() -> None:
    from pydantic_ai.messages import ModelRequest, TextPart, UserPromptPart
    from pydantic_ai.models import ModelRequestParameters

    from agents.core.tools.mcp.pi_model import PiWorkerModel

    captured: dict[str, object] = {}

    class _FakeClient:
        async def execute_workflow(self, workflow, payload, *, id, task_queue):
            captured["payload"] = payload
            captured["task_queue"] = task_queue
            return {
                "finalText": "ok",
                "toolCalls": [],
                "usage": {"inputTokens": 3, "outputTokens": 5, "totalTokens": 8},
            }

    async def _factory():
        return _FakeClient()

    model = PiWorkerModel(
        provider="stub",
        model_name="stub-model",
        temporal_client_factory=_factory,
        task_queue="agents-test",
    )

    response = asyncio.run(
        model.request(
            messages=[ModelRequest(parts=[UserPromptPart(content="hi")])],
            model_settings=None,
            model_request_parameters=ModelRequestParameters(),
        )
    )

    assert len(response.parts) == 1
    assert isinstance(response.parts[0], TextPart)
    assert response.parts[0].content == "ok"
    assert response.usage.input_tokens == 3
    assert response.usage.output_tokens == 5
    assert captured["task_queue"] == "agents-test"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.parametrize(
    ("temporal_queue", "pi_worker_host_queue", "expected_queue"),
    [
        (None, None, "ai-pipeline-queue"),
        ("shared-queue", None, "shared-queue"),
        ("shared-queue", "pi-host-queue", "pi-host-queue"),
    ],
)
def test_pi_worker_model_routes_to_bundled_worker_queue(
    settings,
    temporal_queue: str | None,
    pi_worker_host_queue: str | None,
    expected_queue: str,
) -> None:
    from pydantic_ai.messages import ModelRequest, UserPromptPart
    from pydantic_ai.models import ModelRequestParameters

    from agents.core.tools.mcp.pi_model import PiWorkerModel

    for setting_name, value in (
        ("TEMPORAL_TASK_QUEUE", temporal_queue),
        ("AGENTS_PI_WORKER_HOST_TASK_QUEUE", pi_worker_host_queue),
    ):
        if value is None:
            delattr(settings, setting_name)
        else:
            setattr(settings, setting_name, value)

    captured: dict[str, object] = {}

    class _FakeClient:
        async def execute_workflow(self, workflow, payload, *, id, task_queue):
            captured["task_queue"] = task_queue
            return {"finalText": "ok", "toolCalls": [], "usage": {}}

    async def _factory():
        return _FakeClient()

    model = PiWorkerModel(
        provider="stub",
        model_name="stub-model",
        temporal_client_factory=_factory,
    )

    asyncio.run(
        model.request(
            messages=[ModelRequest(parts=[UserPromptPart(content="hi")])],
            model_settings=None,
            model_request_parameters=ModelRequestParameters(),
        )
    )

    assert captured["task_queue"] == expected_queue


def test_pi_worker_model_request_translates_tool_call() -> None:
    from pydantic_ai.messages import ModelRequest, ToolCallPart, UserPromptPart
    from pydantic_ai.models import ModelRequestParameters

    from agents.core.tools.mcp.pi_model import PiWorkerModel

    class _FakeClient:
        async def execute_workflow(self, workflow, payload, *, id, task_queue):
            return {
                "finalText": "",
                "toolCalls": [{"name": "echo", "arguments": {"text": "x"}}],
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
            }

    async def _factory():
        return _FakeClient()

    model = PiWorkerModel(
        provider="stub",
        model_name="stub-model",
        temporal_client_factory=_factory,
        task_queue="agents-test",
    )

    response = asyncio.run(
        model.request(
            messages=[ModelRequest(parts=[UserPromptPart(content="hi")])],
            model_settings=None,
            model_request_parameters=ModelRequestParameters(),
        )
    )

    tool_parts = [p for p in response.parts if isinstance(p, ToolCallPart)]
    assert len(tool_parts) == 1
    assert tool_parts[0].tool_name == "echo"
    assert tool_parts[0].args_as_dict() == {"text": "x"}


def test_pi_worker_model_request_forwards_function_tool_schemas() -> None:
    from pydantic_ai.messages import ModelRequest, UserPromptPart
    from pydantic_ai.models import ModelRequestParameters
    from pydantic_ai.tools import ToolDefinition

    from agents.core.tools.mcp.pi_model import PiWorkerModel

    captured: dict[str, object] = {}

    class _FakeClient:
        async def execute_workflow(self, workflow, payload, *, id, task_queue):
            captured["payload"] = payload
            return {"finalText": "", "toolCalls": [], "usage": {}}

    async def _factory():
        return _FakeClient()

    model = PiWorkerModel(
        provider="stub",
        model_name="stub-model",
        temporal_client_factory=_factory,
        task_queue="agents-test",
    )

    params = ModelRequestParameters(
        function_tools=[
            ToolDefinition(
                name="echo",
                description="Echoes input.",
                parameters_json_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            )
        ]
    )

    asyncio.run(
        model.request(
            messages=[ModelRequest(parts=[UserPromptPart(content="hi")])],
            model_settings=None,
            model_request_parameters=params,
        )
    )

    payload = captured["payload"]
    assert payload["tools"] == [
        {
            "name": "echo",
            "description": "Echoes input.",
            "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
        }
    ]


def test_pi_worker_model_request_forwards_output_object_for_native_mode() -> None:
    from pydantic_ai.messages import ModelRequest, UserPromptPart
    from pydantic_ai.models import ModelRequestParameters
    from pydantic_ai.output import OutputObjectDefinition

    from agents.core.tools.mcp.pi_model import PiWorkerModel

    captured: dict[str, object] = {}

    class _FakeClient:
        async def execute_workflow(self, workflow, payload, *, id, task_queue):
            captured["payload"] = payload
            return {"finalText": "{}", "toolCalls": [], "usage": {}}

    async def _factory():
        return _FakeClient()

    model = PiWorkerModel(
        provider="stub",
        model_name="stub-model",
        temporal_client_factory=_factory,
        task_queue="agents-test",
    )

    params = ModelRequestParameters(
        output_mode="native",
        allow_text_output=False,
        output_object=OutputObjectDefinition(
            name="EchoSummary",
            description="Summary of an echo.",
            json_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        ),
    )

    asyncio.run(
        model.request(
            messages=[ModelRequest(parts=[UserPromptPart(content="hi")])],
            model_settings=None,
            model_request_parameters=params,
        )
    )

    payload = captured["payload"]
    assert payload["outputObject"]["name"] == "EchoSummary"
    assert payload["outputObject"]["jsonSchema"] == {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
    }


def test_pi_worker_agent_retries_malformed_structured_output() -> None:
    from pydantic import BaseModel
    from pydantic_ai import Agent as PydanticAgent

    from agents.core.tools.mcp.pi_model import PiWorkerModel

    class _StructuredOutput(BaseModel):
        answer: int

    captured_payloads: list[dict[str, object]] = []

    class _FakeClient:
        async def execute_workflow(self, workflow, payload, *, id, task_queue):
            captured_payloads.append(payload)
            if len(captured_payloads) == 1:
                return {
                    "finalText": "",
                    "toolCalls": [
                        {
                            "name": "final_result",
                            "id": "output-call-1",
                            "arguments": {"answer": "not-an-integer"},
                        }
                    ],
                    "usage": {},
                }
            return {
                "finalText": "",
                "toolCalls": [
                    {
                        "name": "final_result",
                        "id": "output-call-2",
                        "arguments": {"answer": 42},
                    }
                ],
                "usage": {},
            }

    async def _factory():
        return _FakeClient()

    model = PiWorkerModel(
        provider="stub",
        model_name="stub-model",
        temporal_client_factory=_factory,
        task_queue="agents-test",
    )
    agent = PydanticAgent(model=model, output_type=_StructuredOutput)

    result = asyncio.run(agent.run("Return a structured answer."))

    assert result.output == _StructuredOutput(answer=42)
    retry_message = captured_payloads[1]["messages"][-1]
    assert retry_message["role"] == "user"
    assert retry_message["content"].startswith("<tool_result>")
    retry_result = json.loads(
        retry_message["content"].removeprefix("<tool_result>").removesuffix("</tool_result>")
    )
    assert retry_result["tool"] == "final_result"
    assert retry_result["tool_call_id"] == "output-call-1"
    assert "Fix the errors and try again." in retry_result["result"]


def test_json_safe_value_normalizes_nested_values() -> None:
    value = _json_safe_value(
        {
            "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "at": datetime(2026, 5, 1, 12, 0, 0),
            "enum": DemoEnum.VALUE,
            "data": DemoData(value=3),
            "items": (DemoData(value=4),),
        }
    )

    assert value == {
        "id": "12345678-1234-5678-1234-567812345678",
        "at": "2026-05-01T12:00:00",
        "enum": "value",
        "data": {"value": 3},
        "items": [{"value": 4}],
    }
