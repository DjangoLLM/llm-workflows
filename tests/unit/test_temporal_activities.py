from __future__ import annotations

import asyncio

from temporalio.activity import _Definition as ActivityDefinition

from agents.temporal import activities


def test_create_pipeline_run_activity_delegates_to_registry(monkeypatch) -> None:
    class Pipeline:
        @classmethod
        def create_run(cls, payload):
            assert payload == {"x": 1}
            return "run-123"

    monkeypatch.setattr("agents.temporal.activities.PipelineRegistry.get", lambda _name: Pipeline)

    run_id = activities.create_pipeline_run_activity("demo", {"x": 1})

    assert run_id == "run-123"


def test_execute_pipeline_step_activity_delegates_to_catalog(monkeypatch) -> None:
    monkeypatch.setattr(
        "agents.temporal.activities.StepCatalog.execute_step",
        lambda **kwargs: {"kwargs": kwargs},
    )

    result = activities.execute_pipeline_step_activity(
        run_id="run-1",
        pipeline_name="pipeline",
        step_key="step",
        order_index=2,
        payload={"ok": True},
    )

    assert result["kwargs"]["step_key"] == "step"


def test_transform_step_to_activity_is_cached(monkeypatch) -> None:
    monkeypatch.setattr("agents.temporal.activities.StepCatalog.get_step", lambda _key: object())

    first = activities.transform_step_to_activity("custom.step")
    second = activities.transform_step_to_activity("custom.step")

    assert first is second
    assert first.__name__ == "custom_step_step_activity"
    assert ActivityDefinition.must_from_callable(first).name == "agents.pipeline_step.custom.step"


def test_generated_activity_dispatches_step_key(monkeypatch) -> None:
    monkeypatch.setattr("agents.temporal.activities.StepCatalog.get_step", lambda _key: object())

    generated = activities.transform_step_to_activity("custom.dispatch")
    calls: list[dict] = []

    def fake_execute(**kwargs):
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr("agents.temporal.activities.execute_pipeline_step_activity", fake_execute)

    output = generated("run-9", "pipeline", 4, {"a": "b"})

    assert output == {"ok": True}
    assert calls[0]["step_key"] == "custom.dispatch"


def test_get_registered_step_activities_filters_legacy(monkeypatch) -> None:
    monkeypatch.setattr(
        "agents.temporal.activities.StepCatalog.list_step_keys",
        lambda: ["correction", "custom.one", "matching", "custom.two"],
    )

    generated = []

    def fake_transform(step_key: str):
        generated.append(step_key)

        def _activity(*_args, **_kwargs):
            return {"step": step_key}

        return _activity

    monkeypatch.setattr("agents.temporal.activities.transform_step_to_activity", fake_transform)

    result = activities.get_registered_step_activities()

    assert len(result) == 2
    assert generated == ["custom.one", "custom.two"]


def test_legacy_step_wrappers_forward_expected_keys(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_execute(run_id, pipeline_name, step_key, order_index, payload):
        calls.append((pipeline_name, step_key))
        return {"ok": step_key}

    monkeypatch.setattr("agents.temporal.activities.execute_pipeline_step_activity", fake_execute)

    activities.correction_step_activity("r", "p", 1, {})
    activities.categorization_step_activity("r", "p", 2, {})
    activities.segmentation_step_activity("r", "p", 3, {})
    activities.matching_step_activity("r", "p", 4, {})

    assert calls == [
        ("p", "correction"),
        ("p", "categorization"),
        ("p", "segmentation"),
        ("p", "matching"),
    ]


def test_mark_pipeline_success_and_failure_delegate(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    class Pipeline:
        @classmethod
        def mark_success(cls, run_id: str):
            calls.append(("success", run_id))

        @classmethod
        def mark_failure(cls, run_id: str, error: str | None = None):
            calls.append(("failure", f"{run_id}:{error}"))

    monkeypatch.setattr("agents.temporal.activities.PipelineRegistry.get", lambda _name: Pipeline)

    activities.mark_pipeline_success_activity("run-1", "pipe")
    activities.mark_pipeline_failed_activity("run-2", "pipe", "err")

    assert calls == [("success", "run-1"), ("failure", "run-2:err")]


def test_stub_handlers_return_success_payloads() -> None:
    assert asyncio.run(activities.handle_meeting_notes_activity("run", {}))["status"] == "stub_success"
    assert asyncio.run(activities.handle_module_creation_activity("run", {}))["handler"] == "handle_module_creation"
    assert asyncio.run(activities.handle_status_update_activity("run", {}))["handler"] == "handle_status_update"
    assert asyncio.run(activities.handle_random_brain_dump_activity("run", {}))["handler"] == "handle_random_brain_dump"
