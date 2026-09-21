from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from agents.core.codex_runner import (
    CodexConfigurationError,
    CodexExecutionError,
    CodexRunner,
)
from agents.core.codex_schema import CodexResponseValidationError


class _Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    count: int


def _config(**overrides: Any) -> SimpleNamespace:
    values = {
        "instructions": "Return an answer.",
        "model": None,
        "settings": None,
        "result_type": _Answer,
        "tools": None,
        "toolsets": None,
        "extra_kwargs": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_from_config_accepts_defaults() -> None:
    runner = CodexRunner.from_config(_config())

    assert runner.model is None
    assert runner.working_dir == Path.cwd().resolve()
    assert runner.timeout_seconds == 300.0
    assert runner.schema["additionalProperties"] is False
    assert runner.schema["required"] == ["message", "count"]


def test_from_config_accepts_supported_options(tmp_path: Path) -> None:
    runner = CodexRunner.from_config(
        _config(
            model="gpt-test",
            extra_kwargs={
                "codex_working_dir": tmp_path,
                "codex_timeout_seconds": 1.5,
            },
        )
    )

    assert runner.model == "gpt-test"
    assert runner.working_dir == tmp_path.resolve()
    assert runner.timeout_seconds == 1.5


def test_from_config_rejects_unknown_options() -> None:
    with pytest.raises(CodexConfigurationError, match="unknown option 'api_key'"):
        CodexRunner.from_config(
            _config(extra_kwargs={"resume_session": "secret", "api_key": "secret"})
        )


@pytest.mark.parametrize("model", ["", "   ", object()])
def test_from_config_rejects_invalid_model(model: object) -> None:
    with pytest.raises(CodexConfigurationError, match="nonempty string or None"):
        CodexRunner.from_config(_config(model=model))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("settings", {}, "model settings"),
        ("tools", [lambda: None], "framework tools"),
        ("toolsets", ["default"], "framework toolsets"),
    ],
)
def test_from_config_rejects_unsupported_framework_configuration(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(CodexConfigurationError, match=message):
        CodexRunner.from_config(_config(**{field: value}))


@pytest.mark.parametrize("working_dir", [None, 7])
def test_from_config_rejects_non_path_working_directory(working_dir: object) -> None:
    with pytest.raises(CodexConfigurationError, match="existing directory"):
        CodexRunner.from_config(
            _config(extra_kwargs={"codex_working_dir": working_dir})
        )


def test_from_config_rejects_missing_or_nondirectory_working_directory(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("content", encoding="utf-8")

    for invalid_path in (tmp_path / "missing", file_path):
        with pytest.raises(CodexConfigurationError, match="existing directory"):
            CodexRunner.from_config(
                _config(extra_kwargs={"codex_working_dir": invalid_path})
            )


@pytest.mark.parametrize(
    "timeout", [True, False, 0, -1, math.inf, -math.inf, math.nan, "10", None]
)
def test_from_config_rejects_invalid_timeout(timeout: object) -> None:
    with pytest.raises(CodexConfigurationError, match="positive finite number"):
        CodexRunner.from_config(
            _config(extra_kwargs={"codex_timeout_seconds": timeout})
        )


class _FakeCodexWrapper:
    final_bytes: bytes | None = b'{"message":"ok","count":2}'
    exit_code = 0
    event_types: list[str] = []
    raised_error: Exception | None = None
    constructor_kwargs: dict[str, object] = {}
    execute_kwargs: dict[str, object] = {}

    def __init__(self, **kwargs: object) -> None:
        type(self).constructor_kwargs = kwargs

    async def execute(self, prompt: str, output_format: object, **kwargs: object):
        type(self).execute_kwargs = {
            "prompt": prompt,
            "output_format": output_format,
            **kwargs,
        }
        if self.raised_error is not None:
            raise self.raised_error
        final_path = Path(str(kwargs["output_last_message"]))
        if self.final_bytes is not None:
            final_path.write_bytes(self.final_bytes)
        events = [SimpleNamespace(type=event_type) for event_type in self.event_types]
        return SimpleNamespace(exit_code=self.exit_code, events=events)


@pytest.fixture
def fake_codex(monkeypatch) -> type[_FakeCodexWrapper]:
    class FakeCodexWrapper(_FakeCodexWrapper):
        pass

    monkeypatch.setattr(
        "agents.core.codex_runner.CodexCLIWrapper", FakeCodexWrapper
    )
    return FakeCodexWrapper


@pytest.mark.asyncio
async def test_run_uses_fresh_wrapper_and_validates_final_file(
    fake_codex: type[_FakeCodexWrapper], tmp_path: Path
) -> None:
    runner = CodexRunner.from_config(
        _config(
            model="gpt-test",
            extra_kwargs={
                "codex_working_dir": tmp_path,
                "codex_timeout_seconds": 4,
            },
        )
    )

    result = await runner.run({"request": "hello"})

    assert result.output == _Answer(message="ok", count=2)
    assert fake_codex.constructor_kwargs == {
        "working_dir": tmp_path.resolve(),
        "timeout": 4.0,
    }
    assert fake_codex.execute_kwargs["prompt"] == "-"
    assert fake_codex.execute_kwargs["model"] == "gpt-test"
    assert fake_codex.execute_kwargs["sandbox"] == "read-only"
    assert fake_codex.execute_kwargs["full_auto"] is False
    assert "Return an answer." in str(fake_codex.execute_kwargs["stdin_data"])
    assert '"request": "hello"' in str(fake_codex.execute_kwargs["stdin_data"])


@pytest.mark.asyncio
async def test_run_rejects_nonzero_exit_without_exposing_process_output(
    fake_codex: type[_FakeCodexWrapper], tmp_path: Path
) -> None:
    fake_codex.exit_code = 17
    fake_codex.final_bytes = b'{"secret":"raw response"}'
    runner = CodexRunner.from_config(
        _config(extra_kwargs={"codex_working_dir": tmp_path})
    )

    with pytest.raises(CodexExecutionError, match="status 17") as exc_info:
        await runner.run({"password": "input-secret"})

    message = str(exc_info.value)
    assert "raw response" not in message
    assert "input-secret" not in message


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["error", "turn.failed", "item.failed"])
async def test_run_rejects_terminal_failure_events(
    fake_codex: type[_FakeCodexWrapper], tmp_path: Path, event_type: str
) -> None:
    fake_codex.event_types = [event_type]
    runner = CodexRunner.from_config(
        _config(extra_kwargs={"codex_working_dir": tmp_path})
    )

    with pytest.raises(CodexExecutionError, match="terminal failure event"):
        await runner.run()


@pytest.mark.asyncio
async def test_run_rejects_missing_final_file(
    fake_codex: type[_FakeCodexWrapper], tmp_path: Path
) -> None:
    fake_codex.final_bytes = None
    runner = CodexRunner.from_config(
        _config(extra_kwargs={"codex_working_dir": tmp_path})
    )

    with pytest.raises(CodexExecutionError, match="file is missing"):
        await runner.run()


@pytest.mark.asyncio
async def test_run_rejects_empty_final_file(
    fake_codex: type[_FakeCodexWrapper], tmp_path: Path
) -> None:
    fake_codex.final_bytes = b""
    runner = CodexRunner.from_config(
        _config(extra_kwargs={"codex_working_dir": tmp_path})
    )

    with pytest.raises(CodexExecutionError, match="file is empty"):
        await runner.run()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "message"),
    [
        (b"refused: cannot comply", "not valid JSON"),
        (b'{"message":"ok","count":"2"}', "strict validation"),
        (b'{"message":"raw-secret","count":2,"extra":true}', "strict validation"),
    ],
)
async def test_run_rejects_malformed_or_strict_invalid_output_without_echoing_it(
    fake_codex: type[_FakeCodexWrapper],
    tmp_path: Path,
    response: bytes,
    message: str,
) -> None:
    fake_codex.final_bytes = response
    runner = CodexRunner.from_config(
        _config(extra_kwargs={"codex_working_dir": tmp_path})
    )

    with pytest.raises(CodexResponseValidationError, match=message) as exc_info:
        await runner.run()

    assert "raw-secret" not in str(exc_info.value)
    assert "refused: cannot comply" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_run_sanitizes_wrapper_failures(
    fake_codex: type[_FakeCodexWrapper], tmp_path: Path
) -> None:
    fake_codex.raised_error = RuntimeError("stderr-secret and raw prompt")
    runner = CodexRunner.from_config(
        _config(extra_kwargs={"codex_working_dir": tmp_path})
    )

    with pytest.raises(
        CodexExecutionError, match="launch or execution failed"
    ) as exc_info:
        await runner.run({"password": "input-secret"})

    message = str(exc_info.value)
    assert "stderr-secret" not in message
    assert "raw prompt" not in message
    assert "input-secret" not in message
