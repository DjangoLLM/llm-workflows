from __future__ import annotations

import agents
from agents.apps import AgentsConfig


def test_agents_config_ready_wires_registrations(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr("agents.runner.agent_definition_registrations.register_all_agent_definitions", lambda: calls.append("definition"))
    monkeypatch.setattr("agents.runner.step_registrations.register_all_steps", lambda: calls.append("steps"))
    monkeypatch.setattr("agents.catalog.agent_definition_catalog.AgentDefinitionCatalog.validate_registry", lambda: calls.append("validate_config"))
    monkeypatch.setattr("agents.catalog.choice_definition_catalog.ChoiceDefinitionCatalog.validate_registry", lambda: calls.append("validate_choice_definition"))
    monkeypatch.setattr("agents.catalog.step_catalog.StepCatalog.validate_registry", lambda: calls.append("validate_step"))

    app = AgentsConfig("agents", agents)
    app.ready()

    assert calls == ["definition", "steps", "validate_config", "validate_choice_definition", "validate_step"]
