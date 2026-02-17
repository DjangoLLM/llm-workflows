import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.dispatch import Signal
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

agent_run_completed = Signal()


def trigger_transcript_post_create_workflow(transcript_id: int, transcript_text: str) -> str:
    """
    Dispatch transcript workflow trigger via configurable callback path.

    :param transcript_id: Transcript primary key as integer.
    :param transcript_text: Transcript text payload for workflow input.
    :return: Created pipeline run UUID string identifier.
    :raises ImproperlyConfigured: When callback path is missing or invalid.
    """
    callback_path = getattr(settings, "AGENTS_TRANSCRIPT_READY_CALLBACK", "")
    if not isinstance(callback_path, str) or not callback_path.strip():
        raise ImproperlyConfigured(
            "AGENTS_TRANSCRIPT_READY_CALLBACK must be a dotted callback path."
        )

    callback = import_string(callback_path.strip())
    return callback(transcript_id, transcript_text)


__all__ = ["agent_run_completed", "register_handler", "trigger_transcript_post_create_workflow"]
