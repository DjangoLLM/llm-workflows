from __future__ import annotations


def mock_transcript_callback(transcript_id: int, transcript_text: str) -> str:
    return f"run-{transcript_id}-{len(transcript_text)}"
