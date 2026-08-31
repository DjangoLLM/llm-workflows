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

## Primitives and Architecture

This package provides a framework for building AI pipelines focused on observability and auditability. It mixes deterministic Python code with non-deterministic AI steps, while keeping an absolute database ledger of everything that happens. 

Before building a pipeline, it's helpful to understand the primitives of this project:

### 1. `ManagedAgent`
A `ManagedAgent` is a wrapper around an LLM based Agent (can do tool calls). It provides database persistence and state tracking (`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`).

What it does:
1. You can provide your agent access to tools.
2. It provides a standardized interface for running agents, with inputs and outputs controlled through Pydantic Types.
3. It executes multi-turn LLM calls to achieve the given objective.

### 2. `PipelineStep`
A `PipelineStep` is a single unit of execution in your workflow. Steps can be:
- **Code Steps**: Pure Python code.
- **LLM Steps**: Backed by a `ManagedAgent`. You just provide an `AgentConfig`, and the step handles the LLM execution automatically.
Every time a step runs, a `PipelineStepModel` database record is created to track its inputs and outputs.

### 3. `Pipeline`
A `Pipeline` groups your `PipelineStep`s together. However, the `Pipeline` class itself does **not** contain orchestration logic (it does not contain a loop to move from step 1 to step 2). It acts purely as a bookkeeping tool, creating a `PipelineRun` database record to tie the step executions together.

### 4. Temporal (The Orchestrator)
Because `Pipeline` only handles database bookkeeping, an external orchestrator is required to actually transition from one step to the next. **Temporal is the only documented and supported workflow execution path for this package.** The Temporal workflow handles the execution order, retries, timeouts, and failure handling, calling the pipeline steps as Temporal Activities.

---

## Creating and Running a Pipeline: End-to-End Example

Let's build a **Customer Feedback Pipeline**. It will consist of two steps:
1. **Clean up the feedback text** (A standard Python code step)
2. **Analyze the sentiment & extract action items** (An LLM Agent step)

### Step 1: Define the Steps and the Pipeline

Define what your pipeline does. You can place this in a file like `my_app/pipelines.py`.

```python
from typing import Optional
from agents.core.pipeline_structure import Pipeline, PipelineRegistry, PipelineStep
from agents.core.agent import AgentConfig
from agents.core.step_catalog import StepCatalog, StepExecutionType

# --- STEP 1: A Standard Python Code Step ---
class CleanFeedbackStep(PipelineStep):
    def execute(self, payload: dict) -> dict:
        # Clean up the text
        raw_text = payload.get("text", "")
        cleaned_text = raw_text.strip().lower()
        return {"cleaned_text": cleaned_text}

# --- STEP 2: An LLM Agent Step ---
class AnalyzeFeedbackStep(PipelineStep):
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
class FeedbackPipeline(Pipeline):
    name = "feedback.pipeline"
    steps = {
        "clean_text": CleanFeedbackStep,
        "analyze": AnalyzeFeedbackStep,
    }

# --- REGISTRATION ---
# This function registers the pipeline with the system.
def register_feedback_pipeline():
    PipelineRegistry.register(FeedbackPipeline)
    
    StepCatalog.register_step(
        key="clean_text",
        pipeline_name="feedback.pipeline",
        step_class=CleanFeedbackStep,
        execution_type=StepExecutionType.CODE,
    )
    
    StepCatalog.register_step(
        key="analyze",
        pipeline_name="feedback.pipeline",
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
from agents.core.temporal.worker_plugins import TemporalWorkerPlugin

# Safely import the built-in activities
with workflow.unsafe.imports_passed_through():
    from agents.core.temporal.activities import (
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
