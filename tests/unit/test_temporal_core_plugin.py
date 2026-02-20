from __future__ import annotations

from temporalio import activity

from agents.temporal.plugins.core import get_temporal_worker_plugin


def test_core_plugin_includes_static_and_generated_activities(monkeypatch) -> None:
    @activity.defn(name="agents.generated.a")
    def generated_a(*_args, **_kwargs):
        return {"a": True}

    @activity.defn(name="agents.generated.b")
    def generated_b(*_args, **_kwargs):
        return {"b": True}

    monkeypatch.setattr(
        "agents.temporal.plugins.core.get_registered_step_activities",
        lambda: [generated_a, generated_b],
    )

    plugin = get_temporal_worker_plugin()

    assert plugin.plugin_slug == "agents"
    static_names = {registration.activity_name for registration in plugin.activities}
    assert "agents.create_pipeline_run_activity" in static_names
    assert len(plugin.activities) >= 6
