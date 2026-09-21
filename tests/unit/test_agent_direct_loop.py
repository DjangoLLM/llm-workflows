from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel
from pydantic_ai.messages import ModelResponse, RetryPromptPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agents.core.agent import Agent, AgentConfig
from agents.core.tools.contracts import Tool


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    echoed: str


class StructuredAnswer(BaseModel):
    answer: str


def _tool_then_structured_output_model(
    *, tool_name: str, expected_tool_output: str
) -> tuple[FunctionModel, list[list[Any]]]:
    requests: list[list[Any]] = []

    def respond(messages: list[Any], info: AgentInfo) -> ModelResponse:
        requests.append(messages)
        if len(requests) == 1:
            assert [tool.name for tool in info.function_tools] == [tool_name]
            return ModelResponse(
                parts=[ToolCallPart(tool_name, {"text": "hello"})]
            )

        assert expected_tool_output in str(messages)
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {"answer": "tool completed"},
                )
            ]
        )

    return FunctionModel(respond), requests


def _fail_if_temporal_connects(*args: Any, **kwargs: Any) -> None:
    raise AssertionError("direct Agent inference must not connect to Temporal")


def test_run_uses_registered_tool_and_returns_validated_structured_output(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def echo(payload: EchoInput) -> EchoOutput:
        calls.append(payload.text)
        return EchoOutput(echoed=payload.text)

    registered_tool = Tool(
        name="registered_echo",
        input_model=EchoInput,
        output_model=EchoOutput,
        mcp_safe=True,
        toolset_name="direct_loop_tools",
        bound_method=echo,
    )
    monkeypatch.setattr(
        "agents.core.tools.default_registry.resolve_toolset",
        lambda name: [registered_tool] if name == "direct_loop_tools" else [],
    )
    monkeypatch.setattr("temporalio.client.Client.connect", _fail_if_temporal_connects)
    model, requests = _tool_then_structured_output_model(
        tool_name="registered_echo",
        expected_tool_output="hello",
    )
    agent = Agent(
        config=AgentConfig(
            instructions="Use the echo tool and summarize its result.",
            model=model,
            result_type=StructuredAnswer,
            toolsets=["direct_loop_tools"],
        )
    )

    result = asyncio.run(agent.run({"text": "hello"}))

    assert result.output == StructuredAnswer(answer="tool completed")
    assert calls == ["hello"]
    assert len(requests) == 2


def test_run_sync_uses_explicit_tool_and_returns_validated_structured_output(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def explicit_echo(text: str) -> str:
        calls.append(text)
        return f"echoed: {text}"

    monkeypatch.setattr("temporalio.client.Client.connect", _fail_if_temporal_connects)
    model, requests = _tool_then_structured_output_model(
        tool_name="explicit_echo",
        expected_tool_output="echoed: hello",
    )
    agent = Agent(
        config=AgentConfig(
            instructions="Use the echo tool and summarize its result.",
            model=model,
            result_type=StructuredAnswer,
            tools=[explicit_echo],
        )
    )

    result = agent.run_sync({"text": "hello"})

    assert result.output == StructuredAnswer(answer="tool completed")
    assert calls == ["hello"]
    assert len(requests) == 2


def test_invalid_structured_output_uses_pydantic_ai_retry_policy() -> None:
    requests: list[list[Any]] = []

    def respond(messages: list[Any], info: AgentInfo) -> ModelResponse:
        requests.append(messages)
        output_tool_name = info.output_tools[0].name
        if len(requests) == 1:
            return ModelResponse(
                parts=[ToolCallPart(output_tool_name, {"wrong_field": "no answer"})]
            )
        assert any(
            isinstance(part, RetryPromptPart)
            for message in messages
            for part in message.parts
        )
        return ModelResponse(
            parts=[ToolCallPart(output_tool_name, {"answer": "recovered"})]
        )

    agent = Agent(
        config=AgentConfig(
            instructions="Return a structured answer.",
            model=FunctionModel(respond),
            result_type=StructuredAnswer,
        )
    )

    result = agent.run_sync({"text": "hello"})

    assert result.output == StructuredAnswer(answer="recovered")
    assert len(requests) == 2
