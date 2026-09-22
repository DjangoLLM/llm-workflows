"""Inference adapters require both execution entry points."""

import pytest

from agents.core import InferenceAdapter


def test_adapter_requires_both_execution_methods():
    class IncompleteAdapter(InferenceAdapter[str]):
        def run_sync(self, input_payload=None):
            return "done"

    with pytest.raises(TypeError, match="abstract"):
        IncompleteAdapter()
