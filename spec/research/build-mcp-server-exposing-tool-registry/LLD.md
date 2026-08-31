## LLD — Build MCP server exposing the tool registry

**Work item:** #396 · **Module:** `freedom-agents` (host app label: `agents`)
**State:** Draft · 2026-05-14
**Parent HLDs:**
- Authoritative: [`../build-toolset-to-mcp-exposure/HLD.md`](../build-toolset-to-mcp-exposure/HLD.md)
- Work-item-scoped: [`./HLD.md`](./HLD.md)

This LLD is the decision-complete implementation harness. The HLDs decided what gets built; this document fixes naming, file boundaries, error semantics, packaging, and the test plan in enough detail that implementation is mechanical. No design questions remain open after this is approved.

---

### 1. Scope confirmation

In-scope, ship under #396:

1. `agents.tools.contracts` — `Tool` descriptor (dataclass) + `ToolExecutionError` (kept).
2. `agents.tools.toolset` — `ToolSet` base + `@tool` decorator.
3. `agents.tools.registry` — `ToolRegistry`/`default_registry` rewrite (toolset-centric write path; flat read path).
4. `agents.tools.mcp` package — adapter, server build, transport runner.
5. Management commands `run_tools_mcp`, `list_toolsets` under `agents/management/commands/`.
6. Test-only `EchoToolSet` fixture used by adapter/server/command tests.
7. `pyproject.toml` — register the new package and add `fastmcp` runtime dep.
8. Migrate the `feedback_demo` example app from the old `Tool`-class shape onto `ToolSet`/`@tool`, including the playground view + template + E2E. The demo doubles as the STDIO boot-validation surface (HLD §7 AC).

Explicitly **not** in this ticket:
- Migrating `freedom-plane-agent/plane_agent/mcp/`. Untouched.
- Concrete production toolsets (e.g. `WebResearchToolSet`).
- pi-side wiring, auth, observability, async tools.

### 1.1 Current state of the tree (discovery, 2026-05-14)

Some of this ticket already has uncommitted scaffolding on disk. It targets the **pre-refinement** registry design (Protocol-based `Tool`, `tags`, single `register(tool)` write path) — i.e. the shape #380 was originally specified for, before the parent HLD §13 superseded it. This LLD treats those files as **drafts to be rewritten in place**, not as greenfield additions.

| Path | State on disk | Disposition under #396 |
|---|---|---|
| `tools/contracts.py` | Untracked. `Tool` is a `runtime_checkable` `Protocol` with a `tags: frozenset[str]` field. `ToolExecutionError` is correct. | Rewrite `Tool` to the frozen dataclass in §3. Keep `ToolExecutionError` verbatim. |
| `tools/registry.py` | Untracked. Single `register(tool) → register(Tool)` write path; `names(*, tags=…)` filter. No toolset awareness. | Rewrite to the surface in §5. The old `register(tool)` and `names(tags=…)` are deleted, not deprecated. |
| `tools/__init__.py` | Untracked. Exports `Tool, ToolExecutionError, ToolRegistry, default_registry`. | Add `ToolSet, tool` to the export tuple per §10. |
| `tests/unit/test_tool_contracts.py` | Untracked. Asserts the Protocol shape and a `tags=frozenset()` field. | Rewrite cases per §12. Keep `test_tool_execution_error_*` exactly as-is. |
| `tests/unit/test_tool_registry.py` | Untracked. Covers `register(tool)` duplicates, `names(tags={"mcp_safe"})`, etc. | Rewrite per §12 — duplicates become toolset/tool-name collisions; `tags` filter goes away. |
| `pytest.ini` | Modified (adds `django_find_project = false`). | Leave as-is; unrelated change rides along. |
| `examples/feedback_demo/feedback/tools.py` | Untracked. Defines an `EchoTool` class with `tags={"demo", "mcp_safe"}` that calls `default_registry.register(EchoTool())` at module level. | Replace with an `EchoToolSet(ToolSet)` exposing `echo` via `@tool(mcp_safe=True)`. Drop module-level registration — the host app's `AppConfig.ready()` will call `register_toolset`. |
| `examples/feedback_demo/feedback/apps.py` | Modified. `FeedbackConfig.ready()` imports the tools module to trigger registration. | Switch to `default_registry.register_toolset(EchoToolSet, module=self.label, expose_mcp=True)`. Drop the side-effect import. |
| `examples/feedback_demo/feedback/views.py` | Modified. `tool_playground` reads `default_registry.get(name).tags`; `tool_invoke` runs by flat name. | `tags` access goes away — replace with `mcp_safe` + owning toolset name. `tool_invoke` keeps using `default_registry.run(name, …)` (flat surface preserved). |
| `examples/feedback_demo/feedback/templates/feedback/tool_playground.html` | Untracked. Renders tag pills. | Render `mcp_safe=yes/no` + toolset chip instead of tag pills. |
| `examples/feedback_demo/test_tool_e2e.py` | Untracked. Includes `test_tag_filter` asserting `names(tags={"mcp_safe"})`. | Rewrite `test_tag_filter` → `test_toolset_lookup` using `toolset_names(exposed_only=True)` + `resolve_toolset`. |

Everything else in the in-scope list is genuinely new — no `ToolSet`/`@tool`/`expose_mcp`/`mcp_safe`/`fastmcp` references exist anywhere in the `freedom-agents` tree today (verified by `grep -rE "ToolSet|@tool\b|fastmcp|FastMCP|expose_mcp|mcp_safe|register_toolset"`).

Two HLD-level frictions are resolved here, not deferred:

- **Legacy Plane AC about `runserver` auto-binding ports 8200+.** Dropped per work-item HLD §2. The boot-gate AC ("`migrate`/`test`/`shell`/`run_temporal_worker` never open an MCP port") is preserved and is satisfied because `agents.tools.mcp.runner` is the only module that touches a transport, and it is imported only from the management command — never from `AppConfig.ready()` or `agents.tools.__init__`.
- **`default_registry.register(tool, expose_mcp="…")` AC.** Dropped. `register_toolset(cls, *, module, expose_mcp)` is the sole write path. A single-tool toolset is the migration path for any caller that previously wanted "just register one tool."

---

### 2. File map and ownership

```
freedom-agents/
  tools/
    __init__.py            REVISE-DRAFT — exists; add ToolSet, tool to the export tuple per §10.
    contracts.py           REWRITE-DRAFT — exists w/ Protocol+tags shape; rewrite to dataclass per §3.
    toolset.py             NEW — ToolSet base class; @tool decorator; method-walk helper.
    registry.py            REWRITE-DRAFT — exists w/ register(tool)/tags; rewrite per §5.
    mcp/
      __init__.py          NEW — empty; just a package marker. No public surface.
      adapter.py           NEW — build_tool_adapter(tool) -> Callable[..., dict].
      server.py            NEW — build_mcp_server(toolset_name, *, registry) -> FastMCP.
      runner.py            NEW — run(toolset_name, *, transport, host, port, name).
  management/commands/
    run_tools_mcp.py       NEW — thin Django Command wrapping runner.run.
    list_toolsets.py       NEW — introspection command.
  tests/unit/
    test_tool_contracts.py     REWRITE-DRAFT — exists; rewrite per §12 (drop Protocol+tags cases).
    test_toolset.py            NEW — @tool decoration + method-walk semantics.
    test_tool_registry.py      REWRITE-DRAFT — exists; rewrite per §12 (drop register(tool)/tags).
    test_mcp_adapter.py        NEW — signature parity; ValidationError; ToolExecutionError propagation.
    test_mcp_server_build.py   NEW — wiring, refusal paths, no FastMCP at import time.
    test_management_commands.py NEW — command gate + STDIO default + list filtering.
    test_boot_gate.py          NEW — subprocess: non-runserver entry points never import runner.
    _toolsets.py               NEW (test support) — EchoToolSet + EnvToolSet fixtures.
  examples/feedback_demo/feedback/
    tools.py                                 REWRITE-DRAFT — EchoTool class → EchoToolSet(ToolSet)
                                                              with @tool(mcp_safe=True).
    apps.py                                  REVISE — register_toolset(..., expose_mcp=True)
                                                       instead of side-effect import.
    views.py                                 REVISE — tool_playground drops .tags;
                                                       surfaces mcp_safe + toolset name.
    templates/feedback/tool_playground.html  REVISE-DRAFT — tag pills → mcp_safe + toolset chips.
  examples/feedback_demo/
    test_tool_e2e.py                         REVISE-DRAFT — test_tag_filter → test_toolset_lookup.
  pyproject.toml             UPDATED — packages += "agents.tools.mcp"; deps += "fastmcp>=2,<3".
```

`plane_agent/mcp/` is not opened, edited, or imported by this ticket. `freedom-plane-agent/pyproject.toml` is untouched.

**Legend.** `NEW` = file does not exist yet. `REWRITE-DRAFT` = file exists as part of the pre-refinement scaffold (mostly uncommitted) and is rewritten in place to match this design. `REVISE-DRAFT` / `REVISE` = file exists and needs targeted edits, not a full rewrite. `UPDATED` = tracked file, small additive edits.

---

### 3. `Tool` descriptor — final shape

`Tool` becomes a **frozen `@dataclass(slots=True, frozen=True)`** in `tools/contracts.py`. Fields, in declaration order:

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Final tool name (post-decorator override). Globally unique across the registry. |
| `input_model` | `type[pydantic.BaseModel]` | Authoritative parameter schema. |
| `output_model` | `type[pydantic.BaseModel]` | Used for adapter return-type annotation only; not enforced at runtime here. |
| `mcp_safe` | `bool` | Author's per-tool MCP gate (HLD §2/§6). |
| `toolset_name` | `str` | Backref to owning toolset (for diagnostics + adapter error mapping). |
| `bound_method` | `Callable[[BaseModel], BaseModel]` | The decorated method, already bound to the toolset instance. |

Removed: `tags`. The current `tags` field and `register(...tags...)`/`names(tags=...)` API are dropped; the parent HLD replaces tags with `mcp_safe` + `expose_mcp` + module ownership (HLD §12 "Out of scope"). Tests that depended on `tags` are rewritten to use those replacements.

`ToolExecutionError`: unchanged. Existing positional-`message` signature with optional kwargs `tool_name`, `input_snapshot`, `provider_status`, `provider_body` is preserved verbatim. The existing `test_tool_execution_error_*` cases stay green untouched.

The runtime-checkable `Protocol` form of `Tool` is removed — the descriptor is concrete now, and a Protocol with private methods would mask shape regressions.

---

### 4. `ToolSet` and `@tool` decorator

`tools/toolset.py` owns both.

**`ToolSet` base class:**

- Has one required class attribute: `name: ClassVar[str]`. Subclasses set this. The base class declares it without a default; instantiating a subclass that hasn't set it raises `TypeError` at `register_toolset` time, with the message `"<cls.__qualname__> must set class attribute 'name'"`.
- `__init__` on the base class is a no-op. Subclasses override freely; raising in `__init__` is the documented way to fail config (HLD §8 row 3) — `register_toolset` does not catch.
- No `get_tools()`/`iter_tools()` public method on the instance. Method-walking lives inside the registry (single source of truth). Keeps the `ToolSet` surface tiny.

**`@tool` decorator:**

- Signature: `tool(*, input_model: type[BaseModel], output_model: type[BaseModel], mcp_safe: bool = False, name: str | None = None)`.
- All arguments are keyword-only. No positional form. (HLD §2 used keyword form; this fixes it.)
- The decorator attaches metadata to the function object via a single private attribute `__agent_tool__` carrying a small `_ToolMeta` namedtuple of `(input_model, output_model, mcp_safe, name_override)`. The function is otherwise returned unchanged — methods stay normally callable from in-process code without going through the registry.
- Validation **at decoration time** (raised from the decorator, so import of a misdeclared toolset module is the failure surface):
  - `input_model` and `output_model` are both required and must be `BaseModel` subclasses; otherwise `TypeError("@tool input_model/output_model must be BaseModel subclasses")`.
  - The decorated callable must be a function (we cannot tell it's a method at decoration time, that check is deferred).
- Validation **at registration time** (raised from `register_toolset`):
  - The decorated function must take exactly two positional parameters after binding (`self`, `input`). Anything else → `TypeError` referencing the tool name and toolset name.
  - The `input` parameter's annotation, if present, must be the declared `input_model` or a subclass. Mismatch → `TypeError`. Missing annotation → soft warning logged to stderr, registration still proceeds. (Keeps test fixtures cheap.)

**Method discovery:** the registry walks `vars(cls)` over the MRO (excluding `object` and `ToolSet` itself), collecting attributes whose `__agent_tool__` marker is set. Inheritance is supported but not tested in v1; a subclass redeclaring a method with `@tool` shadows the parent. Methods without the marker are ignored — including helper methods, properties, and `__init__`.

---

### 5. `ToolRegistry` — write/read split

`tools/registry.py` owns one class plus the module-level singleton.

Internal state (`__init__`):

| Attribute | Type | Holds |
|---|---|---|
| `_toolsets` | `dict[str, type[ToolSet]]` | Toolset class by name (for `get_toolset`). |
| `_toolset_meta` | `dict[str, _ToolsetMeta]` | Per toolset: `module: str`, `expose_mcp: bool`, `instance: ToolSet`, `tools: list[Tool]` (in source order). |
| `_tools` | `dict[str, Tool]` | Flat tool name → `Tool` descriptor (for `get`/`run`/`names`). |

`_ToolsetMeta` is an internal dataclass — not exported.

**`register_toolset(toolset_cls, *, module, expose_mcp=False)`**, in order:

1. Validate `toolset_cls.name` is set and non-empty; reject duplicate toolset names with `ValueError("Toolset '<name>' is already registered.")`.
2. Instantiate `toolset_cls()`. Any exception raised by `__init__` propagates unchanged — this is by design (HLD §8 row 3).
3. Walk the MRO, collect decorated methods, build `Tool` descriptors with `bound_method=getattr(instance, attr_name)` (Python's normal binding). Iteration order is insertion order of `vars(cls)` per class, walking MRO most-derived-first; ties resolved by source order. Empty toolset (no `@tool` methods) is a hard error: `ValueError("Toolset '<name>' has no @tool-decorated methods.")`.
4. **MCP gate validation:** if `expose_mcp is True`, every collected tool must have `mcp_safe is True`. Otherwise raise `ValueError("Toolset '<name>' is expose_mcp=True but tool '<tool>' is not mcp_safe.")` — wording is part of the spec because tests assert on it.
5. **Cross-toolset tool-name uniqueness:** for each new tool, if its name already exists in `self._tools`, raise `ValueError("Tool '<tool>' is already registered by toolset '<owner>'.")`. Rollback: if step 5 fails midway through a multi-tool toolset, the registry must not be left half-populated. Implementation: build the full `list[Tool]`, then run uniqueness checks against `self._tools` before mutating any state. Only after all validations succeed do we mutate `_toolsets`, `_toolset_meta`, `_tools`.
6. Commit state.

Reads:

- `get_toolset(name) -> type[ToolSet]`: returns the **class**, not the instance. Raises `KeyError(name)` if absent.
- `toolset_names(*, modules=None, exposed_only=False) -> list[str]`: sorted; `modules` is an iterable of module labels for AND-style filtering (membership), `exposed_only=True` filters to `expose_mcp=True` toolsets.
- `resolve_toolset(name) -> list[Tool]`: returns the toolset's tools in registration order. Raises `KeyError(name)` if absent. **Not** filtered by `mcp_safe` — adapter callers know the toolset is already validated as fully `mcp_safe` (step 4).
- `get(name) -> Tool`, `run(name, input) -> BaseModel`, `names(*, modules=None) -> list[str]`: flat surface. `run` accepts `dict` (validated through `tool.input_model(**dict)`) or `BaseModel` instance (passed through). Pydantic `ValidationError` propagates to the caller, just like today.

`default_registry = ToolRegistry()` at module bottom.

---

### 6. MCP adapter — `tools/mcp/adapter.py`

`build_tool_adapter(tool: Tool) -> Callable[..., dict]` produces a function whose signature mirrors the input model's fields and whose body validates, calls, and serialises.

Fixed decisions:

- **Parameter kind:** all keyword-only. There is no positional form. Matches the parent HLD §7 spec and avoids subtle FastMCP schema differences across versions.
- **Defaults:** `f.default` is used when present and not `PydanticUndefined`; otherwise `inspect.Parameter.empty` so the parameter is required.
- **Annotations:** `f.annotation` is propagated unchanged. Pydantic-derived annotations (including `Optional`, `Annotated`, `list[str]`, etc.) are passed through; the schema FastMCP builds comes from these.
- **Return annotation:** `dict`. The function returns `output.model_dump(mode="json")` so MCP serialisation is deterministic across JSON-incompatible types (UUIDs, datetimes).
- **`__name__`/`__qualname__`:** both set to `tool.name`. `__doc__` is copied from `tool.bound_method.__doc__` if set, else left as `None`.
- **Error mapping:**
  - `pydantic.ValidationError` from `input_model(**kwargs)` is **not caught**. FastMCP turns it into a tool-call error response. Verified in tests by patching the FastMCP entrypoint.
  - `ToolExecutionError` from `bound_method` is **not caught**. Same propagation. Tests assert that the exception instance reaches FastMCP unchanged (attributes preserved).
  - Any other `Exception` from `bound_method` is **not caught**. Bugs surface as MCP errors with the original type, not as crashes. The server stays up — that is FastMCP's contract; we rely on it and assert it in `test_mcp_server_build.py`.

No global state. Adapter is built fresh per `build_mcp_server` call.

---

### 7. MCP server build — `tools/mcp/server.py`

`build_mcp_server(toolset_name: str, *, registry: ToolRegistry = default_registry) -> FastMCP`:

1. Look up the toolset via `registry.toolset_names(exposed_only=True)`. If `toolset_name` is not in that list, raise `SystemExit(2)` with stderr message `mcp.server.refused toolset=<name> reason=<not-registered|not-exposed>` — the two cases are distinguished by checking `toolset_name in registry.toolset_names()`.
2. Construct `FastMCP(name=toolset_name)`. Import of `fastmcp` happens here, not at module top, to keep `agents.tools.mcp.server` importable even if fastmcp is not installed (useful for `list_toolsets` and registry-only test paths). The import error is re-raised as `SystemExit(3)` with `mcp.server.refused reason=fastmcp-missing`.
3. For each tool in `registry.resolve_toolset(toolset_name)`, call `server.tool(build_tool_adapter(tool), name=tool.name)`.
4. Emit one stderr log line: `mcp.server.bound toolset=<name> tools=<comma-joined sorted names>`.
5. Return the `FastMCP` instance. The server is **not** started here — `runner.run` owns transport.

No multi-toolset path. No port allocation. No supervisor.

---

### 8. Runner — `tools/mcp/runner.py`

`run(toolset_name, *, transport="stdio", host="127.0.0.1", port=None, name=None, registry=default_registry) -> None`:

| Transport | Args used | FastMCP call |
|---|---|---|
| `stdio` | — | `server.run(transport="stdio")` |
| `http` | `host`, `port` (required; default 0 → bind any) | `server.run(transport="http", host=host, port=port)` |
| `sse` | `host`, `port` (same) | `server.run(transport="sse", host=host, port=port)` |

Decisions:

- Default `transport="stdio"` matches HLD §5 — this is the canonical pi-agent path.
- `--port` is required for `http`/`sse`. If omitted, the command exits with `SystemExit(2)` and stderr `mcp.runner.refused transport=<t> reason=port-required`. Auto-assigning a port is explicitly out of scope.
- `name` defaults to `toolset_name`; passed to `build_mcp_server` only insofar as FastMCP's display name — the registry lookup always uses `toolset_name`.
- All boot-time logging goes to **stderr**. Stdout is the STDIO transport. `runner.run` configures a `logging` handler bound to stderr at WARNING for the duration of the call; restored on exit.
- This module imports `fastmcp` (indirectly via `server.py`) and starts a transport. It must not be imported from any module that runs during `migrate`/`test`/`shell`/`run_temporal_worker`. Verified by `test_boot_gate.py`.

---

### 9. Management commands

`management/commands/run_tools_mcp.py`:

Django `BaseCommand` subclass. `add_arguments`:

| Arg | Type | Required | Default |
|---|---|---|---|
| `--toolset` | str | yes | — |
| `--transport` | choices=`stdio,http,sse` | no | `stdio` |
| `--host` | str | no | `127.0.0.1` |
| `--port` | int | no | `None` |
| `--name` | str | no | `None` |

`handle()` simply forwards to `agents.tools.mcp.runner.run(...)`. No business logic. This keeps the command trivially testable via direct `runner.run` calls; the command itself only exists to satisfy Django's `manage.py` surface.

`management/commands/list_toolsets.py`:

Django `BaseCommand`. `add_arguments`:

| Arg | Type | Default | Behaviour |
|---|---|---|---|
| `--module` | str (repeatable via `action="append"`) | `None` | Filter by module label. |
| `--exposed-only` | flag | `False` | Filter to `expose_mcp=True` toolsets only. |

Output to **stdout**, one toolset per line, in the shape `<toolset_name>\t<module>\texposed=<true|false>\ttools=<comma-joined names>`. Tab-separated for grep-friendliness; one decision, fixed. Empty result is an empty stdout (no header) and exit 0.

Neither command opens an MCP port unless explicitly invoked. `list_toolsets` does **not** import `agents.tools.mcp.runner`; it only reads the registry.

---

### 10. `tools/__init__.py` public surface

Final exports, in this order: `ToolSet, tool, Tool, ToolExecutionError, ToolRegistry, default_registry`.

`__all__` reflects the same tuple. `agents.tools.mcp` is **not** re-exported and remains internal. Anything that wants the MCP package imports `agents.tools.mcp.server` or `.runner` directly — both are reachable only via the management commands and tests.

---

### 11. Packaging — `pyproject.toml`

Two edits in `freedom-agents/pyproject.toml`:

1. `[tool.setuptools] packages` append `"agents.tools.mcp"`.
2. `[project] dependencies` append `"fastmcp>=2,<3"`. The version pin matches what `freedom-plane-agent` already vendors; if a version drift is found during implementation, the two packages bump together — not silently here.

No new dev dependency for tests: FastMCP's in-process client harness is shipped inside `fastmcp` itself.

---

### 12. Test plan

Tests live in `tests/unit/`. Tests **must not** modify `default_registry` — they construct fresh `ToolRegistry()` instances and pass `registry=…` into `build_mcp_server` / `runner.run`. The one exception, `test_boot_gate.py`, runs management commands in a subprocess.

**Test fixtures (`tests/unit/_toolsets.py`):**

- `EchoToolSet`: one `@tool(mcp_safe=True)` method `echo(self, input: EchoInput) -> EchoOutput` that returns `EchoOutput(result=input.text)`. Used by adapter/server/command tests.
- `UnsafeToolSet`: one `@tool` method (default `mcp_safe=False`). Used to assert the registration gate raises.
- `EnvToolSet`: `__init__` reads a required env var and raises `ToolExecutionError("config: ENV missing")` if absent. Used to assert config-time failures.
- `EmptyToolSet`: no `@tool` methods. Used to assert the empty-toolset registration error.

**File-by-file:**

| File | Cases (one bullet = one `test_…`) |
|---|---|
| `test_tool_contracts.py` | Frozen-dataclass identity equality; `ToolExecutionError` round-trip (positional `message` + each kwarg); `ToolExecutionError` defaults to `None`; `Tool` instance is hashable (slots); existing `test_tool_execution_error_*` cases preserved verbatim. Drop the protocol-shape test and the `tags` reference. |
| `test_toolset.py` | `@tool` attaches `__agent_tool__` with the right metadata; method without `@tool` is ignored; `@tool` with non-`BaseModel` input/output raises `TypeError` at decoration; `name` override applied; subclassing `ToolSet` without setting `name` is OK at class definition (only fails at register time). |
| `test_tool_registry.py` (rewritten) | `register_toolset` round-trips `get_toolset` and `resolve_toolset`; flat `get`/`run`/`names` reflect registered tools in source order; dict and `BaseModel` inputs both work in `run`; duplicate toolset name raises with the spec message; duplicate tool name across toolsets raises with the spec message; `expose_mcp=True` + non-`mcp_safe` member raises with the spec message; empty toolset raises; toolset without `name` raises `TypeError`; `toolset_names(modules=[…])` filters; `toolset_names(exposed_only=True)` filters; `register_toolset` failure leaves the registry untouched (assert state by-field). |
| `test_mcp_adapter.py` | `adapter.__signature__.parameters` keys equal `input_model.model_fields` keys in order; each parameter's `annotation` is the field annotation; required vs default parameters resolved correctly; calling adapter with valid kwargs returns `output.model_dump(mode="json")` (dict, JSON-roundtrippable); missing required kwarg raises `pydantic.ValidationError`; tool method raising `ToolExecutionError` propagates the instance unchanged (assert `provider_status`/`tool_name` preserved); `adapter.__name__` equals `tool.name`. |
| `test_mcp_server_build.py` | Building against a registered & exposed toolset produces a `FastMCP` with one registered tool per member; `build_mcp_server` for an unknown name raises `SystemExit` with `reason=not-registered`; for a registered-but-not-exposed name raises `SystemExit` with `reason=not-exposed`; `agents.tools.mcp.server` import does **not** import `fastmcp` at module top (assert via `sys.modules` cleanup + reimport); end-to-end echo via FastMCP's in-process client returns the expected dict. |
| `test_management_commands.py` | `call_command("run_tools_mcp", "--toolset", "echo")` with an unexposed registry raises `SystemExit`; `call_command("list_toolsets")` prints lines in the documented TSV shape; `--module` filter; `--exposed-only` filter; `list_toolsets` import path does not pull in `agents.tools.mcp.runner` (assert via fresh interpreter). `run_tools_mcp` actually starting a server is exercised by patching `runner.run` to a recording stub — the real STDIO transport is exercised separately via the FastMCP in-process client in `test_mcp_server_build.py`. |
| `test_boot_gate.py` | Spawns subprocesses running `python manage.py check`, `migrate --check`, `shell -c 'pass'`, `run_temporal_worker --help` (a `--help`-style call to avoid needing Temporal). For each, asserts the child's traced `sys.modules` after exit does **not** contain `agents.tools.mcp.runner`. Implementation: the subprocess writes `list(sys.modules)` to a temp file at exit via `atexit`. |

Existing tests in `tests/unit/` that don't reference the rewritten surface (`test_agent.py`, step/agent-config tests, temporal tests, `test_cli_wrappers.py`) must continue to pass untouched. The two old tool tests are rewritten in place rather than deleted-and-recreated to keep git history readable.

Coverage target: `agents.tools.*` should land at or above the project's current `--cov` baseline. The new `agents.tools.mcp.runner` may be partially uncovered because real transport `server.run(...)` is mocked in tests; document this explicitly in the runner module so future readers don't try to "fix" it.

---

### 13. Acceptance criteria — mapping to deliverables

| AC (work-item HLD §11) | Verified by |
|---|---|
| 1. Public surface importable | `test_agents_module_exports.py` extension + `test_tool_contracts.py`. |
| 2. Authoring + misconfig surfaces loud | `test_tool_registry.py` (duplicates, `mcp_safe` gate, empty toolset, missing `name`). |
| 3. Adapter schema mirrors `input_model` | `test_mcp_adapter.py` signature parity case. |
| 4. `ToolExecutionError` → MCP error, no crash | `test_mcp_adapter.py` propagation case + `test_mcp_server_build.py` in-process FastMCP roundtrip. |
| 5. Boot gate (no MCP transport from non-MCP commands) | `test_boot_gate.py`. |
| 6. `run_tools_mcp` refuses unexposed toolset | `test_management_commands.py`. |
| 7. Demo path — `EchoToolSet` STDIO roundtrip | `test_mcp_server_build.py` via FastMCP in-process client. STDIO transport itself is covered by manual verification in §14 below since FastMCP's transport-level loop is not unit-testable. |
| 8. Existing `freedom-agents` tests pass; `plane_agent/mcp/` untouched | CI `pytest tests/unit/` + `git status` check on `freedom-plane-agent`. |
| 9. `fastmcp` in deps; `agents.tools.mcp` packaged | `pyproject.toml` review + import smoke. |

---

### 14. Manual verification (one-time, after merge)

These are not automated because they require an external MCP client:

1. From the meml repo root, run `python manage.py list_toolsets --exposed-only` after wiring an `EchoToolSet` in an example app's `AppConfig.ready()`. Expect one line.
2. Run `python manage.py run_tools_mcp --toolset echo --transport stdio`. Drive it from `example_mcp_client.py` (already in the meml repo root) pointed at the subprocess. Expect a successful `echo` call returning `{"result": "hi"}`.
3. Run `python manage.py migrate`, `test`, `shell -c "import agents.core.tools"`, `run_temporal_worker` (against a no-op queue), and confirm no `mcp.server.bound` log line appears on stderr.

---

### 15. Implementation order

Strict order — each step's tests are green before the next starts:

1. `tools/contracts.py` rewrite (dataclass) + `test_tool_contracts.py` update.
2. `tools/toolset.py` (`ToolSet` + `@tool`) + `test_toolset.py`.
3. `tools/registry.py` rewrite + `test_tool_registry.py` rewrite. `tools/__init__.py` updated in this step (no MCP exports yet).
4. `tools/mcp/adapter.py` + `test_mcp_adapter.py`. Adds `fastmcp` to `pyproject.toml` because the adapter test imports FastMCP's in-process client.
5. `tools/mcp/server.py` + `test_mcp_server_build.py`. Adds `"agents.tools.mcp"` to the packages list.
6. `tools/mcp/runner.py` (no tests of its own beyond what server/command tests cover).
7. `management/commands/run_tools_mcp.py` + `list_toolsets.py` + `test_management_commands.py`.
8. `test_boot_gate.py`.
9. Final full-suite run + manual verification (§14).

No step is allowed to leave the tree red. If a downstream step reveals a missed decision in this LLD, update the LLD and re-baseline before continuing — the LLD stays the source of truth, not the half-merged code.

---

### 16. Risks and mitigations

| Risk | Mitigation |
|---|---|
| `fastmcp` API drift between minor versions. | Pin `fastmcp>=2,<3`; if a 2.x breaking change ships, bump in lockstep with `freedom-plane-agent`. |
| FastMCP swallows exception attributes (`provider_status` etc.) when converting to MCP errors. | `test_mcp_adapter.py` asserts propagation through FastMCP's in-process client. If FastMCP strips them, the adapter takes responsibility for re-encoding into the MCP error payload — but that decision is deferred and only revisited if the test fails. |
| `register_toolset` instantiates `toolset_cls()` eagerly in `AppConfig.ready()`. A toolset that reads env vars at `__init__` will fail Django startup in test runs. | Test fixtures (`EchoToolSet` etc.) have env-free `__init__`. Production toolsets that need env vars accept the contract: missing env = Django startup fails loudly, by design (HLD §8). |
| `_toolsets.py` test-helper file accidentally collected by pytest. | File is named with leading underscore; `pytest.ini`'s `python_files = test_*.py` already excludes it. |
| Coverage drop from runner.py being mostly mocked. | Documented in §12; not a blocker. |

---

### 17. Out-of-scope guardrails

If during implementation any of the following come up, **stop and surface them** rather than expanding scope:

- Migrating `PlaneToolset` — separate ticket (parent HLD §11).
- Cross-module toolsets / cross-app tool composition — parent HLD §14.1.
- Auto-inferring `input_model`/`output_model` from method hints — parent HLD §14.4.
- Multi-toolset-per-process supervisor or port allocation — explicitly rejected (parent HLD §12).
- `mcp_safe`-only subset exposure within a partially-safe toolset — explicitly rejected (HLD §6 invariant is "expose_mcp=True requires every member mcp_safe=True").
