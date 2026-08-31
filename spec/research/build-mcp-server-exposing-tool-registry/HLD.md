# HLD — Build MCP server exposing the tool registry

**Work item:** #396 · **Module:** Research · **Repo:** `freedom-agents`
**State:** Draft · 2026-05-14
**Authoritative parent HLD:** [`../build-toolset-to-mcp-exposure/HLD.md`](../build-toolset-to-mcp-exposure/HLD.md) (frozen).

This HLD is the work-item-scoped distillation of the parent HLD for ticket #396. The parent HLD is the design source of truth; this document specifies what gets shipped, where files land, and how the ticket is verified. Where the legacy Plane-ticket acceptance criteria conflict with the parent HLD (runserver auto-start, per-tool `register(tool, expose_mcp=...)`), the parent HLD wins per its §13 supersedence note — this HLD reconciles those.

---

## 1. Scope shipped by #396

Per parent HLD §13, #396 covers the **toolset-to-MCP exposure layer end-to-end** inside `freedom-agents`:

1. `ToolSet` base class + `@tool` decorator + `Tool` runtime descriptor (`agents.tools.toolset`, `agents.tools.contracts`).
2. Registry rewrite: `register_toolset` is the only entry point; `expose_mcp` × `mcp_safe` gating enforced at registration (`agents.tools.registry`).
3. `agents.tools.mcp` package — dynamic adapter, server build, transport runner.
4. Two management commands: `run_tools_mcp`, `list_toolsets`.
5. `fastmcp` added to runtime dependencies.

The pre-existing `tools/contracts.py` and `tools/registry.py` (shipped by #380 in their pre-refinement shape) are rewritten to match this surface. The work item description's older AC list (`default_registry.register(tool, expose_mcp="")`, runserver auto-start on port 8200+) is **not** implemented — those describe a superseded design.

### 1.1 Out of scope (deferred)

- Migrating `freedom-plane-agent`'s `PlaneToolset` onto the new base class (separate ticket; parent HLD §11).
- Pi-side STDIO subprocess declarations (parent HLD §10).
- Concrete tool libraries (`WebResearchToolSet` etc.) — separate downstream tickets.
- Auth, rate limiting, observability, async tools, streaming, multi-toolset-per-server.
- A management command to list bound ports per group (not applicable — no boot-time port supervisor exists).

---

## 2. Why the runserver auto-start AC is dropped

The legacy AC said "`runserver` brings up one HTTP FastMCP server per distinct key on ports 8200+." The parent HLD §5 supersedes this with an **explicit management command** (`run_tools_mcp --toolset NAME`), defaulting to STDIO transport. Rationale:

- A pi-spawned agent expects one MCP subprocess per attached toolset over STDIO — auto-binding HTTP ports inside `runserver` doesn't serve that path.
- Side-effects in `runserver` make `migrate`, `test`, `shell`, `run_temporal_worker` harder to reason about (the AC about non-runserver commands not opening ports falls out naturally if MCP is command-gated, not boot-gated).
- One toolset = one server is the parent HLD's invariant; a runserver supervisor would multiplex, which the design explicitly rejects.

The "no MCP port opened by `migrate`/`test`/`shell`/`run_temporal_worker`" AC remains in force and is trivially satisfied because nothing in `AppConfig.ready()` opens a port — registration is in-memory only.

---

## 3. Deliverables — file targets

```
freedom-agents/tools/
  contracts.py       # Tool descriptor (dataclass), ToolExecutionError                  [rewritten]
  toolset.py         # ToolSet base class + @tool decorator                              [new]
  registry.py        # ToolRegistry (register_toolset + flat get/run/names)              [rewritten]
  __init__.py        # public surface: ToolSet, tool, Tool, ToolRegistry,                [updated]
                     #                 ToolExecutionError, default_registry
  mcp/
    __init__.py
    adapter.py       # build_tool_adapter(tool) -> callable with Pydantic-derived sig    [new]
    server.py        # build_mcp_server(toolset_name, *, registry) -> FastMCP            [new]
    runner.py        # run(toolset_name, transport, host, port, name) — transport boot   [new]

freedom-agents/management/commands/
  run_tools_mcp.py   # thin CLI wrapper around agents.tools.mcp.runner.run               [new]
  list_toolsets.py   # introspection: --module M, --exposed-only                         [new]

freedom-agents/tests/unit/
  test_tool_contracts.py     # exists — keep passing, extend for new descriptor shape
  test_toolset.py            # new — @tool decoration, ToolSet.get_tools-equivalent
  test_tool_registry.py      # exists — keep passing, extend for register_toolset path
  test_mcp_adapter.py        # new — signature mirrors input_model; ValidationError path
  test_mcp_server_build.py   # new — registry → FastMCP wiring; gating refusals
  test_management_commands.py # new — run_tools_mcp + list_toolsets behavior

freedom-agents/pyproject.toml  # add "agents.tools.mcp" to packages; add fastmcp dep
```

`plane_agent/mcp/` is **not** touched in this ticket (parent HLD §11 covers the eventual migration as a separate work item).

---

## 4. Public surface

```python
# agents/tools/__init__.py
from agents.core.tools.contracts import Tool, ToolExecutionError
from agents.core.tools.toolset   import ToolSet, tool
from agents.core.tools.registry  import ToolRegistry, default_registry

__all__ = (
    "ToolSet", "tool",
    "Tool", "ToolExecutionError",
    "ToolRegistry", "default_registry",
)
```

`agents.tools.mcp` is internal — host apps never import from it. Its only consumer is the two management commands.

---

## 5. Authoring contract (mirrors parent HLD §2)

```python
class WebResearchToolSet(ToolSet):
    name = "web_research"

    def __init__(self):
        self.searxng_url = os.environ["SEARXNG_URL"]   # raises on misconfig

    @tool(input_model=SearchWebInput, output_model=SearchWebOutput, mcp_safe=True)
    def search_web(self, input: SearchWebInput) -> SearchWebOutput: ...
```

Registration (parent HLD §4):

```python
# host_app/apps.py
class HostConfig(AppConfig):
    def ready(self):
        from agents.core.tools import default_registry
        from host_app.toolsets import WebResearchToolSet
        default_registry.register_toolset(
            WebResearchToolSet, module=self.label, expose_mcp=True,
        )
```

Validation at registration time:
- `expose_mcp=True` with any non-`mcp_safe` member → `ValueError`.
- Duplicate toolset `name`, duplicate tool name across toolsets → `ValueError`.
- Tool method missing a `BaseModel` input arg → `TypeError` at decoration or registration (clear message).

---

## 6. Registry surface

```python
class ToolRegistry:
    # toolset surface (only write path)
    def register_toolset(self, toolset_cls, *, module: str, expose_mcp: bool = False) -> None: ...
    def get_toolset(self, name: str) -> type[ToolSet]: ...
    def toolset_names(self, *, modules=None, exposed_only=False) -> list[str]: ...
    def resolve_toolset(self, name: str) -> list[Tool]: ...

    # flat tool surface (derived; for in-process pipeline calls)
    def get(self, name: str) -> Tool: ...
    def run(self, name: str, input: dict | BaseModel) -> BaseModel: ...
    def names(self, *, modules=None) -> list[str]: ...

default_registry = ToolRegistry()
```

`register(tool)` (the pre-refinement entry point currently in `registry.py`) is removed. The pipeline-side `get/run/names` flat surface is kept because in-process callers index by tool name, not by toolset.

---

## 7. Adapter (parent HLD §7)

```python
def build_tool_adapter(tool: Tool) -> Callable[..., dict]:
    params = [
        inspect.Parameter(
            name, inspect.Parameter.KEYWORD_ONLY,
            default=(f.default if f.default is not PydanticUndefined else inspect.Parameter.empty),
            annotation=f.annotation,
        )
        for name, f in tool.input_model.model_fields.items()
    ]

    def adapter(**kwargs):
        input_obj = tool.input_model(**kwargs)        # ValidationError → MCP error
        output    = tool.bound_method(input_obj)      # ToolExecutionError → MCP error
        return output.model_dump(mode="json")

    adapter.__name__      = tool.name
    adapter.__signature__ = inspect.Signature(params, return_annotation=dict)
    return adapter
```

Server build:

```python
def build_mcp_server(toolset_name: str, *, registry=default_registry) -> FastMCP:
    if toolset_name not in registry.toolset_names(exposed_only=True):
        raise SystemExit(f"toolset '{toolset_name}' not registered with expose_mcp=True")
    server = FastMCP(name=toolset_name)
    for t in registry.resolve_toolset(toolset_name):
        server.tool(build_tool_adapter(t), name=t.name)
    return server
```

Runner picks transport (`stdio` default; `http`/`sse` honored for local dev) and calls `server.run(...)`.

---

## 8. Error mapping (parent HLD §8)

| Source | Effect |
|---|---|
| `ValidationError` inside adapter | MCP tool-call error response. Server stays up. |
| `ToolExecutionError` from `bound_method` | MCP tool-call error response carrying `tool_name`, `provider_status`, `provider_body`. Server stays up. |
| Config error in `ToolSet.__init__` | `register_toolset` raises during `AppConfig.ready()` → Django boot fails. |
| Toolset missing / `expose_mcp=False` / non-`mcp_safe` member | `SystemExit` before server starts (loud, command-line visible). |

---

## 9. Management commands

```bash
python manage.py run_tools_mcp --toolset NAME [--transport stdio|http|sse] [--host H] [--port P] [--name SERVER]
python manage.py list_toolsets [--module M] [--exposed-only]
```

`run_tools_mcp` refuses to start unless the toolset is registered with `expose_mcp=True`. Defaults: `--transport stdio`, `--host 127.0.0.1`, `--port` unset (HTTP/SSE only), `--name` defaults to toolset name. A one-line stderr log on startup announces resolved toolset + tool list (stdout is reserved for STDIO transport).

---

## 10. Tests — coverage map

| Area | File | Key cases |
|---|---|---|
| Tool descriptor / errors | `test_tool_contracts.py` | Frozen dataclass; `ToolExecutionError` round-trip; positional `message` only |
| `ToolSet` / `@tool` | `test_toolset.py` | Decorator records `input_model`, `output_model`, `mcp_safe`, name override; methods without `@tool` ignored; missing `BaseModel` input raises |
| Registry | `test_tool_registry.py` | `register_toolset` expands members; duplicate names raise; `expose_mcp=True` + non-`mcp_safe` member raises; `get/run/names` work; `toolset_names(exposed_only=True)` filters correctly |
| Adapter | `test_mcp_adapter.py` | Adapter `__signature__` mirrors `input_model.model_fields` exactly; bad kwargs → `ValidationError`; `ToolExecutionError` propagates unchanged; `output.model_dump(mode="json")` returned |
| Server build | `test_mcp_server_build.py` | `build_mcp_server(name)` registers one MCP tool per member; unknown / unexposed toolset → `SystemExit`; FastMCP not invoked at module import |
| Commands | `test_management_commands.py` | `run_tools_mcp` rejects non-exposed toolset; STDIO is default; `list_toolsets --exposed-only` filters; `migrate`/`test`/`shell` do not import `agents.tools.mcp.runner` |

The "registry boot gate" (no port opened by `migrate`/`test`/`shell`/`run_temporal_worker`) is asserted by importing those Django entry points in a subprocess and checking that `agents.tools.mcp.runner.run` is never reached. No network probe required because the runner is the only place that starts a transport.

---

## 11. Acceptance criteria (reconciled with parent HLD)

1. **Public surface.** `from agents.core.tools import ToolSet, tool, Tool, ToolRegistry, ToolExecutionError, default_registry` succeeds.
2. **Authoring.** A `ToolSet` subclass with `@tool`-decorated methods can be registered via `default_registry.register_toolset(cls, module="...", expose_mcp=True)`. Misconfig surfaces are loud (duplicate names, non-`mcp_safe` member with `expose_mcp=True`, missing `BaseModel` input).
3. **Adapter schema parity.** Each MCP-exposed tool's parameter schema mirrors `Tool.input_model.model_fields` 1:1 — no handwritten parameter lists.
4. **Error mapping.** A `ToolExecutionError` raised inside a bound tool method surfaces as an MCP tool-call error response; the server does not crash.
5. **Boot gate.** `python manage.py migrate`, `test`, `shell`, `run_temporal_worker` never open an MCP transport. Only `run_tools_mcp` does.
6. **Command gate.** `run_tools_mcp --toolset X` refuses when `X` was not registered with `expose_mcp=True`, with a clear stderr message.
7. **Demo path.** A trivial `EchoToolSet` (test-local or example app, not shipped in `agents.tools`) round-trips through `run_tools_mcp` over STDIO — used as the boot validation in tests.
8. **Compatibility.** All existing `freedom-agents` tests continue to pass. `freedom-plane-agent`'s `plane_agent/mcp/` is unchanged.
9. **Packaging.** `agents.tools.mcp` is listed in `pyproject.toml` packages; `fastmcp` is a runtime dependency.

---

## 12. Risks / open items

1. `fastmcp` runtime API stability. Pinned to the version `freedom-plane-agent` already uses; bump together if needed.
2. STDIO startup logging — must go to stderr, not stdout (stdout is the MCP transport). Asserted in tests.
3. `register_toolset` calls `toolset_cls()` eagerly during `AppConfig.ready()`. If a tool's `__init__` reads env vars that aren't set in test settings, Django startup fails for tests too. Mitigation: tests use a host app whose `ToolSet.__init__` is env-free, or the tested toolset is registered explicitly inside the test.
4. The parent HLD's open item §14.4 (auto-inferred input/output models from method hints) stays deferred. v1 is explicit-only.

---

## 13. Verification flow

```
1. unit tests:          pytest tests/unit/
2. command smoke:       python manage.py list_toolsets --exposed-only
3. STDIO round-trip:    python manage.py run_tools_mcp --toolset echo --transport stdio
                        (driven by an MCP client harness in test_management_commands.py)
4. boot-gate check:     run `migrate`, `test`, `shell`, `run_temporal_worker` in a subprocess
                        — assert no fastmcp transport is initialized
```
