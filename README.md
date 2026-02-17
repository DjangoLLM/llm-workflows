# freedom-agents

Reusable Django app for core agent runtime and pipeline execution.

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
```

## Primitives

### Agent
A wrapper around `pydantic_ai.Agent` for LLM interaction logic. Supports async and sync execution of prompts and tool calls.

### ManagedAgent
Adds a persistence layer to `Agent`. Automatically tracks execution history, inputs, outputs, and status (PENDING -> RUNNING -> SUCCEEDED/FAILED) in the `AgentRun` model.

### Pipeline
A ledger-focused workflow container. Pipelines define a sequence of steps but leave orchestration logic to the caller (e.g. Temporal activities or management commands).

### PipelineStep
An individual unit of work within a pipeline. Executions are recorded in the `PipelineStep` model. Steps can wrap `ManagedAgent` executions or custom logic.

## Usage

**Running a Managed Agent:**

```python
from agents.agent import ManagedAgent, AgentConfig

config = AgentConfig(instructions="You are a helpful assistant.")
agent = ManagedAgent(config=config, agent_label="my-agent")

run_id = agent.run(input_payload={"message": "Hello!"})
```

**Defining a Pipeline Step:**

```python
from agents.pipeline_structure import PipelineStep

class MyStep(PipelineStep):
    def execute(self, payload: dict) -> dict:
        # custom logic or agent delegation
        return {"processed": True}
```
