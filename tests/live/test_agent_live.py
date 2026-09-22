from __future__ import annotations

import pytest

from agents.core import AgentConfig
from agents.runner import Agent


@pytest.mark.live
def test_agent_live_openai_execution() -> None:
    agent = Agent(
        config=AgentConfig(
            instructions="Return JSON with key ok=true.",
            model="gpt-5-mini",
        )
    )

    result = agent.run_sync({"input": "health-check"})

    assert result is not None
    output = getattr(result, "output", getattr(result, "data", None))
    assert output is not None
