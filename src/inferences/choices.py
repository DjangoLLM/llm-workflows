"""Public choice definition and catalog binding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal, Mapping

from agents.core.inference.definition import Definition
from agents.inferences.agents import AgentDefinition

if TYPE_CHECKING:
    from agents.catalog.choice_definition_catalog import ChoiceDefinitionCatalog


@dataclass(frozen=True, slots=True)
class ChoiceDefinition(Definition):
    """Describe a bounded decision without executing it."""

    question: str
    criteria: str
    input_type: type[Any]
    result_type: type[Any]
    candidates: Mapping[str, Any] | None = None
    candidate_type: type[Any] | None = None
    selection: Literal["single", "multiple"] = "single"
    allow_no_match: bool = False
    evaluator: AgentDefinition | Callable[..., Any] | None = None

    def __post_init__(self) -> None:
        if not self.question.strip() or not self.criteria.strip():
            raise ValueError("Choice question and criteria must be non-empty")
        if self.selection not in {"single", "multiple"}:
            raise ValueError("Choice selection must be 'single' or 'multiple'")
        if self.candidates is None and self.candidate_type is None:
            raise ValueError("Declare fixed candidates or a candidate_type")
        if self.candidates is not None:
            if not self.candidates:
                raise ValueError("Fixed candidates must be non-empty")
            if any(not isinstance(key, str) or not key.strip() for key in self.candidates):
                raise ValueError("Candidate identifiers must be non-empty strings")
        for name in ("input_type", "result_type", "candidate_type"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, type):
                raise TypeError(f"{name} must be a type")

    @classmethod
    def _get_catalog(cls) -> type[ChoiceDefinitionCatalog]:
        from agents.catalog.choice_definition_catalog import ChoiceDefinitionCatalog

        return ChoiceDefinitionCatalog


__all__ = ("ChoiceDefinition",)
