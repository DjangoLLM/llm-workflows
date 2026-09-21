"""Jev execution backend: one TypeSafe request answers the config's choice heads over the run's state.

Every answer is validated against the ids the question offered before it is returned, so a
malformed or out-of-vocabulary choice raises instead of flowing into a workflow.
"""
from __future__ import annotations

import asyncio
import math
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import httpx

URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
_client = httpx.Client(timeout=25)


def post_json(body: Mapping[str, Any], key: str) -> dict:
    for attempt in range(3):
        try:
            response = _client.post(URL, json=body, headers={"Authorization": f"Bearer {key}"})
        except httpx.HTTPError:
            raise RuntimeError("Jev connection failed; no decision made.") from None
        if response.status_code in {429, 503, 529} and attempt < 2:
            time.sleep(0.5 * 2**attempt)
            continue
        if response.is_error:
            raise RuntimeError(f"Jev returned HTTP {response.status_code}; no decision made.")
        return response.json()
    raise RuntimeError("Jev unavailable")


def validate_choice(answer: Any, ids: set[str]) -> dict:
    """A choice must be one of the offered ids, with a proper distribution over exactly those ids."""
    try:
        probabilities = answer["probabilities"]
        numbers = [*probabilities.values(), answer["confidence"]]
        valid = (
            answer["choice"] in ids
            and set(probabilities) == set(ids)
            and all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in numbers)
            and abs(sum(probabilities.values()) - 1) < 0.02
            and probabilities[answer["choice"]] >= max(probabilities.values()) - 1e-6
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("Invalid Jev answer; no decision made.")
    return answer


def build_questions(instructions: str, questions: Mapping[str, Mapping[str, Any]]) -> dict:
    """Fill each head with the config's instructions as its goal unless the head brought its own."""
    return {
        head: {"type": "choice", "instructions": {"goal": instructions}, **question}
        for head, question in questions.items()
    }


def decide(*, instructions: str, questions: Mapping[str, Mapping[str, Any]], model: str | None, state: Any) -> dict:
    """Ask Jev every head at once; return validated choices keyed by head."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY is not set; Jev backend cannot run.")
    heads = build_questions(instructions, questions)
    result = post_json({"model": model or DEFAULT_MODEL, "state": state or {}, "questions": heads}, key)
    answers = result.get("answers", {})
    choices, confidence, probabilities = {}, {}, {}
    for head, question in heads.items():
        answer = validate_choice(answers.get(head, {}), set(question["criteria"]))
        choices[head] = answer["choice"]
        confidence[head] = answer["confidence"]
        probabilities[head] = answer["probabilities"]
    return {
        "choices": choices,
        "confidence": confidence,
        "probabilities": probabilities,
        "model": result.get("model"),
        "usage": result.get("usage", {}),
    }


@dataclass(slots=True)
class JevRunner:
    """Runner with the same run/run_sync surface as CodexRunner; the payload is Jev's observed state."""

    instructions: str
    questions: Mapping[str, Mapping[str, Any]]
    model: str | None = None

    @classmethod
    def from_config(cls, config: Any) -> JevRunner:
        return cls(instructions=config.instructions, questions=config.questions or {}, model=config.model)

    def run_sync(self, input_payload: Any = None) -> SimpleNamespace:
        output = decide(instructions=self.instructions, questions=self.questions, model=self.model, state=input_payload)
        return SimpleNamespace(output=output)

    async def run(self, input_payload: Any = None) -> SimpleNamespace:
        return await asyncio.to_thread(self.run_sync, input_payload)
