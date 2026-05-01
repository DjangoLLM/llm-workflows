"""Django app config for the feedback demo."""

from __future__ import annotations

from django.apps import AppConfig


class FeedbackConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "feedback"

    def ready(self) -> None:
        from .pipelines import register_feedback_pipeline

        register_feedback_pipeline()
