from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace

import pytest

from agents.management.commands.run_temporal_worker import Command
from agents.runner.temporal.worker_plugins import TemporalWorkerComposition


@pytest.mark.django_db
def test_run_worker_builds_and_runs_worker(settings, monkeypatch) -> None:
    settings.TEMPORAL_SERVER_URL = "localhost:7233"
    settings.TEMPORAL_TASK_QUEUE = "queue-x"

    composition = TemporalWorkerComposition(
        plugin_modules=["agents.runner.temporal.plugins.core"],
        plugin_slugs=["agents"],
        workflow_names=["wf"],
        workflows=[object],
        activity_names=["agents.core_activity"],
        activities=[lambda: None],
    )

    calls: dict[str, object] = {}

    async def fake_connect(url: str):
        calls["connect_url"] = url
        return "client"

    class DummyWorker:
        def __init__(self, client, task_queue, workflows, activities, activity_executor):
            calls["worker_client"] = client
            calls["worker_queue"] = task_queue
            calls["workflow_count"] = len(workflows)
            calls["activity_count"] = len(activities)
            calls["activity_executor"] = activity_executor

        async def run(self):
            calls["ran"] = True

    monkeypatch.setattr(
        "agents.management.commands.run_temporal_worker.build_temporal_worker_composition",
        lambda: composition,
    )
    monkeypatch.setattr("agents.management.commands.run_temporal_worker.Client.connect", fake_connect)
    monkeypatch.setattr("agents.management.commands.run_temporal_worker.Worker", DummyWorker)
    monkeypatch.setattr(
        "agents.management.commands.run_temporal_worker.concurrent.futures.ThreadPoolExecutor",
        lambda max_workers: contextlib.nullcontext(SimpleNamespace(max_workers=max_workers)),
    )

    command = Command()
    asyncio.run(command.run_worker())

    assert calls["connect_url"] == "localhost:7233"
    assert calls["worker_client"] == "client"
    assert calls["worker_queue"] == "queue-x"
    assert calls["workflow_count"] == 1
    assert calls["activity_count"] == 1
    assert calls["ran"] is True


def test_handle_gracefully_handles_keyboard_interrupt(monkeypatch) -> None:
    def _raise_keyboard_interrupt(coroutine):
        coroutine.close()
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        "agents.management.commands.run_temporal_worker.asyncio.run",
        _raise_keyboard_interrupt,
    )

    command = Command()
    command.handle()


def test_handle_re_raises_exceptions(monkeypatch) -> None:
    def _raise_runtime_error(coroutine):
        coroutine.close()
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "agents.management.commands.run_temporal_worker.asyncio.run",
        _raise_runtime_error,
    )

    command = Command()
    with pytest.raises(RuntimeError, match="boom"):
        command.handle()
