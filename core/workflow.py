"""Author-facing workflow definition and registry."""

from __future__ import annotations

from typing import ClassVar

from agents.core.step import Step


class Workflow:
    """A named composition of registered step definitions."""

    name: ClassVar[str] = ""
    steps: ClassVar[dict[str, type[Step]]] = {}


class WorkflowRegistry:
    """Registry populated by target applications during startup."""

    _workflows: dict[str, type[Workflow]] = {}
    _pipelines = _workflows

    @classmethod
    def register(cls, workflow_cls: type[Workflow]) -> None:
        if not workflow_cls.name:
            raise ValueError(
                f"Workflow {workflow_cls.__name__} must have a 'name'."
            )
        cls._workflows[workflow_cls.name] = workflow_cls

    @classmethod
    def get(cls, name: str) -> type[Workflow]:
        if name not in cls._workflows:
            raise ValueError(f"Workflow '{name}' not found in registry.")
        return cls._workflows[name]


def register_workflow(workflow_cls: type[Workflow]) -> None:
    """Register a workflow definition with the default registry."""

    WorkflowRegistry.register(workflow_cls)


__all__ = ("Workflow", "WorkflowRegistry", "register_workflow")
