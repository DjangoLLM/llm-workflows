from __future__ import annotations

import agents
from agents.apps import AgentsConfig


def test_agents_config_ready_wires_registrations(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr("agents.core.agent_config_registrations.register_all_agent_configs", lambda: calls.append("config"))
    monkeypatch.setattr("agents.core.step_registrations.register_all_steps", lambda: calls.append("steps"))
    monkeypatch.setattr("agents.core.agent_config_catalog.AgentConfigCatalog.validate_registry", lambda: calls.append("validate_config"))
    monkeypatch.setattr("agents.core.step_catalog.StepCatalog.validate_registry", lambda: calls.append("validate_step"))

    app = AgentsConfig("agents", agents)
    app.ready()

    assert calls == ["config", "steps", "validate_config", "validate_step"]
