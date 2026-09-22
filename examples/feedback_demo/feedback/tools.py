"""Demo ToolSet illustrating how a host app exposes tools via the registry.

The toolset is registered in `FeedbackConfig.ready()`; this module only
declares it. Validates the boot path for `agents.adapters.tools.mcp` / `run_tools_mcp`.
"""

from __future__ import annotations

from pydantic import BaseModel

from agents.tools import ToolSet, tool


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    echoed: str
    char_count: int


class EchoToolSet(ToolSet):
    name = "echo"

    @tool(input_model=EchoInput, output_model=EchoOutput, mcp_safe=True)
    def echo(self, input: EchoInput) -> EchoOutput:
        return EchoOutput(echoed=input.text, char_count=len(input.text))
