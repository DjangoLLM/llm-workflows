"""Test-only ToolSet fixtures. Underscore-prefixed so pytest does not collect it."""

from __future__ import annotations

import os

from pydantic import BaseModel

from agents.tools import ToolExecutionError, ToolSet, tool


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    result: str


class EchoToolSet(ToolSet):
    name = "echo"

    @tool(input_model=EchoInput, output_model=EchoOutput, mcp_safe=True)
    def echo(self, input: EchoInput) -> EchoOutput:
        return EchoOutput(result=input.text)


class DoubleInput(BaseModel):
    value: int


class DoubleOutput(BaseModel):
    doubled: int


class MultiToolSet(ToolSet):
    name = "multi"

    @tool(input_model=EchoInput, output_model=EchoOutput, mcp_safe=True)
    def shout(self, input: EchoInput) -> EchoOutput:
        return EchoOutput(result=input.text.upper())

    @tool(input_model=DoubleInput, output_model=DoubleOutput, mcp_safe=True)
    def double(self, input: DoubleInput) -> DoubleOutput:
        return DoubleOutput(doubled=input.value * 2)


class UnsafeToolSet(ToolSet):
    name = "unsafe"

    @tool(input_model=EchoInput, output_model=EchoOutput)  # mcp_safe defaults False
    def whisper(self, input: EchoInput) -> EchoOutput:
        return EchoOutput(result=input.text)


class EnvToolSet(ToolSet):
    name = "env"

    def __init__(self) -> None:
        super().__init__()
        if "TEST_ENV_TOOLSET_VAR" not in os.environ:
            raise ToolExecutionError("config: TEST_ENV_TOOLSET_VAR missing")

    @tool(input_model=EchoInput, output_model=EchoOutput, mcp_safe=True)
    def echo(self, input: EchoInput) -> EchoOutput:
        return EchoOutput(result=input.text)


class EmptyToolSet(ToolSet):
    name = "empty"


class FailingTool(ToolSet):
    name = "failing"

    @tool(input_model=EchoInput, output_model=EchoOutput, mcp_safe=True)
    def boom(self, input: EchoInput) -> EchoOutput:
        raise ToolExecutionError(
            "boom",
            tool_name="boom",
            provider_status=503,
            provider_body="upstream",
        )
