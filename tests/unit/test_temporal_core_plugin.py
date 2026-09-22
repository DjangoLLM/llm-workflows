from __future__ import annotations

from temporalio import activity

from agents.adapters.temporal.plugins.core import get_temporal_worker_plugin


def test_core_plugin_includes_static_and_generated_activities(monkeypatch) -> None:
    @activity.defn(name="agents.generated.a")
    def generated_a(*_args, **_kwargs):
        return {"a": True}

    @activity.defn(name="agents.generated.b")
    def generated_b(*_args, **_kwargs):
        return {"b": True}

    monkeypatch.setattr(
        "agents.adapters.temporal.plugins.core.get_registered_step_activities",
        lambda: [generated_a, generated_b],
    )

    plugin = get_temporal_worker_plugin()

    assert plugin.plugin_slug == "agents"
    activity_names = {registration.activity_name for registration in plugin.activities}
    assert {
        "agents.create_pipeline_run_activity",
        "agents.mark_pipeline_success_activity",
        "agents.mark_pipeline_failed_activity",
        "agents.execute_pipeline_step_activity",
        "agents.handle_meeting_notes_activity",
        "agents.handle_random_brain_dump_activity",
        "agents.generated.a",
        "agents.generated.b",
    } <= activity_names


def test_core_plugin_does_not_register_inference_workflow() -> None:
    plugin = get_temporal_worker_plugin()

    assert plugin.workflows == []


def test_core_plugin_does_not_register_pi_mcp_bridge_activities() -> None:
    plugin = get_temporal_worker_plugin()

    activity_names = {registration.activity_name for registration in plugin.activities}
    assert "agents.mcp.list_pi_tools" not in activity_names
    assert "agents.mcp.call_pi_tool" not in activity_names
