# Workflow building

Freedom Agents is a workflow-building harness for producing reusable workflows from tasks defined collaboratively with an agent.

## Language

**Workflow-building harness**:
The conventions, capabilities, and validation facilities that let an agent produce a reusable, executable workflow from a user's task.

**Coding agent**:
The agent that collaborates with a user to author reusable tools, task agents, choices, steps, and workflows.

**Task agent**:
An agent defined to perform a specific task using explicit instructions, permitted tools, and an expected result contract.

**Tool**:
A reusable operation with an input/output contract that an agent or ordinary workflow code can invoke.

**Toolset**:
A named collection of related tools.

**Workflow**:
A reusable definition of a task that composes steps and specifies how their results determine subsequent work.
_Avoid_: Run when referring to the reusable definition.

**Run**:
A particular execution of a workflow, step, agent, or choice, with its own inputs, outcomes, and execution history.
_Avoid_: Workflow when referring to a single execution.

**Step**:
A unit of workflow work with a defined input/output contract, performed through ordinary operations, an agent, or a choice.

**AgentDefinition**:
The definition of an agent's instructions, execution configuration, permitted tools, and input/output contract.

_Avoid_: AgentConfig or AgentTemplate for this reusable definition.

**ManagedAgent**:
The managed execution of an agent, responsible for preserving its inputs, outputs, available execution trace, and outcome.

**Choice**:
A bounded decision that selects among declared candidates under explicit criteria. A workflow can use its result as data or to select subsequent work.
_Avoid_: Branch when referring only to the decision rather than the path executed afterward.

**Branch**:
An execution path selected by workflow logic, which may use a choice's result.
_Avoid_: Branch when referring to classification or the decision alone.

**ChoiceDefinition**:
The definition of a choice's question, criteria, input/output contract, candidates or candidate schema, selection cardinality, and evaluator configuration.

_Avoid_: ChoiceConfig or ChoiceTemplate for this reusable definition.

**ManagedChoice**:
The managed evaluation of a choice, responsible for validating its selection and preserving the input, actual candidates, decision, available execution trace, and outcome.

**Evaluator**:
The configured decision mechanism that supplies a choice's selection, using Jev, an LLM, or ordinary code.

**Candidate**:
An identifiable option eligible for selection in a particular choice execution.

**No match**:
An explicit valid choice outcome indicating that no supplied candidate fits, when the choice contract permits that outcome.
