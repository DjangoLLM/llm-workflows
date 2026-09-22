"""Django app config for the feedback demo."""

from __future__ import annotations

from django.apps import AppConfig


class FeedbackConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "feedback"

    def ready(self) -> None:
        from agents.runner.tools import register_toolset

        from .pipelines import register_feedback_pipeline
        from .tools import EchoToolSet

        register_toolset(
            EchoToolSet, module=self.label, expose_mcp=True
        )
        register_feedback_pipeline()
