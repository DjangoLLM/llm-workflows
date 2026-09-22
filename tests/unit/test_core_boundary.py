"""Keep authoring definitions independent of installed runtime integrations."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from agents.inferences.choices import ChoiceDefinition


def test_definitions_import_and_register_without_runtime_dependencies():
    script = '''
import importlib.abc
import sys

class BlockRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("agents.runner", "agents.adapters", "agents.models", "django", "temporalio", "pydantic", "coding_agent_drivers")):
            raise AssertionError("Definitions imported runtime dependency: " + fullname)

sys.meta_path.insert(0, BlockRuntime())
from agents.inferences.agents import AgentDefinition
from agents.inferences.choices import ChoiceDefinition
from agents.steps import Step
from agents.workflows import Workflow
from agents.core import Definition, DefinitionCatalog, InferenceAdapter
AgentDefinition(instructions="test").register("agent")
ChoiceDefinition("Which?", "Best fit", dict, dict, candidates={"one": 1}).register("choice")
from agents.catalog.step_catalog import register_step
from agents.catalog.workflow_catalog import register_workflow
from agents.catalog.step_catalog import StepCatalog
class Echo(Step):
    def execute(self, payload):
        return payload
class Demo(Workflow):
    name = "isolated"
    steps = {"echo": Echo}
register_workflow(Demo)
register_step(key="echo", workflow_name=Demo.name, step_class=Echo, execution_type="CODE")
StepCatalog.validate_registry()
assert not hasattr(StepCatalog, "execute_step")
import agents.inferences.agents as agent
assert not hasattr(agent, "ManagedAgent")
'''
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(("package", "allowed"), [
    ("agents.core", ("agents.core",)),
    ("agents.inferences", ("agents.core", "agents.inferences", "agents.catalog")),
    ("agents.steps", ("agents.inferences",)),
    ("agents.workflows", ("agents.steps",)),
    ("agents.tools", ("agents.core.tools",)),
])
def test_source_imports_respect_package_boundaries(package, allowed):
    import ast
    import importlib

    module = importlib.import_module(package)
    for path in Path(module.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            for module in modules:
                schema_dependency = path.parent.name == "tools" and module == "pydantic"
                assert module.startswith(allowed) or module.split(".")[0] in sys.stdlib_module_names or schema_dependency, (path, module)


def test_choice_declares_fixed_or_dynamic_candidates():
    fixed = ChoiceDefinition("Which project?", "Closest topic", dict, dict, candidates={"p1": "Project one"})
    dynamic = ChoiceDefinition("Which projects?", "Related topics", dict, dict, candidate_type=dict, selection="multiple", allow_no_match=True)
    assert fixed.selection == "single"
    assert dynamic.candidates is None
    assert dynamic.allow_no_match


@pytest.mark.parametrize("overrides", [
    {"question": ""}, {"criteria": " "}, {"candidates": {}},
    {"candidates": {"": "bad"}}, {"selection": "unknown"},
    {"candidates": None},
])
def test_choice_rejects_invalid_definitions(overrides):
    values = dict(question="Which?", criteria="Best fit", input_type=dict, result_type=dict, candidates={"one": 1})
    values.update(overrides)
    with pytest.raises(ValueError):
        ChoiceDefinition(**values)
