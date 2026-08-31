# HLD — Build tool contracts and registry

**Work item:** #380 · **Module:** Research · **Repo:** `freedom-agents`
**Parent HLD:** `research-agent/spec/research-agent/typed-search-and-scrape-tool-module/HLD.md` (§3, §4, §7, §9, §11)

## 1. Purpose

Ship the foundational **typed tool layer** that the rest of the Tool Framework (search_web, scrape_url, future tool libraries, and the on-demand MCP server) depends on. This story delivers only the authoring surface and registry — `Toolset` base class, `@tool` decorator, `ToolDef`, `ToolRegistry`, `ToolExecutionError`, and a module-level `default_registry`. Concrete tool libraries and adapters (PydanticAI bridge, MCP server) are out of scope and land in follow-up stories.

The work was originally scoped under `research-agent/src/tools/` in the parent HLD. Per `project-plan.md` v0.4 (R3) the Tool Framework has been **relocated to `freedom-agents`** so it can be reused across host apps (research-agent, MeML pipelines, future agents). This HLD also reflects a further refinement: the authoring unit shifts from a per-tool `Tool` Protocol (parent §4) to a **`Toolset`** class that bundles related operations sharing config — matching the proven pattern already in use in `freedom-plane-agent`.

## 2. Conceptual model

`freedom-agents` owns the **authoring surface**. Host apps **extend** it by writing `Toolset` subclasses, decorating methods with `@tool`, and self-registering on Django app startup.

```
freedom-agents (this repo)        host app (e.g. research-agent, a Django app)
  agents.tools.Toolset    <─────  class SearchToolset(Toolset): ...
  agents.tools.tool       <─────  @tool(tags={"mcp_safe"}) def search_web(...): ...
  agents.tools.ToolRegistry        AppConfig.ready() → default_registry.register(SearchToolset(...))
  agents.tools.default_registry
```

This is deliberately **not** the `StepCatalog` / `AgentConfigCatalog` pattern already in `freedom-agents`:

| Concept | What it represents | Lookup key | Registration |
|---|---|---|---|
| `StepCatalog` | Pipeline node (durable, may recruit tools) | step key | classmethod on global class |
| `AgentConfigCatalog` | Named factory for `AgentConfig` | config key | classmethod on global class |
| `ToolRegistry` *(new)* | External-action primitives, bundled per toolset | `f"{toolset.name}.{method_name}"` | instance method on a module-level singleton, called from `AppConfig.ready()` |

Tools and steps share no abstractions. A step may call `registry.run("search.search_web", …)`; a tool never calls a step.

### 2.1 Relationship to existing tool surfaces

`freedom-plane-agent` already implements this exact pattern, hand-rolled:

- `freedom_plane_agent/api/tools.py` — `PlaneToolset` class with `*_tool` methods, exposed via `get_tools()` as a `list[pydantic_ai.Tool]`.
- `freedom_plane_agent/mcp/tools_adapter.py` — reflection-based discovery wrapping the same methods as FastMCP tools on port 8123.

The new `Toolset` base class in `freedom-agents` is the **formalization** of that pattern, lifted into a shared library. The boilerplate (reflection, adapter wiring, MCP server, PydanticAI bridge) lives once in `freedom-agents` instead of being re-implemented in every host app.

- **Today:** `freedom-plane-agent` is independent — not consumed by `freedom-agents`, not registered in `default_registry`.
- **Future migration (out of scope for #380):** `PlaneToolset` becomes a `Toolset` subclass, registers into `default_registry` via its existing `AppConfig.ready()`, and the standalone `mcp/tools_adapter.py` is replaced by the generic MCP server (#2828ba7e) reading from the registry. No rewrite of behavior — just a renaming of the base class and removal of duplicate adapter code.
- **Open question (deferred):** whether the future generic MCP server subsumes the Plane FastMCP on :8123 or whether they coexist. The `tags={"mcp_safe"}` filter on the registry is built to make either choice possible without touching individual tools.

## 3. Module layout

A new flat sub-package at the `freedom-agents` root, alongside `step_catalog.py` and `agent_config_catalog.py`:

```
freedom-agents/
  tools/
    __init__.py          # re-exports the public surface
    contracts.py         # ToolDef dataclass, ToolExecutionError
    toolset.py           # Toolset base class + @tool decorator
    registry.py          # ToolRegistry class + module-level default_registry
  tests/unit/
    test_tool_contracts.py
    test_toolset.py
    test_tool_registry.py
```

Public import path: `from agents.core.tools import Toolset, tool, ToolDef, ToolRegistry, ToolExecutionError, default_registry`.

The setuptools package is named `agents` (`[tool.setuptools.package-dir] agents = "."`), so `tools/` becomes the dotted module `agents.tools`.

## 4. Authoring surface

### 4.1 `Toolset` base class (`toolset.py`)

```python
class Toolset:
    name: ClassVar[str]                            # toolset namespace, e.g. "search"
    tags: ClassVar[frozenset[str]] = frozenset()   # tags inherited by every tool method

    def get_tools(self) -> list[ToolDef]:
        """Reflect over the instance, return a ToolDef for every @tool-decorated method."""
```

- Subclasses set `name` (required) and optionally `tags`.
- Subclasses define stateful config in `__init__` (clients, credentials, URLs) — shared across all tool methods on that instance, exactly like `PlaneToolset.service`.
- `get_tools()` is implemented once in the base class via reflection on `@tool`-decorated bound methods.

### 4.2 `@tool` decorator (`toolset.py`)

```python
def tool(
    *,
    name: str | None = None,                      # default: method.__name__
    tags: Iterable[str] = (),                     # merged with toolset.tags
    output_model: type[BaseModel] | None = None,  # default: from return annotation
) -> Callable: ...
```

- Marks a method as a registered tool. Methods without `@tool` are not exposed, even if their name ends in `_tool` — the decorator is the **single source of truth** for discovery (no suffix magic).
- The decorated method must have exactly one annotated parameter (after `self`) whose type is a `BaseModel` subclass — this becomes `input_model`. The return annotation is `output_model` (decorator-provided override wins).
- Per-method `tags` are unioned with the toolset's class-level `tags`.

### 4.3 `ToolDef` (`contracts.py`)

The internal record produced by `get_tools()` and stored in the registry:

```python
@dataclass(frozen=True)
class ToolDef:
    name: str                           # fully qualified, e.g. "search.search_web"
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    tags: frozenset[str]
    callable: Callable[[BaseModel], BaseModel]   # bound method
```

`ToolDef` is what the registry holds. Host-app code never constructs it directly — it falls out of `Toolset.get_tools()`.

### 4.4 Authoring example

```python
class SearchToolset(Toolset):
    name = "search"

    def __init__(self, searxng_url: str):
        self.client = SearxngClient(searxng_url)

    @tool(tags={"mcp_safe"})
    def search_web(self, input: SearchWebInput) -> SearchWebOutput:
        return self.client.search(input)
```

Resulting tool: `name="search.search_web"`, `tags=frozenset({"mcp_safe"})`, `input_model=SearchWebInput`, `output_model=SearchWebOutput`.

## 5. Error model (`contracts.py`)

```python
class ToolExecutionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        tool_name: str | None = None,
        input_snapshot: dict | None = None,
        provider_status: int | None = None,
        provider_body: str | None = None,
    ) -> None: ...
```

- Single positional `message` matches the call sites already prototyped in #388 / #391 (e.g. `raise ToolExecutionError("config: SEARXNG_URL missing")`).
- All metadata fields are keyword-only and optional. Config-time errors raised before any provider call can omit them.
- **v1 fail-loud policy.** No code in `agents.tools` catches `ToolExecutionError`. The workflow upstream decides whether to mark work `failed` and move on.

### 5.1 Host integration via `AppConfig.ready()`

Tool libraries are expected to ship as **Django apps**. Their `AppConfig.ready()` is the canonical registration point:

```python
# search_tools/apps.py
class SearchToolsConfig(AppConfig):
    name = "search_tools"

    def ready(self):
        from django.conf import settings
        from agents.core.tools import default_registry
        from search_tools.toolset import SearchToolset

        default_registry.register(SearchToolset(settings.SEARXNG_URL))
```

The host application's contract is:

```python
# host_app/settings.py
INSTALLED_APPS = [..., "search_tools"]
SEARXNG_URL = env("SEARXNG_URL")          # documented by the library
```

That is the entirety of the host-side wiring. No imports, no manual `register()` calls. This matches `freedom-plane-agent`'s existing `PlaneAgentConfig` pattern.

`freedom-agents` itself does **not** auto-discover or auto-import any tool libraries. The trigger is Django's app loader walking `INSTALLED_APPS`.

## 6. Registry (`registry.py`)

```python
class ToolRegistry:
    def register(self, toolset: Toolset) -> None: ...           # expands via toolset.get_tools()
    def get(self, name: str) -> ToolDef: ...                    # fully-qualified name
    def run(self, name: str, input: dict | BaseModel) -> BaseModel: ...
    def names(self, *, tags: Iterable[str] | None = None) -> list[str]: ...
    def toolsets(self) -> list[Toolset]: ...                    # registered toolsets, in registration order

default_registry = ToolRegistry()  # module-level singleton
```

**Behavioral contract:**

| Method | Behavior |
|---|---|
| `register(toolset)` | Calls `toolset.get_tools()` and stores each `ToolDef` keyed by `tool_def.name`. Raises `ValueError` if any tool name collides with an existing entry (no silent overwrite — v1 fail-loud). |
| `get(name)` | Returns the `ToolDef`. Raises `KeyError` on unknown name. **No auto-discovery.** |
| `run(name, input)` | If `input` is a dict, validate against `tool_def.input_model` (raising Pydantic `ValidationError`) **before** calling `tool_def.callable`. If `input` is already a `BaseModel` of the right type, pass through. Returns whatever the tool returns (typed as `BaseModel`). |
| `names(tags=None)` | Returns `sorted(self._tools)` when `tags=None`. When `tags` is given, returns names whose `tool_def.tags` is a **superset** of the requested set. |
| `toolsets()` | Returns registered toolset instances (used by the future PydanticAI adapter to call `get_pydantic_ai_tools()` per toolset). |

**`default_registry`** starts **empty** at import time of `agents.tools`. Population happens exclusively via host-app `AppConfig.ready()` calls.

**Explicitly out of v1:**
- Tool versioning / namespacing beyond `toolset.method` (no `search_web:searxng` keys yet).
- Async `run()` variant.
- PydanticAI adapter (`get_pydantic_ai_tools(...)`) — separate ticket.
- MCP server mount adapter — separate ticket (#2828ba7e).

## 7. Public surface (`__init__.py`)

```python
from agents.core.tools.contracts import ToolDef, ToolExecutionError
from agents.core.tools.toolset import Toolset, tool
from agents.core.tools.registry import ToolRegistry, default_registry

__all__ = (
    "Toolset", "tool",
    "ToolDef", "ToolExecutionError",
    "ToolRegistry", "default_registry",
)
```

## 8. Packaging

`freedom-agents/pyproject.toml` currently lists:

```toml
[tool.setuptools]
packages = [
    "agents", "agents.management", "agents.management.commands",
    "agents.migrations", "agents.temporal", "agents.temporal.plugins",
]
```

Add `"agents.tools"` to that list. Without this, the new package is excluded from the installed wheel and host apps cannot import it.

## 9. Tests

All test modules live under `tests/unit/` and use the existing pytest setup (`agents.tests.settings`, `conftest.py`).

**`tests/unit/test_tool_contracts.py`**

- `ToolExecutionError` carries every field round-trip; positional-only `message` works as documented.
- `ToolExecutionError` constructible with only `message` (config-time error path).
- `ToolDef` is a frozen dataclass; mutation raises.

**`tests/unit/test_toolset.py`**

A test-local `EchoToolset` defines one `@tool`-decorated method `say(self, input: EchoInput) -> EchoOutput`.

- `EchoToolset(...).get_tools()` returns one `ToolDef` with `name="echo.say"`, correct `input_model`/`output_model`, and tag union of class + decorator.
- Methods without `@tool` are not discovered, even if named `*_tool`.
- `@tool(name="custom")` overrides the method name in the fully qualified key.
- `@tool(output_model=Other)` overrides the return annotation.
- A `@tool` method missing a `BaseModel`-typed input parameter raises a clear error at `get_tools()` time.

**`tests/unit/test_tool_registry.py`**

- `register(toolset)` expands and stores every tool; `names()` returns them sorted.
- Re-registering a toolset with a colliding tool name raises `ValueError`.
- `get("unknown")` raises `KeyError`.
- `run("echo.say", {"text": "hi"})` invokes the method and returns the expected `BaseModel`.
- `run("echo.say", {"wrong_field": 1})` raises Pydantic `ValidationError` **before** the method is called (spy asserts method not entered).
- `run` accepts a pre-validated `BaseModel` and passes it through.
- `names(tags={"mcp_safe"})` filters to tools whose `tags` is a superset; `names(tags={"missing"})` returns `[]`.
- `default_registry` is the same instance across re-imports of `agents.tools` and starts empty.

No `EchoToolset` ships in `agents.tools`; it lives only in tests.

## 10. Failure modes (summary)

| Condition | Behavior |
|---|---|
| Tool name not in registry | `KeyError` (no auto-discovery) |
| Duplicate tool name on `register(toolset)` | `ValueError` (no silent overwrite) |
| Input dict fails Pydantic validation | `ValidationError` raised before the tool method is called |
| `@tool` method has no annotated `BaseModel` input parameter | raise at `get_tools()` time with a clear message |
| Tool method itself raises | propagates (only providers should raise `ToolExecutionError`) |

Provider-level failure rows (env vars, non-2xx, timeouts) are documented in parent HLD §9 and apply to **concrete tools** — they are not surfaced by the registry itself.

## 11. Acceptance criteria

- `from agents.core.tools import Toolset, tool, ToolDef, ToolRegistry, ToolExecutionError, default_registry` succeeds.
- A test-local `EchoToolset(Toolset)` with `name = "echo"` and one `@tool def say(self, input: EchoInput) -> EchoOutput` can be registered into a fresh `ToolRegistry()`. After registration, `registry.run("echo.say", {"text": "hi"})` returns the expected output.
- `ToolRegistry().get("unknown")` raises `KeyError`.
- `registry.run("echo.say", {"wrong_field": 1})` raises Pydantic `ValidationError` before `EchoToolset.say` is called.
- `registry.names(tags={"mcp_safe"})` returns only tools whose merged (class + decorator) tags is a superset of `{"mcp_safe"}`.
- `default_registry` is empty until at least one host package calls `default_registry.register(...)`.
- `freedom-agents/pyproject.toml` includes `agents.tools` in its `packages` list.

## 12. Out of scope (deferred to follow-ups)

- Concrete tool libraries (`SearxngSearchToolset`, `FirecrawlScrapeToolset`) — separate stories #381, #382.
- PydanticAI compatibility adapter (`get_pydantic_ai_tools`).
- Generic MCP server mounting the registry (#2828ba7e).
- Migration of `freedom-plane-agent` `PlaneToolset` onto this base class (no behavior change, mechanical refactor — separate ticket).
- Async `run()` variant.
- Tool versioning / namespaced keys beyond `toolset.method`.
