from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agents.core.tools import ToolExecutionError, ToolRegistry
from agents.core.tools.mcp.adapter import build_tool_adapter

from tests.unit._toolsets import EchoOutput, EchoToolSet, FailingTool


@pytest.fixture
def echo_tool():
    registry = ToolRegistry()
    registry.register_toolset(EchoToolSet, module="t", expose_mcp=True)
    return registry.resolve_toolset("echo")[0]


def test_adapter_exposes_input_model_schema():
    class _SchemaInput(BaseModel):
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

    class _Out(BaseModel):
        result: int

    def bound(input: _SchemaInput) -> _Out:
        return _Out(result=input.count + len(input.tags))

    from agents.core.tools.contracts import Tool

    adapter = build_tool_adapter(
        Tool(
            name="constrained",
            input_model=_SchemaInput,
            output_model=_Out,
            mcp_safe=True,
            toolset_name="tests",
            bound_method=bound,
        )
    )

    schema = adapter.parameters

    assert schema == _SchemaInput.model_json_schema()
    assert schema["properties"]["count"]["minimum"] == 1
    assert schema["properties"]["count"]["description"] == "Positive count"
    assert schema["properties"]["tags"]["description"] == "Optional tags"
    assert schema["properties"]["displayLabel"]["default"] == "default"
    assert schema["required"] == ["count"]
    assert schema["additionalProperties"] is False
    assert schema["x-model"] == "preserved"

    result = asyncio.run(adapter.run({"count": 1, "displayLabel": "custom"}))
    assert result.structured_content == {"result": 1}


def test_adapter_required_parameter_is_in_schema(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    assert adapter.parameters["required"] == ["text"]


def test_adapter_optional_field_has_default():
    class _OptInput(BaseModel):
        text: str
        suffix: str = "!"

    class _Out(BaseModel):
        result: str

    def bound(input):
        return _Out(result=input.text + input.suffix)

    from agents.core.tools.contracts import Tool

    tool = Tool(
        name="t",
        input_model=_OptInput,
        output_model=_Out,
        mcp_safe=True,
        toolset_name="x",
        bound_method=bound,
    )
    adapter = build_tool_adapter(tool)
    assert adapter.parameters["required"] == ["text"]
    assert adapter.parameters["properties"]["suffix"]["default"] == "!"


def test_adapter_returns_model_dump_dict(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    out = adapter.fn(text="hi")
    assert isinstance(out, dict)
    assert out == {"result": "hi"}


def test_adapter_validates_kwargs(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    with pytest.raises(ValidationError):
        adapter.fn()  # missing required `text`


def test_adapter_propagates_tool_execution_error_unchanged():
    registry = ToolRegistry()
    registry.register_toolset(FailingTool, module="t", expose_mcp=True)
    [tool] = registry.resolve_toolset("failing")
    adapter = build_tool_adapter(tool)
    with pytest.raises(ToolExecutionError) as excinfo:
        adapter.fn(text="hi")
    err = excinfo.value
    assert err.tool_name == "boom"
    assert err.provider_status == 503
    assert err.provider_body == "upstream"


def test_adapter_name_and_qualname(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    assert adapter.name == "echo"
    assert adapter.fn.__name__ == "echo"
    assert adapter.fn.__qualname__ == "echo"


def test_adapter_keeps_dict_output_untyped(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    assert adapter.output_schema is None


def test_adapter_returns_json_dumpable(echo_tool):
    import json

    adapter = build_tool_adapter(echo_tool)
    json.dumps(adapter.fn(text="hi"))


def test_adapter_output_is_model_dump_json_mode():
    """mode='json' converts UUID/datetime to JSON-friendly types."""
    import uuid

    class _Input(BaseModel):
        text: str

    class _Output(BaseModel):
        ident: uuid.UUID

    sentinel = uuid.uuid4()

    def bound(input):
        return _Output(ident=sentinel)

    from agents.core.tools.contracts import Tool

    tool = Tool(
        name="t",
        input_model=_Input,
        output_model=_Output,
        mcp_safe=True,
        toolset_name="x",
        bound_method=bound,
    )
    adapter = build_tool_adapter(tool)
    out = adapter.fn(text="ignored")
    assert out["ident"] == str(sentinel)
