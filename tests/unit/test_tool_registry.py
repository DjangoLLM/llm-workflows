from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from agents.runner.tools import (
    ToolExecutionError,
    ToolRegistry,
    ToolSet,
    default_registry,
    tool,
)

from tests.unit._toolsets import (
    DoubleInput,
    EchoInput,
    EchoOutput,
    EchoToolSet,
    EmptyToolSet,
    EnvToolSet,
    MultiToolSet,
    UnsafeToolSet,
)


@pytest.fixture
def registry():
    return ToolRegistry()


def test_register_toolset_round_trip(registry):
    registry.register_toolset(EchoToolSet, module="demo", expose_mcp=True)
    assert registry.get_toolset("echo") is EchoToolSet
    tools = registry.resolve_toolset("echo")
    assert [t.name for t in tools] == ["echo"]
    assert tools[0].toolset_name == "echo"
    assert tools[0].mcp_safe is True


def test_flat_surface_after_register(registry):
    registry.register_toolset(MultiToolSet, module="demo", expose_mcp=True)
    assert registry.names() == ["double", "shout"]
    result = registry.run("shout", {"text": "hi"})
    assert result == EchoOutput(result="HI")
    doubled = registry.run("double", DoubleInput(value=4))
    assert doubled.doubled == 8


def test_run_raises_validation_error_before_invoking(registry):
    registry.register_toolset(EchoToolSet, module="demo", expose_mcp=True)
    with pytest.raises(ValidationError):
        registry.run("echo", {"wrong_field": 1})


def test_get_raises_key_error_on_unknown(registry):
    with pytest.raises(KeyError):
        registry.get("nope")
    with pytest.raises(KeyError):
        registry.get_toolset("nope")
    with pytest.raises(KeyError):
        registry.resolve_toolset("nope")


def test_duplicate_toolset_name_raises(registry):
    registry.register_toolset(EchoToolSet, module="demo", expose_mcp=True)
    with pytest.raises(ValueError, match="Toolset 'echo' is already registered."):
        registry.register_toolset(EchoToolSet, module="demo", expose_mcp=True)


def test_duplicate_tool_name_across_toolsets_raises(registry):
    class _AnotherEcho(ToolSet):
        name = "other"

        @tool(input_model=EchoInput, output_model=EchoOutput, mcp_safe=True)
        def echo(self, input):
            return EchoOutput(result=input.text)

    registry.register_toolset(EchoToolSet, module="demo", expose_mcp=True)
    with pytest.raises(
        ValueError, match="Tool 'echo' is already registered by toolset 'echo'."
    ):
        registry.register_toolset(_AnotherEcho, module="demo", expose_mcp=True)


def test_expose_mcp_with_unsafe_tool_raises(registry):
    with pytest.raises(
        ValueError,
        match=r"Toolset 'unsafe' is expose_mcp=True but tool 'whisper' is not mcp_safe.",
    ):
        registry.register_toolset(UnsafeToolSet, module="demo", expose_mcp=True)


def test_unsafe_tool_allowed_without_expose_mcp(registry):
    # Pipeline-only tools may live in registry; not exposed to MCP.
    registry.register_toolset(UnsafeToolSet, module="demo", expose_mcp=False)
    assert "whisper" in registry.names()


def test_empty_toolset_raises(registry):
    with pytest.raises(
        ValueError, match=r"Toolset 'empty' has no @tool-decorated methods."
    ):
        registry.register_toolset(EmptyToolSet, module="demo", expose_mcp=False)


def test_toolset_without_name_raises(registry):
    class _Anon(ToolSet):
        @tool(input_model=EchoInput, output_model=EchoOutput)
        def echo(self, input):
            return EchoOutput(result=input.text)

    with pytest.raises(TypeError, match="must set class attribute 'name'"):
        registry.register_toolset(_Anon, module="demo")


def test_toolset_init_failure_propagates(registry, monkeypatch):
    monkeypatch.delenv("TEST_ENV_TOOLSET_VAR", raising=False)
    with pytest.raises(ToolExecutionError, match="config: TEST_ENV_TOOLSET_VAR"):
        registry.register_toolset(EnvToolSet, module="demo", expose_mcp=True)


def test_toolset_names_modules_filter(registry):
    registry.register_toolset(EchoToolSet, module="alpha", expose_mcp=True)
    registry.register_toolset(MultiToolSet, module="beta", expose_mcp=True)
    assert registry.toolset_names() == ["echo", "multi"]
    assert registry.toolset_names(modules=["alpha"]) == ["echo"]
    assert registry.toolset_names(modules=["beta"]) == ["multi"]
    assert registry.toolset_names(modules=["gamma"]) == []


def test_toolset_names_exposed_only(registry):
    registry.register_toolset(EchoToolSet, module="demo", expose_mcp=True)
    registry.register_toolset(UnsafeToolSet, module="demo", expose_mcp=False)
    assert registry.toolset_names() == ["echo", "unsafe"]
    assert registry.toolset_names(exposed_only=True) == ["echo"]


def test_names_modules_filter(registry):
    registry.register_toolset(EchoToolSet, module="alpha", expose_mcp=True)
    registry.register_toolset(MultiToolSet, module="beta", expose_mcp=True)
    assert registry.names() == ["double", "echo", "shout"]
    assert registry.names(modules=["beta"]) == ["double", "shout"]


def test_register_failure_leaves_registry_untouched(registry):
    registry.register_toolset(EchoToolSet, module="demo", expose_mcp=True)
    snapshot_tools = set(registry.names())
    snapshot_toolsets = set(registry.toolset_names())

    class _Conflict(ToolSet):
        name = "other"

        @tool(input_model=EchoInput, output_model=EchoOutput, mcp_safe=True)
        def echo(self, input):
            return EchoOutput(result=input.text)

    with pytest.raises(ValueError):
        registry.register_toolset(_Conflict, module="demo", expose_mcp=True)

    assert set(registry.names()) == snapshot_tools
    assert set(registry.toolset_names()) == snapshot_toolsets


def test_default_registry_is_module_level_singleton():
    from agents.runner.tools import default_registry as dr1
    from agents.catalog.tool_catalog import default_registry as dr2

    assert dr1 is dr2


def test_default_registry_starts_empty():
    assert default_registry.names() == []
    assert default_registry.toolset_names() == []
