from __future__ import annotations

import io

import pytest
from django.core.management import call_command

from agents.core.tools import default_registry

from tests.unit._toolsets import EchoToolSet, MultiToolSet, UnsafeToolSet


@pytest.fixture
def populated_default_registry():
    """Populate `default_registry` for the duration of a single test."""
    saved_toolsets = dict(default_registry._toolsets)
    saved_meta = dict(default_registry._toolset_meta)
    saved_tools = dict(default_registry._tools)

    default_registry._toolsets.clear()
    default_registry._toolset_meta.clear()
    default_registry._tools.clear()

    default_registry.register_toolset(EchoToolSet, module="demo", expose_mcp=True)
    default_registry.register_toolset(MultiToolSet, module="other", expose_mcp=True)
    default_registry.register_toolset(UnsafeToolSet, module="demo", expose_mcp=False)

    yield default_registry

    default_registry._toolsets.clear()
    default_registry._toolset_meta.clear()
    default_registry._tools.clear()
    default_registry._toolsets.update(saved_toolsets)
    default_registry._toolset_meta.update(saved_meta)
    default_registry._tools.update(saved_tools)


def test_list_toolsets_prints_all(populated_default_registry):
    buf = io.StringIO()
    call_command("list_toolsets", stdout=buf)
    lines = buf.getvalue().strip().splitlines()
    assert lines == [
        "echo\tdemo\texposed=true\ttools=echo",
        "multi\tother\texposed=true\ttools=shout,double",
        "unsafe\tdemo\texposed=false\ttools=whisper",
    ]


def test_list_toolsets_module_filter(populated_default_registry):
    buf = io.StringIO()
    call_command("list_toolsets", "--module", "demo", stdout=buf)
    lines = buf.getvalue().strip().splitlines()
    assert lines == [
        "echo\tdemo\texposed=true\ttools=echo",
        "unsafe\tdemo\texposed=false\ttools=whisper",
    ]


def test_list_toolsets_exposed_only(populated_default_registry):
    buf = io.StringIO()
    call_command("list_toolsets", "--exposed-only", stdout=buf)
    lines = buf.getvalue().strip().splitlines()
    assert "echo\tdemo\texposed=true\ttools=echo" in lines
    assert "multi\tother\texposed=true\ttools=shout,double" in lines
    assert not any("unsafe" in l for l in lines)


def test_list_toolsets_empty_registry_prints_nothing():
    buf = io.StringIO()
    call_command("list_toolsets", stdout=buf)
    assert buf.getvalue() == ""


def test_run_tools_mcp_refuses_unexposed_toolset(
    populated_default_registry, capsys
):
    with pytest.raises(SystemExit) as excinfo:
        call_command("run_tools_mcp", "--toolset", "unsafe")
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "reason=not-exposed" in err


def test_run_tools_mcp_refuses_unknown_toolset(populated_default_registry, capsys):
    with pytest.raises(SystemExit) as excinfo:
        call_command("run_tools_mcp", "--toolset", "missing")
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "reason=not-registered" in err


def test_run_tools_mcp_invokes_runner_with_defaults(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(toolset_name, *, transport, host, port, name, registry=None):
        captured["toolset"] = toolset_name
        captured["transport"] = transport
        captured["host"] = host
        captured["port"] = port
        captured["name"] = name

    monkeypatch.setattr("agents.core.tools.mcp.runner.run", fake_run)

    call_command("run_tools_mcp", "--toolset", "echo")

    assert captured == {
        "toolset": "echo",
        "transport": "stdio",
        "host": "127.0.0.1",
        "port": None,
        "name": None,
    }


def test_run_tools_mcp_passes_through_http_args(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(toolset_name, *, transport, host, port, name, registry=None):
        captured["toolset"] = toolset_name
        captured["transport"] = transport
        captured["host"] = host
        captured["port"] = port
        captured["name"] = name

    monkeypatch.setattr("agents.core.tools.mcp.runner.run", fake_run)

    call_command(
        "run_tools_mcp",
        "--toolset", "echo",
        "--transport", "http",
        "--host", "0.0.0.0",
        "--port", "9000",
        "--name", "echo-srv",
    )
    assert captured == {
        "toolset": "echo",
        "transport": "http",
        "host": "0.0.0.0",
        "port": 9000,
        "name": "echo-srv",
    }


def test_runner_refuses_http_without_port(populated_default_registry, capsys):
    from agents.core.tools.mcp.runner import run

    with pytest.raises(SystemExit) as excinfo:
        run("echo", transport="http", port=None)
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "reason=port-required" in err
