from __future__ import annotations

import pytest

import agents


def test_agents_lazy_exports_resolve_known_symbols() -> None:
    assert agents.Agent is not None
    assert agents.AgentConfig is not None
    assert agents.ManagedAgent is not None
    assert agents.AgentRunStatus is not None
    assert agents.run_agent is not None


def test_agents_lazy_exports_reject_unknown_symbol() -> None:
    with pytest.raises(AttributeError):
        getattr(agents, "DOES_NOT_EXIST")
