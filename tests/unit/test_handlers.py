from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured

from agents.handlers import trigger_transcript_post_create_workflow


def test_trigger_callback_requires_dotted_path(settings) -> None:
    settings.AGENTS_TRANSCRIPT_READY_CALLBACK = ""

    with pytest.raises(ImproperlyConfigured, match="must be a dotted callback path"):
        trigger_transcript_post_create_workflow(1, "text")


def test_trigger_callback_invokes_configured_target(settings) -> None:
    settings.AGENTS_TRANSCRIPT_READY_CALLBACK = "agents.tests.support.helpers.mock_transcript_callback"

    run_id = trigger_transcript_post_create_workflow(9, "hello world")

    assert run_id == "run-9-11"
