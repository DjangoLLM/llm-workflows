# freedom-agents

Reusable Django app for Temporal-backed agent workflow execution.

## Installation

Add to `INSTALLED_APPS` and configure the default agent settings:

```python
INSTALLED_APPS = [
    ...,
    "agents",
]

DEFAULT_AGENT_CONFIG = {
    "model": "gpt-4o",
}

TEMPORAL_SERVER_URL = "localhost:7233"
TEMPORAL_TASK_QUEUE = "ai-pipeline-queue"

# Optional: host apps add their own workflow plugins here.
AGENTS_TEMPORAL_PLUGIN_MODULES = [
    "my_app.temporal_plugin",
]
```

## Execution Model

Temporal is the only documented workflow execution path for this package.

Host applications define pipeline steps and concrete Temporal workflows. This package supplies the shared ledger models, step execution helpers, core Temporal activities, worker plugin loading, and the `run_temporal_worker` command.

The runtime shape is:

- `Pipeline` and `PipelineStep` own ledger records and step execution.
- `StepCatalog` registers executable step metadata.
- `agents.temporal.activities` exposes core Temporal activities, including pipeline run creation, step execution, and success/failure marking.
- `run_temporal_worker` starts a Temporal worker and loads core activities plus any configured host-app workflow plugins.
- `AGENTS_TEMPORAL_PLUGIN_MODULES` points at modules that expose `get_temporal_worker_plugin()`.

The built-in core plugin registers activities only. It does not register application workflows. A host app must provide at least one Temporal workflow plugin to run a workflow.

## Temporal Workflow Setup

### Define a Pipeline and Steps

Define each executable unit as a `PipelineStep`, then register its owning `Pipeline` and `StepCatalog` metadata during Django startup. The step is not run directly by application code; Temporal activities invoke it.

```python
from agents.pipeline_structure import Pipeline, PipelineRegistry, PipelineStep
from agents.step_catalog import StepCatalog, StepExecutionType


class NormalizeStep(PipelineStep):
    def execute(self, payload: dict) -> dict:
        return {"text": payload["text"].strip()}


class SummarizeStep(PipelineStep):
    def execute(self, payload: dict) -> dict:
        return {"summary": payload["text"][:120]}


class NotesPipeline(Pipeline):
    name = "notes.pipeline"
    steps = {
        "normalize": NormalizeStep,
        "summarize": SummarizeStep,
    }


def register_pipeline_runtime() -> None:
    PipelineRegistry.register(NotesPipeline)
    StepCatalog.register_step(
        key="normalize",
        pipeline_name="notes.pipeline",
        step_class=NormalizeStep,
        execution_type=StepExecutionType.CODE,
    )
    StepCatalog.register_step(
        key="summarize",
        pipeline_name="notes.pipeline",
        step_class=SummarizeStep,
        execution_type=StepExecutionType.CODE,
    )
```

Call `register_pipeline_runtime()` from your app's `AppConfig.ready()` or from a registration module imported there.

### Create a Temporal Workflow Plugin

Create a module listed in `AGENTS_TEMPORAL_PLUGIN_MODULES`, for example `my_app/temporal_plugin.py`.

```python
from datetime import timedelta

from temporalio import workflow

from agents.temporal.worker_plugins import TemporalWorkerPlugin

with workflow.unsafe.imports_passed_through():
    from agents.temporal.activities import (
        create_pipeline_run_activity,
        execute_pipeline_step_activity,
        mark_pipeline_failed_activity,
        mark_pipeline_success_activity,
    )


PIPELINE_NAME = "notes.pipeline"


@workflow.defn(name="notes.pipeline.workflow")
class NotesPipelineWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        run_id = payload.get("run_id")
        step_payload = payload.get("payload", payload)

        try:
            if not run_id:
                run_id = await workflow.execute_activity(
                    create_pipeline_run_activity,
                    args=[PIPELINE_NAME, step_payload],
                    start_to_close_timeout=timedelta(seconds=10),
                )

            normalized = await workflow.execute_activity(
                execute_pipeline_step_activity,
                args=[run_id, PIPELINE_NAME, "normalize", 0, step_payload],
                start_to_close_timeout=timedelta(minutes=1),
            )
            summary = await workflow.execute_activity(
                execute_pipeline_step_activity,
                args=[run_id, PIPELINE_NAME, "summarize", 1, normalized],
                start_to_close_timeout=timedelta(minutes=2),
            )

            await workflow.execute_activity(
                mark_pipeline_success_activity,
                args=[run_id, PIPELINE_NAME],
                start_to_close_timeout=timedelta(seconds=10),
            )
            return {"run_id": run_id, "output": summary}
        except Exception as exc:
            if run_id:
                await workflow.execute_activity(
                    mark_pipeline_failed_activity,
                    args=[run_id, PIPELINE_NAME, str(exc)],
                    start_to_close_timeout=timedelta(seconds=10),
                )
            raise


def get_temporal_worker_plugin() -> TemporalWorkerPlugin:
    return TemporalWorkerPlugin(
        plugin_slug="notes",
        workflows=[NotesPipelineWorkflow],
        activities=[],
    )
```

If the workflow needs custom activities, decorate them with `@activity.defn(name="notes.some_activity")` and register them as `TemporalActivityRegistration` entries. Activity names must start with the plugin slug plus a dot, for example `notes.`.

### Configure Django

```python
INSTALLED_APPS = [
    ...,
    "agents",
    "my_app",
]

TEMPORAL_SERVER_URL = "localhost:7233"
TEMPORAL_TASK_QUEUE = "ai-pipeline-queue"
AGENTS_TEMPORAL_PLUGIN_MODULES = [
    "my_app.temporal_plugin",
]
```

### Start Temporal and the Worker

Run a Temporal server locally, then start the Django worker process.

```bash
temporal server start-dev
python manage.py run_temporal_worker
```

The worker connects to `TEMPORAL_SERVER_URL`, listens on `TEMPORAL_TASK_QUEUE`, loads the built-in `agents` activities, then loads each configured plugin module.

### Start a Workflow

Use the Temporal Python client from any async caller, management command, view, or service layer. Do not call `Pipeline.execute_step()` or `ManagedAgent.run()` as the application workflow entrypoint.

```python
from temporalio.client import Client


async def start_notes_workflow() -> str:
    client = await Client.connect("localhost:7233")
    handle = await client.start_workflow(
        "notes.pipeline.workflow",
        {"payload": {"text": "  summarize this note  "}},
        id="notes-pipeline-001",
        task_queue="ai-pipeline-queue",
    )
    return handle.id
```

To wait for the result instead of only starting the workflow:

```python
result = await handle.result()
```

### Execute a Single Registered Step

Workflows can call the generic activity:

```python
await workflow.execute_activity(
    execute_pipeline_step_activity,
    args=[run_id, "notes.pipeline", "normalize", 0, {"text": "hello"}],
    start_to_close_timeout=timedelta(minutes=1),
)
```

The core plugin also exposes generated step activities named `agents.pipeline_step.<step_key>` for every registered `StepCatalog` key. The generic activity is usually simpler and avoids static imports for dynamic step names.

---
Built with love in Bangalore!
