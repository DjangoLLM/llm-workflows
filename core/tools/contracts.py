from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel


@dataclass(slots=True, frozen=True)
class Tool:
    name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    mcp_safe: bool
    toolset_name: str
    bound_method: Callable[[BaseModel], BaseModel]


class ToolExecutionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        tool_name: str | None = None,
        input_snapshot: dict | None = None,
        provider_status: int | None = None,
        provider_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.input_snapshot = input_snapshot
        self.provider_status = provider_status
        self.provider_body = provider_body
