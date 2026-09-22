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

## Typed inference through the Codex CLI

Set `execution_backend="codex_cli"` to run inference with the installed
`codex` executable instead of Pydantic AI. The package pins its
`coding-agent-drivers` dependency to an exact Git revision in
`pyproject.toml`, so a normal package installation does not depend on a sibling
editable checkout.

```python
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from agents.core import AgentConfig
from agents.runner import Agent, ManagedAgent


class Details(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: list[str]
    note: str | None


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marker: Literal["codex-ok"]
    count: int
    details: Details


config = AgentConfig(
    instructions="Return marker codex-ok, count 2, two values, and a null note.",
    execution_backend="codex_cli",
    model=None,
    result_type=Answer,
    extra_kwargs={
        "codex_working_dir": Path.cwd(),
        "codex_timeout_seconds": 180,
    },
)

direct = Agent(config).run_sync({"request": "typed example"})
assert type(direct.output) is Answer

managed = ManagedAgent(config=config)
stored_output = managed.run_sync({"request": "typed example"})
assert stored_output == direct.output.model_dump(mode="json")
```

`model` is optional. A nonempty string is passed to `codex --model`. With
`model=None`, the command omits that flag and the Codex CLI resolves its
configured default. `codex_working_dir` defaults to the current directory and
must name an existing directory. `codex_timeout_seconds` defaults to 300 and
must be a positive finite number.

The backend reuses authentication from the installed Codex CLI. Sign in with
the CLI before running the agent. It does not accept an API key in
`extra_kwargs`.

### Result schema contract

`result_type` must be a Pydantic `BaseModel` subclass with
`ConfigDict(extra="forbid")`. Supported fields are fixed nested models,
strings, integers, numbers, booleans, homogeneous lists, scalar literals or
enums, and a nullable union of one supported type with `None`. Local,
nonrecursive model references are supported. Root models, recursive models,
arbitrary dictionaries, general unions, tuples, and constraints such as
lengths or numeric bounds are rejected before the CLI starts. Every declared
field must appear in the response JSON, including fields with Python defaults.
The final response is validated strictly against the original model.

`Agent.run()` and `Agent.run_sync()` return a result whose `output` is the
declared model instance. `ManagedAgent` converts that model to JSON-safe data,
stores it on `AgentRun.output`, and marks the run `SUCCEEDED`. A launch error,
timeout, nonzero exit, terminal failure event, missing final response, or
schema validation error raises on a direct call. A managed call records the
same error message and marks the run `FAILED`.

Each call gets its own temporary schema and final-response files. The runner
removes them after success, failure, timeout, or cancellation.

### Tools and sandbox limits

The framework does not bridge `AgentConfig.tools` or `toolsets` into Codex;
the backend rejects both. The runner requests Codex's read-only sandbox policy,
but that policy is not filesystem isolation. The process can still read local
files allowed by the Codex sandbox, and trusted Codex configuration may make
other local tools available. Only use this backend with a working directory
and Codex configuration you trust.

See [tests/TESTING.md](tests/TESTING.md) for deterministic and live test
commands.

## Public interfaces

Workflow code imports definition primitives from `agents.core`. It defines and
registers toolsets, steps, and workflows. Application execution code imports
from `agents.runner`, which resolves those registrations and owns persistence,
backends, and Temporal integration.

```python
from agents.core import (
    AgentConfig,
    Step,
    StepExecutionType,
    ToolSet,
    Workflow,
    register_step,
    register_toolset,
    register_workflow,
    tool,
)
```

## Primitives and architecture

This package provides a framework for building AI pipelines focused on observability and auditability. It mixes deterministic Python code with non-deterministic AI steps, while keeping an absolute database ledger of everything that happens. 

Before building a pipeline, it's helpful to understand the primitives of this project:

### 1. `ManagedAgent`
A `ManagedAgent` is a wrapper around an LLM based Agent (can do tool calls). It provides database persistence and state tracking (`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`).

What it does:
1. You can provide your agent access to tools.
2. It provides a standardized interface for running agents, with inputs and outputs controlled through Pydantic Types.
3. It executes multi-turn LLM calls to achieve the given objective.

### 2. `Step`
A `Step` is a single unit of execution in your workflow. Steps can be:
- **Code Steps**: Pure Python code.
- **LLM Steps**: Backed by a `ManagedAgent`. You just provide an `AgentConfig`, and the step handles the LLM execution automatically.
Every time a step runs, a `PipelineStepModel` database record is created to track its inputs and outputs.

### 3. `JevIf`
A standalone two-way decision made by Jev. It is not a `PipelineStep` and needs no `PipelineRun`; each decision is ledgered as an `AgentRun`. Workflows call it through the `agents.jev_if_activity` activity and branch on `result`. Jev supplies the judgement, Temporal owns the branch.

```python
# in a Temporal workflow
verdict = await workflow.execute_activity(
    "agents.jev_if_activity",
    args=["The segment refers to a tracked task.", {"segment_text": text}],
    start_to_close_timeout=timedelta(seconds=30),
)
if verdict["result"]:
    ...
```

Output is `{"result": bool, "confidence": float, "probabilities": {"true": p, "false": q}}`. Requires `TYPESAFE_API_KEY`. For more than two outcomes use a Jev `AgentConfig` with your own `questions` criteria.

### 4. `Workflow`
A `Workflow` names and groups its `Step` definitions. The runner records each execution as a `PipelineRun`; that persisted model keeps its existing name for database compatibility.

### 5. Temporal (The Orchestrator)
Temporal is the supported executor. It handles execution order, retries, timeouts, and failure handling while calling registered steps as activities.

---

## Creating and Running a Pipeline: End-to-End Example

Let's build a **Customer Feedback Pipeline**. It will consist of two steps:
1. **Clean up the feedback text** (A standard Python code step)
2. **Analyze the sentiment & extract action items** (An LLM Agent step)

### Step 1: Define the Steps and the Pipeline

Define what your pipeline does. You can place this in a file like `my_app/pipelines.py`.

```python
from typing import Optional
from agents.core import (
    AgentConfig,
    Step,
    StepExecutionType,
    Workflow,
    register_step,
    register_workflow,
)

# --- STEP 1: A Standard Python Code Step ---
class CleanFeedbackStep(Step):
    def execute(self, payload: dict) -> dict:
        # Clean up the text
        raw_text = payload.get("text", "")
        cleaned_text = raw_text.strip().lower()
        return {"cleaned_text": cleaned_text}

# --- STEP 2: An LLM Agent Step ---
class AnalyzeFeedbackStep(Step):
    @property
    def agent_config(self) -> Optional[AgentConfig]:
        # Provide the instructions for the LLM under the hood
        return AgentConfig(
            instructions=(
                "You are a customer success AI. Read the feedback and return JSON "
                "with two keys: 'sentiment' (positive/negative/neutral) and "
                "'action_item' (a short string suggesting what we should do)."
            ),
            model="gpt-4o"
        )

# --- THE PIPELINE ---
class FeedbackWorkflow(Workflow):
    name = "feedback.pipeline"
    steps = {
        "clean_text": CleanFeedbackStep,
        "analyze": AnalyzeFeedbackStep,
    }

# --- REGISTRATION ---
# This function registers the pipeline with the system.
def register_feedback_pipeline():
    register_workflow(FeedbackWorkflow)
    
    register_step(
        key="clean_text",
        workflow_name="feedback.pipeline",
        step_class=CleanFeedbackStep,
        execution_type=StepExecutionType.CODE,
    )
    
    register_step(
        key="analyze",
        workflow_name="feedback.pipeline",
        step_class=AnalyzeFeedbackStep,
        execution_type=StepExecutionType.LLM,
    )
```

### Step 2: Register during Django Startup

You need to call the registration function when Django boots up. Do this in your `my_app/apps.py`.

```python
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = "my_app"

    def ready(self):
        from .pipelines import register_feedback_pipeline
        register_feedback_pipeline()
```

### Step 3: Create the Temporal Orchestrator (Workflow)

Create a file called `my_app/temporal_plugin.py`. This is where we tell Temporal **how** to orchestrate the steps.

```python
from datetime import timedelta
from temporalio import workflow
from agents.runner.temporal.worker_plugins import TemporalWorkerPlugin

# Safely import the built-in activities
with workflow.unsafe.imports_passed_through():
    from agents.runner.temporal.activities import (
        create_pipeline_run_activity,
        execute_pipeline_step_activity,
        mark_pipeline_success_activity,
        mark_pipeline_failed_activity,
    )

PIPELINE_NAME = "feedback.pipeline"

@workflow.defn(name="feedback.pipeline.workflow")
class FeedbackPipelineWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        run_id = payload.get("run_id")
        step_payload = payload.get("payload", payload)

        try:
            # 1. Create the database run record (Ledger)
            if not run_id:
                run_id = await workflow.execute_activity(
                    create_pipeline_run_activity,
                    args=[PIPELINE_NAME, step_payload],
                    start_to_close_timeout=timedelta(seconds=10),
                )

            # 2. Execute Step 1: Clean
            cleaned_data = await workflow.execute_activity(
                execute_pipeline_step_activity,
                args=[run_id, PIPELINE_NAME, "clean_text", 0, step_payload],
                start_to_close_timeout=timedelta(minutes=1),
            )

            # 3. Execute Step 2: Analyze (pass the cleaned_data into it)
            analysis_result = await workflow.execute_activity(
                execute_pipeline_step_activity,
                args=[run_id, PIPELINE_NAME, "analyze", 1, cleaned_data],
                start_to_close_timeout=timedelta(minutes=2),
            )

            # 4. Mark success in the ledger
            await workflow.execute_activity(
                mark_pipeline_success_activity,
                args=[run_id, PIPELINE_NAME],
                start_to_close_timeout=timedelta(seconds=10),
            )
            
            return {"run_id": run_id, "output": analysis_result}

        except Exception as exc:
            # 5. Mark failure if anything breaks
            if run_id:
                await workflow.execute_activity(
                    mark_pipeline_failed_activity,
                    args=[run_id, PIPELINE_NAME, str(exc)],
                    start_to_close_timeout=timedelta(seconds=10),
                )
            raise

def get_temporal_worker_plugin() -> TemporalWorkerPlugin:
    return TemporalWorkerPlugin(
        plugin_slug="feedback",
        workflows=[FeedbackPipelineWorkflow],
        activities=[],
    )
```

*(If the workflow needs custom activities, decorate them with `@activity.defn(name="feedback.some_activity")` and pass them into `activities=[]` inside the plugin.)*

### Step 4: Configure Django

Make sure your app and the new temporal plugin module are registered in `settings.py`.

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

### Step 5: Start Temporal and the Worker

Run a Temporal server locally, then start the Django worker process. The worker will connect to Temporal and load your built-in `agents` activities and the `my_app.temporal_plugin` you just configured.

```bash
temporal server start-dev
python manage.py run_temporal_worker
```

### Step 6: Trigger the Pipeline from Your App

When you want to run the pipeline (e.g., from a Django View, an API, or a Celery task), use the Temporal Python client.

```python
import uuid
from temporalio.client import Client
from django.conf import settings

async def process_new_feedback(feedback_text: str):
    # Connect to your Temporal server
    client = await Client.connect(settings.TEMPORAL_SERVER_URL)
    
    # Start the workflow
    handle = await client.start_workflow(
        "feedback.pipeline.workflow",
        {"payload": {"text": feedback_text}}, # Initial payload
        id=f"feedback-job-{uuid.uuid4()}",
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )
    
    # Wait for completion and return the result
    result = await handle.result()
    print("Final Analysis:", result["output"])
    return result
```

## Execute a Single Registered Step Manually

If you only want to execute one step in a custom workflow, you can call the generic activity:

```python
await workflow.execute_activity(
    execute_pipeline_step_activity,
    args=[run_id, "feedback.pipeline", "clean_text", 0, {"text": "hello"}],
    start_to_close_timeout=timedelta(minutes=1),
)
```

The core plugin also exposes generated step activities named `agents.pipeline_step.<step_key>` for every registered `StepCatalog` key. However, the generic activity is usually simpler and avoids static imports for dynamic step names.

---
Built with love in Bangalore!
