from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agents.cli_wrappers import CodexCLIWrapper, GeminiCLIWrapper, OutputFormat


@pytest.mark.live
def test_codex_cli_wrapper_live_execution() -> None:
    wrapper = CodexCLIWrapper(api_key=None, working_dir=Path.cwd(), timeout=120)

    response = asyncio.run(
        wrapper.execute(
            prompt="Reply with exactly one word: PASS",
            output_format=OutputFormat.STREAM_JSON,
            sandbox="read-only",
        )
    )

    assert response.exit_code == 0
    assert response.final_output.strip()


@pytest.mark.live
def test_gemini_cli_wrapper_live_execution() -> None:
    wrapper = GeminiCLIWrapper(api_key=None, working_dir=Path.cwd(), timeout=120)

    response = asyncio.run(
        wrapper.execute(
            prompt="Reply with exactly one word: PASS",
            output_format=OutputFormat.STREAM_JSON,
            approval_mode="default",
            model="gemini-2.0-flash",
        )
    )

    assert response.exit_code == 0
    assert response.final_output.strip()
