"""Catalogs can be imported first and preserve shared compatibility state."""

import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(("module", "legacy_modules", "symbols"), [
    ("agent_definition_catalog", ["runner.agent_definition_catalog"], ["AgentDefinitionCatalog"]),
    ("choice_definition_catalog", ["runner.choice_definition_catalog"], ["ChoiceDefinitionCatalog"]),
    ("step_catalog", [], ["StepCatalog", "StepRegistration", "StepExecutionType", "register_step"]),
    ("workflow_catalog", [], ["WorkflowRegistry", "register_workflow"]),
    ("tool_catalog", ["runner.tools.registry", "runner.tools"], ["ToolRegistry", "default_registry", "register_toolset"]),
])
def test_catalog_first_import_and_compatibility(module, legacy_modules, symbols):
    script = f'''
import importlib
catalog = importlib.import_module("agents.catalog.{module}")
for symbol in {symbols!r}:
    assert hasattr(catalog, symbol), symbol
for module in {legacy_modules!r}:
    legacy = importlib.import_module("agents." + module)
    for symbol in {symbols!r}:
        assert getattr(legacy, symbol) is getattr(catalog, symbol), (module, symbol)
'''
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    assert result.returncode == 0, result.stderr
