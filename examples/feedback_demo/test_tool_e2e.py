"""E2E test: host app registers a ToolSet into default_registry via AppConfig.ready().

Run from the feedback_demo directory:
    DJANGO_SETTINGS_MODULE=feedback_demo.settings python test_tool_e2e.py
"""

from __future__ import annotations

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "feedback_demo.settings")

# Ensure agents package is importable (editable install in the parent venv).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

django.setup()

# After django.setup(), AppConfig.ready() has run and the EchoToolSet is registered.
from agents.runner.tools import default_registry  # noqa: E402
from feedback.tools import EchoOutput  # noqa: E402


def test_toolset_registered_after_app_ready():
    assert "echo" in default_registry.toolset_names(exposed_only=True), (
        "Expected 'echo' toolset registered with expose_mcp=True after app startup; "
        f"got: {default_registry.toolset_names()}"
    )
    print(f"  exposed toolsets: {default_registry.toolset_names(exposed_only=True)}")


def test_run_via_dict():
    result = default_registry.run("echo", {"text": "hello from e2e"})
    assert result == EchoOutput(echoed="hello from e2e", char_count=14)
    print(f"  run result: {result}")


def test_toolset_lookup():
    [echo_tool] = default_registry.resolve_toolset("echo")
    assert echo_tool.name == "echo"
    assert echo_tool.mcp_safe is True
    assert echo_tool.toolset_name == "echo"
    print(f"  resolved tool: {echo_tool.name} (mcp_safe={echo_tool.mcp_safe})")


def test_unknown_tool_raises():
    try:
        default_registry.get("no_such_tool")
        assert False, "should have raised KeyError"
    except KeyError:
        print("  KeyError raised correctly for unknown tool")


if __name__ == "__main__":
    tests = [
        test_toolset_registered_after_app_ready,
        test_run_via_dict,
        test_toolset_lookup,
        test_unknown_tool_raises,
    ]
    passed = 0
    for t in tests:
        print(f"[RUN] {t.__name__}")
        try:
            t()
            print(f"[PASS] {t.__name__}\n")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}\n")

    print(f"Results: {passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
