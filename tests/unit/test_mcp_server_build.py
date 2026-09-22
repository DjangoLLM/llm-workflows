from __future__ import annotations

import asyncio
import importlib
import sys

import pytest

from agents.core.tools import ToolRegistry
from agents.runner.tools.mcp.server import build_mcp_server

from tests.unit._toolsets import EchoToolSet, FailingTool, MultiToolSet, UnsafeToolSet


def test_build_mcp_server_registers_each_tool(capsys):
    registry = ToolRegistry()
    registry.register_toolset(MultiToolSet, module="t", expose_mcp=True)

    server = build_mcp_server("multi", registry=registry)

    tool_map = asyncio.run(server.get_tools())
    assert set(tool_map.keys()) == {"double", "shout"}
    err = capsys.readouterr().err
    assert "mcp.server.bound toolset=multi" in err
    assert "tools=double,shout" in err


def test_build_mcp_server_uses_custom_name() -> None:
    registry = ToolRegistry()
    registry.register_toolset(EchoToolSet, module="t", expose_mcp=True)

    server = build_mcp_server("echo", name="feedback-tools", registry=registry)

    assert server.name == "feedback-tools"


def test_build_mcp_server_unknown_toolset_systemexit(capsys):
    registry = ToolRegistry()
    with pytest.raises(SystemExit) as excinfo:
        build_mcp_server("missing", registry=registry)
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "reason=not-registered" in err


def test_build_mcp_server_unexposed_toolset_systemexit(capsys):
    registry = ToolRegistry()
    registry.register_toolset(UnsafeToolSet, module="t", expose_mcp=False)
    with pytest.raises(SystemExit) as excinfo:
        build_mcp_server("unsafe", registry=registry)
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "reason=not-exposed" in err


def test_in_process_echo_round_trip():
    from fastmcp import Client

    registry = ToolRegistry()
    registry.register_toolset(EchoToolSet, module="t", expose_mcp=True)
    server = build_mcp_server("echo", registry=registry)

    async def go():
        async with Client(server) as client:
            return await client.call_tool("echo", {"text": "hi"})

    result = asyncio.run(go())
    assert result.data == {"result": "hi"}


def test_in_process_tool_execution_error_is_tool_call_error():
    from fastmcp import Client
    from fastmcp.exceptions import ToolError

    registry = ToolRegistry()
    registry.register_toolset(FailingTool, module="t", expose_mcp=True)
    server = build_mcp_server("failing", registry=registry)

    async def go():
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool("boom", {"text": "hi"})

    asyncio.run(go())


def test_server_module_does_not_import_fastmcp_at_top():
    """The agents.runner.tools.mcp.server module must be importable without fastmcp."""
    import subprocess

    code = (
        "import sys\n"
        "import agents.runner.tools.mcp.server\n"
        "assert 'fastmcp' not in sys.modules, sorted(m for m in sys.modules if 'fastmcp' in m)\n"
    )
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
    )
