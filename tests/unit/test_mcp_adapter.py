from __future__ import annotations

import inspect

import pytest
from pydantic import BaseModel, ValidationError

from agents.core.tools import ToolExecutionError, ToolRegistry
from agents.core.tools.mcp.adapter import build_tool_adapter

from tests.unit._toolsets import EchoOutput, EchoToolSet, FailingTool


@pytest.fixture
def echo_tool():
    registry = ToolRegistry()
    registry.register_toolset(EchoToolSet, module="t", expose_mcp=True)
    return registry.resolve_toolset("echo")[0]


def test_adapter_signature_mirrors_input_model_keys(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    sig = adapter.__signature__
    assert list(sig.parameters.keys()) == list(
        echo_tool.input_model.model_fields.keys()
    )


def test_adapter_signature_annotations_match_input_model_fields(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    for field_name, field_info in echo_tool.input_model.model_fields.items():
        assert (
            adapter.__signature__.parameters[field_name].annotation
            is field_info.annotation
        )


def test_adapter_parameters_are_keyword_only(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    for p in adapter.__signature__.parameters.values():
        assert p.kind is inspect.Parameter.KEYWORD_ONLY


def test_adapter_required_parameter_has_no_default(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    text_param = adapter.__signature__.parameters["text"]
    assert text_param.default is inspect.Parameter.empty


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
    assert adapter.__signature__.parameters["text"].default is inspect.Parameter.empty
    assert adapter.__signature__.parameters["suffix"].default == "!"


def test_adapter_returns_model_dump_dict(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    out = adapter(text="hi")
    assert isinstance(out, dict)
    assert out == {"result": "hi"}


def test_adapter_validates_kwargs(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    with pytest.raises(ValidationError):
        adapter()  # missing required `text`


def test_adapter_propagates_tool_execution_error_unchanged():
    registry = ToolRegistry()
    registry.register_toolset(FailingTool, module="t", expose_mcp=True)
    [tool] = registry.resolve_toolset("failing")
    adapter = build_tool_adapter(tool)
    with pytest.raises(ToolExecutionError) as excinfo:
        adapter(text="hi")
    err = excinfo.value
    assert err.tool_name == "boom"
    assert err.provider_status == 503
    assert err.provider_body == "upstream"


def test_adapter_name_and_qualname(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    assert adapter.__name__ == "echo"
    assert adapter.__qualname__ == "echo"


def test_adapter_return_annotation_is_dict(echo_tool):
    adapter = build_tool_adapter(echo_tool)
    assert adapter.__signature__.return_annotation is dict


def test_adapter_returns_json_dumpable(echo_tool):
    import json

    adapter = build_tool_adapter(echo_tool)
    json.dumps(adapter(text="hi"))


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
    out = adapter(text="ignored")
    assert out["ident"] == str(sentinel)
