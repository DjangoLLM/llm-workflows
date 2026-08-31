from __future__ import annotations

import pytest
from pydantic import BaseModel

from agents.core.tools.toolset import ToolSet, _TOOL_MARKER, _ToolMeta, tool


class _Input(BaseModel):
    text: str


class _Output(BaseModel):
    result: str


def test_tool_decorator_attaches_metadata():
    @tool(input_model=_Input, output_model=_Output, mcp_safe=True)
    def echo(self, input):
        return _Output(result=input.text)

    meta = getattr(echo, _TOOL_MARKER)
    assert isinstance(meta, _ToolMeta)
    assert meta.input_model is _Input
    assert meta.output_model is _Output
    assert meta.mcp_safe is True
    assert meta.name_override is None


def test_tool_decorator_records_name_override():
    @tool(input_model=_Input, output_model=_Output, name="alias")
    def echo(self, input):
        return _Output(result=input.text)

    assert getattr(echo, _TOOL_MARKER).name_override == "alias"


def test_tool_decorator_default_mcp_safe_is_false():
    @tool(input_model=_Input, output_model=_Output)
    def echo(self, input):
        return _Output(result=input.text)

    assert getattr(echo, _TOOL_MARKER).mcp_safe is False


def test_tool_decorated_method_is_callable_directly():
    class TS(ToolSet):
        name = "ts"

        @tool(input_model=_Input, output_model=_Output, mcp_safe=True)
        def echo(self, input):
            return _Output(result=input.text + "!")

    assert TS().echo(_Input(text="hi")) == _Output(result="hi!")


def test_tool_rejects_non_basemodel_input():
    class NotModel:
        pass

    with pytest.raises(TypeError, match="input_model"):
        tool(input_model=NotModel, output_model=_Output)  # type: ignore[arg-type]


def test_tool_rejects_non_basemodel_output():
    class NotModel:
        pass

    with pytest.raises(TypeError, match="output_model"):
        tool(input_model=_Input, output_model=NotModel)  # type: ignore[arg-type]


def test_undecorated_methods_have_no_marker():
    class TS(ToolSet):
        name = "ts"

        def helper(self):
            return 1

        @tool(input_model=_Input, output_model=_Output)
        def echo(self, input):
            return _Output(result=input.text)

    assert not hasattr(TS.helper, _TOOL_MARKER)
    assert hasattr(TS.echo, _TOOL_MARKER)


def test_toolset_subclass_without_name_class_defines_fine():
    # Class definition succeeds; only registration fails.
    class TS(ToolSet):
        @tool(input_model=_Input, output_model=_Output)
        def echo(self, input):
            return _Output(result=input.text)

    assert hasattr(TS.echo, _TOOL_MARKER)
