from __future__ import annotations

import pytest
from pydantic import BaseModel

from agents.core.tools.contracts import Tool, ToolExecutionError


class _Input(BaseModel):
    text: str


class _Output(BaseModel):
    result: str


def _bound(input: _Input) -> _Output:
    return _Output(result=input.text)


def _make_tool(**overrides) -> Tool:
    fields = dict(
        name="echo",
        input_model=_Input,
        output_model=_Output,
        mcp_safe=True,
        toolset_name="demo",
        bound_method=_bound,
    )
    fields.update(overrides)
    return Tool(**fields)


def test_tool_execution_error_carries_all_fields():
    err = ToolExecutionError(
        "something went wrong",
        tool_name="search_web",
        input_snapshot={"q": "test"},
        provider_status=503,
        provider_body="Service Unavailable",
    )
    assert str(err) == "something went wrong"
    assert err.tool_name == "search_web"
    assert err.input_snapshot == {"q": "test"}
    assert err.provider_status == 503
    assert err.provider_body == "Service Unavailable"


def test_tool_execution_error_optional_fields_default_none():
    err = ToolExecutionError("config: SEARXNG_URL missing")
    assert err.tool_name is None
    assert err.input_snapshot is None
    assert err.provider_status is None
    assert err.provider_body is None


def test_tool_execution_error_is_exception():
    with pytest.raises(ToolExecutionError):
        raise ToolExecutionError("boom")


def test_tool_descriptor_round_trip():
    t = _make_tool()
    assert t.name == "echo"
    assert t.input_model is _Input
    assert t.output_model is _Output
    assert t.mcp_safe is True
    assert t.toolset_name == "demo"
    assert t.bound_method(_Input(text="hi")) == _Output(result="hi")


def test_tool_descriptor_is_frozen():
    t = _make_tool()
    with pytest.raises(Exception):
        t.name = "other"  # type: ignore[misc]


def test_tool_descriptor_equality_by_value():
    a = _make_tool()
    b = _make_tool()
    assert a == b


def test_tool_descriptor_is_hashable():
    t = _make_tool()
    assert hash(t) == hash(_make_tool())
