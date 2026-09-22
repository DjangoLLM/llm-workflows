from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from agents.inferences.agents import AgentDefinition
from agents.runner import Agent


class _Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str
    count: int


def _install_fake_codex(tmp_path: Path, monkeypatch) -> Path:
    executable = tmp_path / "codex"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

args = sys.argv[1:]
stdin_text = sys.stdin.read()
schema_path = pathlib.Path(args[args.index("--output-schema") + 1])
final_path = pathlib.Path(args[args.index("--output-last-message") + 1])
pathlib.Path(os.environ["CODEX_CAPTURE_PATH"]).write_text(json.dumps({
    "args": args,
    "stdin": stdin_text,
    "schema": json.loads(schema_path.read_text()),
    "schema_path": str(schema_path),
    "final_path": str(final_path),
}))
final_path.write_text('{"message":"typed","count":2}')
print('{"type":"item.completed","item":{"text":"commentary must be ignored"}}')
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    capture_path = tmp_path / "capture.json"
    monkeypatch.setenv("CODEX_CAPTURE_PATH", str(capture_path))
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    return capture_path


def test_codex_agent_run_sync_returns_validated_model_and_cleans_files(
    tmp_path: Path, monkeypatch
) -> None:
    capture_path = _install_fake_codex(tmp_path, monkeypatch)
    agent = Agent(definition=AgentDefinition(
        instructions="Return the requested typed answer.",
        execution_backend="codex_cli",
        model="test-model",
        result_type=_Answer,
        extra_kwargs={"codex_working_dir": tmp_path},
    ))
    result = agent.run_sync({"question": "two"})
    assert result.output == _Answer(message="typed", count=2)
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    assert capture["args"][-1] == "-"
    assert "--json" in capture["args"]
    assert capture["args"][capture["args"].index("--sandbox") + 1] == "read-only"
    assert capture["args"][capture["args"].index("--model") + 1] == "test-model"
    assert "--full-auto" not in capture["args"]
    assert "Return the requested typed answer." in capture["stdin"]
    assert '{"question": "two"}' in capture["stdin"]
    assert capture["schema"]["additionalProperties"] is False
    assert set(capture["schema"]["required"]) == {"message", "count"}
    assert not Path(capture["schema_path"]).exists()
    assert not Path(capture["final_path"]).exists()


def test_codex_agent_run_async_returns_validated_model(
    tmp_path: Path, monkeypatch
) -> None:
    _install_fake_codex(tmp_path, monkeypatch)
    agent = Agent(
        instructions="Return the requested typed answer.",
        execution_backend="codex_cli",
        result_type=_Answer,
        extra_kwargs={"codex_working_dir": tmp_path},
    )

    result = asyncio.run(agent.run({"question": "two"}))

    assert result.output == _Answer(message="typed", count=2)


def test_codex_agent_concurrent_calls_isolate_response_files(
    tmp_path: Path, monkeypatch
) -> None:
    executable = tmp_path / "codex"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

args = sys.argv[1:]
stdin_text = sys.stdin.read()
payload = json.loads(stdin_text.split("<input-json>\\n", 1)[1].split("\\n</input-json>", 1)[0])
schema_path = pathlib.Path(args[args.index("--output-schema") + 1])
final_path = pathlib.Path(args[args.index("--output-last-message") + 1])
pathlib.Path(os.environ["CODEX_CAPTURE_DIR"], payload["question"] + ".json").write_text(json.dumps({
    "schema_path": str(schema_path), "final_path": str(final_path)
}))
final_path.write_text(json.dumps({"message": payload["question"], "count": 1}))
print('{"type":"turn.completed"}')
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("CODEX_CAPTURE_DIR", str(tmp_path))
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    agent = Agent(
        instructions="Return the question.",
        execution_backend="codex_cli",
        result_type=_Answer,
        extra_kwargs={"codex_working_dir": tmp_path},
    )

    async def run_both():
        return await asyncio.gather(
            agent.run({"question": "first"}),
            agent.run({"question": "second"}),
        )

    first, second = asyncio.run(run_both())

    assert first.output.message == "first"
    assert second.output.message == "second"
    captures = [
        json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("first", "second")
    ]
    assert captures[0]["schema_path"] != captures[1]["schema_path"]
    assert captures[0]["final_path"] != captures[1]["final_path"]
    assert all(not Path(item["schema_path"]).exists() for item in captures)
    assert all(not Path(item["final_path"]).exists() for item in captures)
