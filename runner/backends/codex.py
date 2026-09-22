"""Codex CLI execution backend."""

from __future__ import annotations

import asyncio
import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from coding_agents import CodexCLIWrapper, NonInteractivePolicy, OutputFormat
from coding_agents.errors import CodingAgentTimeout
from pydantic import BaseModel

from agents.runner.backends.codex_schema import (
    build_codex_output_schema,
    validate_codex_output,
)


class CodexConfigurationError(ValueError):
    """The Codex backend configuration is invalid."""


class CodexExecutionError(RuntimeError):
    """The Codex process could not produce a successful final response."""


class CodexTimeoutError(CodexExecutionError, TimeoutError):
    """The complete Codex invocation exceeded its deadline."""


@dataclass(frozen=True, slots=True)
class CodexRunResult:
    """The stable direct-Agent result contract for Codex inference."""

    output: BaseModel


class CodexRunner:
    """Run one fresh Codex CLI process for each inference call."""

    def __init__(
        self,
        *,
        instructions: str,
        result_type: type[BaseModel],
        model: str | None,
        working_dir: Path,
        timeout_seconds: float,
        schema: Mapping[str, Any],
    ) -> None:
        self.instructions = instructions
        self.result_type = result_type
        self.model = model
        self.working_dir = working_dir
        self.timeout_seconds = timeout_seconds
        self.schema = dict(schema)

    @classmethod
    def from_config(cls, config: Any) -> CodexRunner:
        """Validate all Codex-only configuration before any process launch."""

        if config.settings is not None:
            raise CodexConfigurationError("codex_cli does not support model settings")
        if _contains_items(config.tools):
            raise CodexConfigurationError("codex_cli does not support framework tools")
        if _contains_items(config.toolsets):
            raise CodexConfigurationError("codex_cli does not support framework toolsets")

        try:
            options = dict(config.extra_kwargs or {})
        except (TypeError, ValueError) as exc:
            raise CodexConfigurationError(
                "codex_cli extra_kwargs must be a mapping"
            ) from exc
        allowed = {"codex_working_dir", "codex_timeout_seconds"}
        unknown = sorted(set(options) - allowed)
        if unknown:
            raise CodexConfigurationError(
                f"codex_cli received unknown option {unknown[0]!r}"
            )

        model = config.model
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise CodexConfigurationError(
                "codex_cli model must be a nonempty string or None"
            )

        working_value = options.get("codex_working_dir", Path.cwd())
        try:
            working_dir = Path(working_value).expanduser().resolve()
        except (TypeError, ValueError, OSError) as exc:
            raise CodexConfigurationError(
                "codex_working_dir must identify an existing directory"
            ) from exc
        if not working_dir.is_dir():
            raise CodexConfigurationError(
                "codex_working_dir must identify an existing directory"
            )

        timeout = options.get("codex_timeout_seconds", 300)
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise CodexConfigurationError(
                "codex_timeout_seconds must be a positive finite number"
            )

        schema = build_codex_output_schema(config.result_type)
        return cls(
            instructions=config.instructions,
            result_type=config.result_type,
            model=model,
            working_dir=working_dir,
            timeout_seconds=float(timeout),
            schema=schema,
        )

    async def run(self, input_payload: Any = None) -> CodexRunResult:
        """Execute one isolated Codex call and validate only its final file."""

        try:
            serialized_input = json.dumps(input_payload)
        except (TypeError, ValueError) as exc:
            raise CodexConfigurationError(
                "codex_cli input payload must be JSON serializable"
            ) from exc

        prompt = (
            "<instructions>\n"
            f"{self.instructions}\n"
            "</instructions>\n"
            "<input-json>\n"
            f"{serialized_input}\n"
            "</input-json>\n"
        )
        policy = NonInteractivePolicy(
            interactive=False,
            allow_writes=False,
            auto_approve=False,
            output_format=OutputFormat.STREAM_JSON,
        )

        with tempfile.TemporaryDirectory(prefix="freedom-agents-codex-") as temp_dir:
            temp_path = Path(temp_dir).resolve()
            schema_path = temp_path / "schema.json"
            final_path = temp_path / "final-response.json"
            schema_path.write_text(json.dumps(self.schema), encoding="utf-8")

            wrapper = CodexCLIWrapper(
                working_dir=self.working_dir,
                timeout=self.timeout_seconds,
            )
            try:
                response = await wrapper.execute(
                    "-",
                    OutputFormat.STREAM_JSON,
                    stdin_data=prompt,
                    policy=policy,
                    model=self.model,
                    output_schema=schema_path,
                    output_last_message=final_path,
                    full_auto=False,
                    sandbox="read-only",
                )
            except asyncio.CancelledError:
                raise
            except CodingAgentTimeout as exc:
                raise CodexTimeoutError("Codex CLI invocation timed out") from exc
            except Exception as exc:
                raise CodexExecutionError("Codex CLI launch or execution failed") from exc

            if response.exit_code != 0:
                raise CodexExecutionError(
                    f"Codex CLI exited unsuccessfully with status {response.exit_code}"
                )
            if any(_is_terminal_failure(event.type) for event in response.events):
                raise CodexExecutionError("Codex CLI reported a terminal failure event")
            try:
                raw_response = final_path.read_bytes()
            except OSError as exc:
                raise CodexExecutionError("Codex final response file is missing") from exc
            if not raw_response:
                raise CodexExecutionError("Codex final response file is empty")

            output = validate_codex_output(self.result_type, raw_response)
            return CodexRunResult(output=output)

    def run_sync(self, input_payload: Any = None) -> CodexRunResult:
        """Synchronous wrapper around the cancellation-safe async execution path."""

        return asyncio.run(self.run(input_payload))


def _is_terminal_failure(event_type: str) -> bool:
    normalized = event_type.lower()
    return normalized in {"error", "failed", "failure", "turn.failed"} or normalized.endswith(
        ".failed"
    )


def _contains_items(value: Any) -> bool:
    if value is None:
        return False
    try:
        return bool(list(value))
    except TypeError as exc:
        raise CodexConfigurationError(
            "codex_cli tools and toolsets must be iterable"
        ) from exc
