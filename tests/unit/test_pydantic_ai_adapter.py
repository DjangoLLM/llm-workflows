from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agents.core.tools.contracts import Tool
from agents.core.tools.pydantic_ai_adapter import build_pydantic_ai_tool


class _ConstrainedInput(BaseModel):
    model_config = ConfigDict(
        title="Constrained input",
        extra="forbid",
        json_schema_extra={"x-model": "preserved"},
    )

    count: int = Field(ge=1, description="Positive count")
    tags: list[str] = Field(default_factory=list, description="Optional tags")
    label: str = Field(
        "default",
        alias="displayLabel",
        description="Display label",
    )


class _Output(BaseModel):
    result: int


def _build_constrained_tool() -> Tool:
    def bound(input: _ConstrainedInput) -> _Output:
        return _Output(result=input.count + len(input.tags))

    return Tool(
        name="constrained",
        input_model=_ConstrainedInput,
        output_model=_Output,
        mcp_safe=True,
        toolset_name="tests",
        bound_method=bound,
    )


def test_pydantic_ai_tool_exposes_input_model_schema():
    adapted = build_pydantic_ai_tool(_build_constrained_tool())

    schema = adapted.tool_def.parameters_json_schema

    assert schema == _ConstrainedInput.model_json_schema()
    assert schema["properties"]["count"]["minimum"] == 1
    assert schema["properties"]["count"]["description"] == "Positive count"
    assert schema["properties"]["tags"]["description"] == "Optional tags"
    assert schema["properties"]["displayLabel"]["default"] == "default"
    assert schema["required"] == ["count"]
    assert schema["additionalProperties"] is False
    assert schema["x-model"] == "preserved"


def test_pydantic_ai_tool_validates_and_applies_factory_defaults():
    adapted = build_pydantic_ai_tool(_build_constrained_tool())

    assert adapted.function(count=1, displayLabel="custom") == _Output(result=1)
    with pytest.raises(ValidationError):
        adapted.function(count=0)
