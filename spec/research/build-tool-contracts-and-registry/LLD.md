# LLD — Build tool contracts and registry

**Work item:** #380 · **Plane ID:** cc39c7b4-fdbb-4c85-8712-18c5d18e401f  
**HLD:** `spec/research/build-tool-contracts-and-registry/HLD.md`  
**Target module:** `freedom-agents/tools/`

---

## 1. File layout to create

Create the following files (all new; nothing is renamed or deleted):

```
freedom-agents/
  tools/
    __init__.py
    contracts.py
    toolset.py
    registry.py
  tests/unit/
    test_tool_contracts.py
    test_toolset.py
    test_tool_registry.py
```

---

## 2. `tools/contracts.py`

### 2.1 `ToolExecutionError`

Subclass `Exception`. Constructor signature: single positional parameter `message: str`, plus four keyword-only optional parameters — `tool_name: str | None`, `input_snapshot: dict | None`, `provider_status: int | None`, `provider_body: str | None`, all defaulting to `None`. Store each parameter as an instance attribute with the same name. No `__str__` override needed; the default `Exception.__str__` behaviour (displaying `message`) is sufficient.

### 2.2 `ToolDef`

A `dataclass(frozen=True)` with exactly five fields in declaration order: `name: str`, `input_model: type[BaseModel]`, `output_model: type[BaseModel]`, `tags: frozenset[str]`, `callable: Callable[[BaseModel], BaseModel]`. Import `BaseModel` from `pydantic`, `Callable` from `collections.abc`, `dataclass` from `dataclasses`, and `ClassVar` / type-var machinery only if needed. No methods beyond what `dataclass` generates.

---

## 3. `tools/toolset.py`

### 3.1 `_TOOL_MARKER` sentinel

Module-private string constant used to mark decorated methods. Value is `"__tool_meta__"`. This is the single source of truth for `@tool` discovery — no suffix inspection.

### 3.2 `@tool` decorator

A function (not a class) that accepts three keyword-only parameters: `name: str | None = None`, `tags: Iterable[str] = ()`, `output_model: type[BaseModel] | None = None`. It returns a decorator that, when applied to a method, attaches a dict of metadata to the method object under the `_TOOL_MARKER` attribute key. The dict stores: `override_name` (the `name` argument, `None` if not given), `extra_tags` (a `frozenset` built from `tags`), `override_output_model` (the `output_model` argument, `None` if not given). The decorator must return the original function unchanged (i.e. it is not a wrapper — the method itself is returned with the attribute attached).

### 3.3 `Toolset` base class

A plain Python class (not a dataclass). Two class variables: `name: ClassVar[str]` (no default — subclasses must set it) and `tags: ClassVar[frozenset[str]] = frozenset()`. One instance method: `get_tools(self) -> list[ToolDef]`.

`get_tools` implementation steps:

1. Iterate over `inspect.getmembers(self, predicate=inspect.ismethod)` to obtain bound methods.
2. For each bound method, check whether its underlying function has the `_TOOL_MARKER` attribute. Skip any method that does not.
3. For methods that pass the check, retrieve the stored metadata dict.
4. Resolve the tool's short name: use `metadata["override_name"]` if set, otherwise use the method's `__name__`.
5. Build the fully-qualified name as `f"{self.name}.{short_name}"`.
6. Resolve `input_model`: inspect the method's type hints (excluding `return`). Iterate the hint values; the first that is a subclass of `BaseModel` is the input model. If none is found, raise `TypeError` with a message that names the method and states a `BaseModel`-typed parameter is required.
7. Resolve `output_model`: use `metadata["override_output_model"]` if set; otherwise take `hints.get("return")`. If neither resolves to a `BaseModel` subclass, raise `TypeError` with a message naming the method.
8. Build `tags` as the union of `self.__class__.tags` and `metadata["extra_tags"]`.
9. Construct and append a `ToolDef(name=fqn, input_model=..., output_model=..., tags=..., callable=bound_method)`.
10. Return the collected list.

Import: `inspect` from stdlib, `get_type_hints` from `typing`, `ClassVar` from `typing`, `Iterable` from `collections.abc`, `ToolDef` from `.contracts`, `BaseModel` from `pydantic`.

---

## 4. `tools/registry.py`

### 4.1 `ToolRegistry` class

Internal state: a single `dict[str, ToolDef]` instance attribute `_tools`, initialised to `{}` in `__init__`, and a `list[Toolset]` instance attribute `_toolsets`, also initialised to `[]`.

#### `register(self, toolset: Toolset) -> None`

Call `toolset.get_tools()`. For each returned `ToolDef`, check if `tool_def.name` is already in `self._tools`. If it is, raise `ValueError` with a message that names the colliding tool. Otherwise, store it. After processing all tools, append the toolset instance to `self._toolsets`.

#### `get(self, name: str) -> ToolDef`

Look up `name` in `self._tools`. If absent, raise `KeyError(name)` — no wrapping, no message.

#### `run(self, name: str, input: dict | BaseModel) -> BaseModel`

1. Retrieve the `ToolDef` via `self.get(name)` (lets `KeyError` propagate naturally).
2. If `input` is a `dict`, validate it: call `tool_def.input_model.model_validate(input)`. This raises Pydantic `ValidationError` on bad input; do not catch it.
3. If `input` is already an instance of `tool_def.input_model`, pass it through unchanged.
4. If `input` is a `BaseModel` instance but not the right type, validate via `tool_def.input_model.model_validate(input.model_dump())`.
5. Call `tool_def.callable(validated_input)` and return the result.

#### `names(self, *, tags: Iterable[str] | None = None) -> list[str]`

If `tags` is `None`, return `sorted(self._tools.keys())`. Otherwise, convert `tags` to a `frozenset` and return `sorted(name for name, td in self._tools.items() if frozenset(tags).issubset(td.tags))`.

#### `toolsets(self) -> list[Toolset]`

Return `list(self._toolsets)` (a copy).

### 4.2 Module-level singleton

After the class definition: `default_registry = ToolRegistry()`. No auto-population; it starts empty.

Import: `Iterable` from `collections.abc`, `BaseModel` from `pydantic`, `Toolset` from `.toolset`, `ToolDef` from `.contracts`.

---

## 5. `tools/__init__.py`

Three import lines: one from `.contracts` exporting `ToolDef` and `ToolExecutionError`, one from `.toolset` exporting `Toolset` and `tool`, one from `.registry` exporting `ToolRegistry` and `default_registry`. One `__all__` tuple listing all six names in that order.

---

## 6. `pyproject.toml` change

In `freedom-agents/pyproject.toml`, under `[tool.setuptools]`, append `"agents.tools"` to the `packages` list. The existing package entries are not reordered.

---

## 7. Test files

All test files import only from `agents.tools` (the public surface) and from `pydantic`. No Django settings or database access needed — these are pure-Python unit tests. The test runner is pytest with the existing `pytest.ini` configuration.

Each test file defines its own local `BaseModel` subclasses (`EchoInput`, `EchoOutput`, etc.) and a local toolset/tool fixture. No test fixture is shared across files.

### 7.1 `tests/unit/test_tool_contracts.py`

Tests to include:

- `ToolExecutionError` can be constructed with `message` alone; all optional attributes default to `None`.
- `ToolExecutionError` constructed with all fields stores each as the correct attribute.
- `str(ToolExecutionError("boom"))` contains `"boom"` (default Exception str behaviour).
- `ToolDef` is a frozen dataclass: assigning to any field after construction raises `FrozenInstanceError`.
- `ToolDef` stores all five fields with the values passed to the constructor.

### 7.2 `tests/unit/test_toolset.py`

Define a local `EchoToolset(Toolset)` with `name = "echo"`, one `@tool`-decorated method `say(self, input: EchoInput) -> EchoOutput`, and one non-decorated method `_helper`. `EchoInput` has a single field `text: str`; `EchoOutput` has a single field `result: str`.

Tests to include:

- `EchoToolset().get_tools()` returns a list of exactly one `ToolDef`.
- That `ToolDef` has `name == "echo.say"`.
- `input_model` is `EchoInput` and `output_model` is `EchoOutput`.
- `_helper` is not in the returned list (non-decorated methods are excluded).
- A toolset method decorated with `@tool(name="custom")` produces a `ToolDef` with `name == "echo.custom"`.
- Class-level `tags = frozenset({"a"})` plus `@tool(tags={"b"})` produces `tags == frozenset({"a", "b"})`.
- `@tool(output_model=OtherOutput)` overrides the return annotation.
- A method decorated with `@tool` but with no `BaseModel`-typed parameter raises `TypeError` from `get_tools()`.

### 7.3 `tests/unit/test_tool_registry.py`

Define a local `EchoToolset` (same shape as above) and a local `TaggedToolset` containing a method decorated with `@tool(tags={"mcp_safe"})` and a method without that tag.

Tests to include:

- After `registry.register(toolset)`, `registry.names()` includes the expected tool names sorted.
- `registry.get("echo.say")` returns the expected `ToolDef`.
- `registry.toolsets()` returns the registered toolset instance.
- Registering two toolsets whose tool names collide raises `ValueError`; the registry is not partially updated on conflict.
- `registry.get("unknown")` raises `KeyError`.
- `registry.run("echo.say", {"text": "hi"})` calls the bound method and returns an `EchoOutput` with the correct value.
- `registry.run("echo.say", EchoInput(text="hi"))` also works (pre-validated `BaseModel` path).
- `registry.run("echo.say", {"wrong_field": 1})` raises Pydantic `ValidationError` and the method is never entered (verify with a spy — replace the bound method via `unittest.mock.patch` or a counter on the toolset).
- `registry.names(tags={"mcp_safe"})` returns only tools whose tags are a superset; names with no such tag are excluded.
- `registry.names(tags={"nonexistent"})` returns `[]`.
- `default_registry` imported from `agents.tools` in two separate import statements (or via `importlib.reload`) is the same object (`is` check), confirming module-level singleton semantics.
- `default_registry` has no tools registered at import time (`registry.names() == []`).

---

## 8. Validation order

Implement and verify in this order:

1. `contracts.py` + `test_tool_contracts.py` — zero dependencies.
2. `toolset.py` + `test_toolset.py` — depends on `contracts.py`.
3. `registry.py` + `test_tool_registry.py` — depends on both.
4. `__init__.py` — wire exports, confirm `from agents.core.tools import ...` works.
5. `pyproject.toml` — add package entry, confirm no import error from a fresh install path.

Run `pytest tests/unit/test_tool_contracts.py tests/unit/test_toolset.py tests/unit/test_tool_registry.py -v` after each step.

---

## 9. Out of scope (not touched in this story)

- `freedom-plane-agent` migration to the new `Toolset` base.
- PydanticAI adapter (`get_pydantic_ai_tools`).
- MCP server registry mount.
- Async `run()` variant.
- Settings-driven `AGENTS_TOOL_MODULES` auto-registration.
- Any changes to `tests/settings.py`, `conftest.py`, or `pytest.ini`.
