from __future__ import annotations

from unittest import mock

import pytest

from agents.adapters.tools.mcp.runner import run


def test_runner_routes_stdio_without_network_options(monkeypatch) -> None:
    server = mock.Mock()
    build_server = mock.Mock(return_value=server)
    monkeypatch.setattr("agents.adapters.tools.mcp.runner.build_mcp_server", build_server)

    run("echo", transport="stdio")

    build_server.assert_called_once_with("echo", registry=mock.ANY)
    server.run.assert_called_once_with(transport="stdio")


def test_runner_forwards_custom_server_name(monkeypatch) -> None:
    server = mock.Mock()
    build_server = mock.Mock(return_value=server)
    monkeypatch.setattr("agents.adapters.tools.mcp.runner.build_mcp_server", build_server)

    run("echo", name="feedback-tools")

    build_server.assert_called_once_with(
        "echo",
        name="feedback-tools",
        registry=mock.ANY,
    )


@pytest.mark.parametrize("transport", ["http", "sse"])
def test_runner_forwards_network_transport_options(monkeypatch, transport: str) -> None:
    server = mock.Mock()
    monkeypatch.setattr(
        "agents.adapters.tools.mcp.runner.build_mcp_server",
        mock.Mock(return_value=server),
    )

    run("echo", transport=transport, host="0.0.0.0", port=8765)

    server.run.assert_called_once_with(
        transport=transport,
        host="0.0.0.0",
        port=8765,
    )


@pytest.mark.parametrize("transport", ["http", "sse"])
def test_runner_requires_port_for_network_transports(
    capsys,
    transport: str,
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        run("echo", transport=transport)

    assert excinfo.value.code == 2
    assert f"transport={transport} reason=port-required" in capsys.readouterr().err


def test_runner_refuses_unknown_transport(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        run("echo", transport="websocket")

    assert excinfo.value.code == 2
    assert "transport=websocket reason=unknown-transport" in capsys.readouterr().err
