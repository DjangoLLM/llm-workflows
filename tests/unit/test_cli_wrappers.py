from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from agents.cli_wrappers import (
    AuthenticationError,
    BaseCLIWrapper,
    CLIEvent,
    CLIResponse,
    CodexCLIWrapper,
    EventAggregator,
    GeminiCLIWrapper,
    OutputFormat,
    ResilientCLIWrapper,
    WorkflowSession,
)


class DummyWrapper(BaseCLIWrapper):
    def build_command(self, prompt: str, output_format: OutputFormat, **kwargs):
        return ["dummy", prompt, output_format.value]

    def parse_event(self, line: str):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        return CLIEvent(
            type=payload.get("type", "unknown"),
            data=payload,
            raw=line,
            timestamp=0.0,
        )

    def _extract_usage(self, events):
        return None


class FakeStream:
    def __init__(self, lines: list[str]):
        self._lines = [line.encode("utf-8") + b"\n" for line in lines]

    async def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)


class FakeStdin:
    def __init__(self):
        self.written = b""
        self.drained = False
        self.closed = False

    def write(self, data: bytes) -> None:
        self.written += data

    async def drain(self) -> None:
        self.drained = True

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(
        self,
        stdout_lines: list[str],
        stderr_lines: list[str],
        wait_result: int = 0,
        with_stdin: bool = False,
    ):
        self.stdout = FakeStream(stdout_lines)
        self.stderr = FakeStream(stderr_lines)

        self.stdin = FakeStdin() if with_stdin else None
        self._wait_result = wait_result
        self.killed = False

    async def wait(self) -> int:
        return self._wait_result

    def kill(self) -> None:
        self.killed = True


class SlowWaitProcess(FakeProcess):
    async def wait(self) -> int:
        await asyncio.sleep(0.2)
        return 0


class FakeExecWrapper:
    def __init__(self, responses: list[CLIResponse]):
        self.responses = responses
        self.calls = 0

    async def execute(self, prompt: str, **kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        return response


class FakeResumeWrapper(FakeExecWrapper):
    async def resume(self, prompt: str, **kwargs):
        return await self.execute(prompt, **kwargs)


def test_codex_build_command_variants() -> None:
    wrapper = CodexCLIWrapper(working_dir=Path("."))

    cmd = wrapper.build_command("hello", OutputFormat.STREAM_JSON, sandbox="workspace-write")
    assert cmd[:2] == ["codex", "exec"]
    assert "--json" in cmd
    assert "--sandbox" in cmd

    resume_cmd = wrapper.build_command(
        "follow-up",
        OutputFormat.JSON,
        resume_session="session-123",
        full_auto=True,
    )
    assert resume_cmd[:3] == ["codex", "exec", "resume"]
    assert "session-123" in resume_cmd
    assert "--full-auto" in resume_cmd


def test_codex_build_command_text_resume_last_and_schema() -> None:
    wrapper = CodexCLIWrapper(api_key="token", working_dir=Path("."))

    cmd = wrapper.build_command(
        "hello",
        OutputFormat.TEXT,
        output_schema=Path("schema.json"),
        resume_last=True,
    )

    assert wrapper.env_vars["CODEX_API_KEY"] == "token"
    assert cmd[:3] == ["codex", "exec", "resume"]
    assert "--last" in cmd
    assert "--json" not in cmd
    assert "--output-schema" in cmd


def test_codex_parse_event_and_usage() -> None:
    wrapper = CodexCLIWrapper(working_dir=Path("."))

    event = wrapper.parse_event('{"type":"turn.completed","usage":{"input_tokens":10}}')
    assert event is not None
    assert wrapper._extract_usage([event]) == {"input_tokens": 10}
    assert wrapper._extract_usage([]) is None
    assert wrapper.parse_event("not-json") is None


def test_gemini_build_parse_and_usage() -> None:
    wrapper = GeminiCLIWrapper(api_key="gk", project="proj", working_dir=Path("."))

    cmd = wrapper.build_command(
        "hello",
        OutputFormat.STREAM_JSON,
        approval_mode="strict",
        allowed_tools=["read_file", "list"],
        model="gemini-2.5-pro",
    )
    assert cmd[0] == "gemini"
    assert "--approval-mode" in cmd
    assert "strict" in cmd
    assert "--allowed-tools" in cmd
    assert wrapper.env_vars["GEMINI_API_KEY"] == "gk"
    assert wrapper.env_vars["GOOGLE_CLOUD_PROJECT"] == "proj"

    json_cmd = wrapper.build_command("prompt", OutputFormat.JSON)
    assert "--output-format" in json_cmd
    assert "json" in json_cmd

    text_cmd = wrapper.build_command("prompt", OutputFormat.TEXT, allowed_tools=None)
    assert "--output-format" not in text_cmd

    done = wrapper.parse_event('{"done":true,"statistics":{"inputTokens":2}}')
    assert done is not None
    assert done.type == "done"
    assert wrapper._extract_usage([done]) == {"inputTokens": 2}
    assert wrapper._extract_usage([]) is None

    assert wrapper.parse_event('{"content":"x"}').type == "content"
    assert wrapper.parse_event('{"toolCall":{}}').type == "tool_call"
    assert wrapper.parse_event('{"toolResult":{}}').type == "tool_result"
    assert wrapper.parse_event('{"error":"bad"}').type == "error"
    assert wrapper.parse_event("not-json") is None


def test_event_aggregator_tracks_tools_and_file_changes() -> None:
    aggregator = EventAggregator()

    aggregator.process_event(CLIEvent(type="tool_call", data={"name": "read_file"}, raw="", timestamp=0.0))
    aggregator.process_event(CLIEvent(type="toolCall", data={"name": "legacy"}, raw="", timestamp=0.0))
    aggregator.process_event(
        CLIEvent(
            type="item.completed",
            data={"item": {"type": "file_change", "path": "foo.py"}},
            raw="",
            timestamp=0.0,
        )
    )
    aggregator.process_event(
        CLIEvent(
            type="item.completed",
            data={"item": {"type": "other", "path": "ignored.py"}},
            raw="",
            timestamp=0.0,
        )
    )

    summary = aggregator.get_summary()
    assert summary["tool_calls"] == 2
    assert summary["files_changed"] == 1


def test_base_execute_collects_stream_and_stderr(monkeypatch) -> None:
    wrapper = DummyWrapper(timeout=5)
    process = FakeProcess(
        stdout_lines=[
            '{"type":"thread.started","thread_id":"thread-1"}',
            '{"type":"session.started","session_id":"session-2"}',
            '{"type":"content","content":"hello"}',
            '{"type":"item.completed","item":{"text":"item-text"}}',
            '{"type":"item.completed","item":{"content":"item-content"}}',
            'not-json',
            '{"type":"done","text":"world"}',
        ],
        stderr_lines=["warn line"],
        wait_result=0,
    )

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr("agents.cli_wrappers.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    response = asyncio.run(wrapper.execute("prompt", output_format=OutputFormat.STREAM_JSON))

    assert response.exit_code == 0
    assert response.session_id == "session-2"
    assert "hello" in response.final_output
    assert "item-text" in response.final_output
    assert "item-content" in response.final_output
    assert "world" in response.final_output
    assert "warn line" in response.stderr


def test_base_execute_text_mode_with_stdin(monkeypatch) -> None:
    wrapper = DummyWrapper(timeout=5)
    process = FakeProcess(
        stdout_lines=["line one", "line two"],
        stderr_lines=[],
        wait_result=0,
        with_stdin=True,
    )

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr("agents.cli_wrappers.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    response = asyncio.run(
        wrapper.execute(
            "prompt",
            output_format=OutputFormat.TEXT,
            stdin_data="hello stdin",
        )
    )

    assert response.final_output.splitlines() == ["line one", "line two"]
    assert process.stdin.written == b"hello stdin"
    assert process.stdin.drained is True
    assert process.stdin.closed is True


def test_base_execute_times_out_and_kills_process(monkeypatch) -> None:
    wrapper = DummyWrapper(timeout=0)
    process = SlowWaitProcess(stdout_lines=[], stderr_lines=[])

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr("agents.cli_wrappers.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    with pytest.raises(TimeoutError, match="timed out"):
        asyncio.run(wrapper.execute("prompt", output_format=OutputFormat.STREAM_JSON))

    assert process.killed is True


def test_resilient_wrapper_retries_and_succeeds() -> None:
    wrapper = FakeExecWrapper(
        responses=[
            CLIResponse(final_output="", events=[], session_id=None, exit_code=1, usage=None, stderr="x"),
            CLIResponse(final_output="ok", events=[], session_id=None, exit_code=0, usage=None, stderr=""),
        ]
    )
    resilient = ResilientCLIWrapper(wrapper, max_retries=3, retry_delay=0)

    result = asyncio.run(resilient.execute_with_retry("prompt"))

    assert result.final_output == "ok"
    assert wrapper.calls == 2


def test_resilient_wrapper_raises_authentication_error() -> None:
    wrapper = FakeExecWrapper(
        responses=[
            CLIResponse(final_output="", events=[], session_id=None, exit_code=41, usage=None, stderr="auth"),
        ]
    )
    resilient = ResilientCLIWrapper(wrapper, max_retries=1, retry_delay=0)

    with pytest.raises(AuthenticationError):
        asyncio.run(resilient.execute_with_retry("prompt"))


def test_resilient_wrapper_raises_invalid_input_value_error() -> None:
    wrapper = FakeExecWrapper(
        responses=[
            CLIResponse(final_output="", events=[], session_id=None, exit_code=42, usage=None, stderr="bad"),
        ]
    )
    resilient = ResilientCLIWrapper(wrapper, max_retries=1, retry_delay=0)

    with pytest.raises(ValueError, match="Invalid input"):
        asyncio.run(resilient.execute_with_retry("prompt"))


def test_resilient_wrapper_retries_on_runtime_error() -> None:
    class ErrorWrapper:
        def __init__(self):
            self.calls = 0

        async def execute(self, _prompt: str, **_kwargs):
            self.calls += 1
            raise RuntimeError("boom")

    wrapper = ErrorWrapper()
    resilient = ResilientCLIWrapper(wrapper, max_retries=2, retry_delay=0)

    with pytest.raises(RuntimeError, match="Failed after 2 attempts"):
        asyncio.run(resilient.execute_with_retry("prompt"))


def test_resilient_wrapper_retries_on_timeout_error() -> None:
    class TimeoutWrapper:
        def __init__(self):
            self.calls = 0

        async def execute(self, _prompt: str, **_kwargs):
            self.calls += 1
            raise asyncio.TimeoutError("slow")

    wrapper = TimeoutWrapper()
    resilient = ResilientCLIWrapper(wrapper, max_retries=2, retry_delay=0)

    with pytest.raises(RuntimeError, match="Failed after 2 attempts"):
        asyncio.run(resilient.execute_with_retry("prompt"))


def test_resilient_wrapper_raises_after_all_retries() -> None:
    wrapper = FakeExecWrapper(
        responses=[
            CLIResponse(final_output="", events=[], session_id=None, exit_code=2, usage=None, stderr="err"),
            CLIResponse(final_output="", events=[], session_id=None, exit_code=2, usage=None, stderr="err"),
        ]
    )
    resilient = ResilientCLIWrapper(wrapper, max_retries=2, retry_delay=0)

    with pytest.raises(RuntimeError, match="Failed after 2 attempts"):
        asyncio.run(resilient.execute_with_retry("prompt"))


def test_workflow_session_uses_resume_after_first_step() -> None:
    wrapper = FakeResumeWrapper(
        responses=[
            CLIResponse(final_output="one", events=[], session_id="s1", exit_code=0, usage=None, stderr=""),
            CLIResponse(final_output="two", events=[], session_id="s1", exit_code=0, usage=None, stderr=""),
        ]
    )
    session = WorkflowSession(wrapper)

    first = asyncio.run(session.execute_step("step 1"))
    second = asyncio.run(session.execute_step("step 2"))

    assert first.final_output == "one"
    assert second.final_output == "two"
    assert "Step 1" in session.get_full_transcript()


def test_codex_resume_and_execute_with_stdin_delegate_to_execute(monkeypatch) -> None:
    wrapper = CodexCLIWrapper(working_dir=Path("."))
    captured = []

    async def fake_execute(prompt, **kwargs):
        captured.append((prompt, kwargs))
        return CLIResponse(final_output="ok", events=[], session_id="s", exit_code=0, usage=None, stderr="")

    monkeypatch.setattr(wrapper, "execute", fake_execute)

    asyncio.run(wrapper.resume("hello", session_id="sid"))
    asyncio.run(wrapper.execute_with_stdin("world", "stdin-text"))

    assert captured[0][1]["resume_session"] == "sid"
    assert captured[1][1]["stdin_data"] == "stdin-text"
