# HLD: Toolset-to-MCP Exposure Layer

**Plane:** #396 (parent); downstream: #380, #384, #385, #386, #388, #389, #391, #392, #397–#399
**Module:** freedom-agents — meml-side machinery only.
**State:** Draft · 2026-05-14

Supersedes the MCP portion of `research-agent/.../typed-search-and-scrape-tool-module/HLD.md` §11.

---

## 1. Model

`ToolSet` is a **base class**. Concrete toolsets subclass it; tools live as `@tool`-decorated methods on the subclass. One subclass = one toolset = (optionally) one MCP server.

| Primitive | Status | Owner |
|---|---|---|
| **`ToolSet`** — base class; subclasses define tools as methods | **new** | `agents.tools.toolset` |
| **`@tool`** — decorator that marks a method as a tool and supplies its metadata | **new** | `agents.tools.toolset` |
| **`Tool`** — runtime descriptor returned by `@tool` (name, input_model, output_model, mcp_safe, bound_method) | **new** | `agents.tools.contracts` |
| `ToolRegistry` + module-level `default_registry` | extend | `agents.tools.registry` |
| `ToolExecutionError` | unchanged | `agents.tools.contracts` |

Pattern matches `freedom-plane-agent`'s existing `PlaneToolset` shape; that becomes prior art for the migration in §11.

---

## 2. Shape

```python
from agents.core.tools import ToolSet, tool, ToolExecutionError

class WebResearchToolSet(ToolSet):
    name = "web_research"          # globally unique toolset key

    def __init__(self):
        # config-time setup. Raise ToolExecutionError("config: ...") on missing env.
        self.searxng_url = os.environ.get("SEARXNG_URL") or _raise("SEARXNG_URL")
        self.firecrawl_url = os.environ.get("FIRECRAWL_URL") or _raise("FIRECRAWL_URL")
        self.firecrawl_key = os.environ.get("FIRECRAWL_API_KEY") or _raise("FIRECRAWL_API_KEY")

    @tool(input_model=SearchWebInput, output_model=SearchWebOutput, mcp_safe=True)
    def search_web(self, input: SearchWebInput) -> SearchWebOutput:
        ...

    @tool(input_model=ScrapeUrlInput, output_model=ScrapeUrlOutput, mcp_safe=True)
    def scrape_url(self, input: ScrapeUrlInput) -> ScrapeUrlOutput:
        ...
```

- `name` (class attribute): globally unique toolset key.
- `@tool(input_model=…, output_model=…, mcp_safe=False, name=None)`: marks a method. Tool name defaults to the method name; can be overridden.
- `__init__`: state and credentials. Raises loud on misconfig.
- `mcp_safe` is **per tool**; default `False`. Tool author's call: "is this tool safe to expose via MCP at all."

---

## 3. Registry surface

```python
class ToolRegistry:
    # toolset registration — only entry point for putting tools in the registry
    def register_toolset(
        self,
        toolset_cls: type[ToolSet],
        *,
        module: str,
        expose_mcp: bool = False,        # NEW — does this toolset get an MCP server?
    ) -> None: ...

    def get_toolset(self, name) -> type[ToolSet]: ...
    def toolset_names(self, *, modules=None) -> list[str]: ...
    def resolve_toolset(self, name) -> list[Tool]: ...

    # individual-tool surface (derived; for in-process pipeline calls)
    def get(self, name) -> Tool: ...
    def run(self, name, input): ...
    def names(self, *, modules=None) -> list[str]: ...
```

`register_toolset` does the work:

1. Instantiates `toolset_cls()` (config-time errors surface here).
2. Walks methods, collects `@tool`-decorated ones, builds `Tool` descriptors bound to the instance.
3. Records the toolset under `cls.name`, with `module` + `expose_mcp` metadata.
4. Records each member tool under its `name` for flat lookup by pipelines.
5. **If `expose_mcp=True`**: validates every member tool has `mcp_safe=True`. Raises loudly if not.
6. Raises on duplicate toolset names or duplicate tool names across toolsets.

There is no standalone `register(tool)` — tools live inside toolsets only. The MCP-server-spawn boilerplate (adapter generation, FastMCP wiring, transport bootstrap) lives in `agents.tools.mcp` and is invoked via the management command; host apps never write that code.

---

## 4. Registration lifecycle

Each host app declares its toolsets in `AppConfig.ready()`. No bare-module import side effects.

```python
# research_agent/apps.py
class ResearchAgentConfig(AppConfig):
    name = "research_agent"

    def ready(self):
        from agents.core.tools import default_registry
        from research_agent.toolsets import WebResearchToolSet

        default_registry.register_toolset(
            WebResearchToolSet,
            module=self.label,
            expose_mcp=True,            # tells freedom-agents this toolset is MCP-exposable
        )
```

`INSTALLED_APPS` is the opt-in. A toolset registered with `expose_mcp=False` (the default) is invisible to MCP — it's strictly for in-process pipeline use.

---

## 5. Invocation

Single Django management command in `freedom-agents`:

```bash
python manage.py run_tools_mcp --toolset NAME \
    [--transport stdio|http|sse] [--host H] [--port P] [--name SERVER]
```

| Flag | Default |
|---|---|
| `--toolset` | required |
| `--transport` | `stdio` (canonical for pi-agent subprocess) |
| `--host` | `127.0.0.1` (HTTP/SSE only) |
| `--port` | unset (HTTP/SSE only) |
| `--name` | toolset name |

Refuses to start unless the named toolset was registered with `expose_mcp=True`. Plus a `list_toolsets [--module M] [--exposed-only]` introspection command.

Flow: Django boots → `ready()` populates registry → command looks up toolset → checks `expose_mcp` → builds FastMCP via §7 → runs.

---

## 6. Two-tier MCP gating

Two opt-in flags, both required for a tool to reach an MCP client:

| Layer | Flag | Default | Author |
|---|---|---|---|
| Tool | `mcp_safe` (on `@tool` decorator) | `False` | Tool author — "is this tool safe to expose via MCP at all?" |
| Toolset | `expose_mcp` (on `register_toolset`) | `False` | Host app — "should this toolset have an MCP server?" |

Rules (enforced at registration, fail-loud):

- `expose_mcp=True` + any member tool with `mcp_safe=False` → `register_toolset` raises.
- `expose_mcp=False` → the `run_tools_mcp` command refuses to serve that toolset.

A tool with `mcp_safe=False` can still live in `default_registry` for pipeline use — it just can never reach an MCP client. Example: `fetch_bookmarks` (uses OAuth tokens; pipeline-only).

---

## 7. Adapter generation

Dynamic per tool — Pydantic input model **is** the MCP parameter schema. No handwritten lists. Lives in `agents.tools.mcp.adapter`.

```python
def build_tool_adapter(tool: Tool):
    params = [
        inspect.Parameter(n, KEYWORD_ONLY,
                          default=(f.default if f.default is not PydanticUndefined else inspect.Parameter.empty),
                          annotation=f.annotation)
        for n, f in tool.input_model.model_fields.items()
    ]
    def adapter(**kwargs):
        input_obj = tool.input_model(**kwargs)
        output = tool.bound_method(input_obj)
        return output.model_dump(mode="json")
    adapter.__name__ = tool.name
    adapter.__signature__ = inspect.Signature(params, return_annotation=dict)
    return adapter

# in server build:
for t in registry.resolve_toolset(toolset_name):
    mcp.tool(build_tool_adapter(t), name=t.name)
```

Pattern mirrors `freedom-plane-agent/mcp/tools_adapter.py._wrap_plane_tool`, driven by `Tool` descriptors instead of bound method introspection.

---

## 8. Error mapping

| Source | Behaviour |
|---|---|
| `ToolExecutionError` from `bound_method` | Propagates → MCP tool-call error. Server stays up. |
| `ValidationError` from `input_model(**kwargs)` | Same. |
| Config error in toolset `__init__` (e.g. missing env var) | Django boot fails. Command never starts. |
| Toolset missing / `expose_mcp=False` / non-`mcp_safe` member | `SystemExit` before server starts. |

Error payload to client carries `ToolExecutionError.args[0]` plus `tool_name`, `provider_status`, `provider_body` when set.

---

## 9. Code layout

```
freedom-agents/tools/
  contracts.py       # Tool descriptor; ToolExecutionError
  toolset.py         # ToolSet base class; @tool decorator
  registry.py        # ToolRegistry; default_registry
  mcp/
    adapter.py       # build_tool_adapter
    server.py        # build_mcp_server(name, registry, toolset_name) -> FastMCP
    runner.py        # transport bootstrap; called by management command

freedom-agents/management/commands/
  run_tools_mcp.py
  list_toolsets.py
```

All MCP boilerplate lives here. Host apps add zero MCP-specific code — they only subclass `ToolSet` and call `register_toolset`. `fastmcp` added to `freedom-agents` runtime deps.

---

## 10. Pi boundary

Out of scope here. meml-side surface that pi consumes:

- Each `expose_mcp=True` toolset reachable via `python manage.py run_tools_mcp --toolset <NAME> --transport stdio`.
- Pi-agent spawns N subprocesses, one per attached toolset.
- Standard MCP STDIO. No meml-specific wire protocol.

How pi declares per-agent toolset attachments belongs to a pi-side spec.

---

## 11. Plane-agent migration (sketch — not in scope to implement)

The current `PlaneToolset` is already toolset-shaped; migration is mechanical:

1. `class PlaneToolset(ToolSet)`, add `name = "plane_write_safe"` (or split into read/write toolsets).
2. Replace the `*_tool` method-naming convention with explicit `@tool(input_model=…, output_model=…, mcp_safe=True)` decoration. Each method's body stays the same.
3. `plane_agent/apps.py:ready()` calls `default_registry.register_toolset(PlaneToolset, module=self.label, expose_mcp=True)`.
4. Delete `plane_agent/mcp/server.py`, `tools_adapter.py`, `main.py`.
5. `start_services.sh mcp` target switches to `run_tools_mcp --toolset plane_write_safe …`.

Confirms the layer supports plane's eventual collapse. No bespoke per-app MCP code left.

---

## 12. Out of scope (v1)

- Pi-side TS declaration shape.
- Cross-module toolsets (toolset referencing tools owned by a different `AppConfig`).
- Settings-based toolset declaration (in `MeML/settings.py`). Code-defined only.
- Auth, streaming, async tools, retries, budget accounting.
- Multi-toolset-per-server, multi-server-per-process.
- Tag-based filtering (replaced by `mcp_safe` + `expose_mcp` + module ownership).
- Implementing plane-agent migration (sketched only).

---

## 13. Downstream ticket consequences

| Ticket | Action |
|---|---|
| #380 | Replace standalone-tool model with `ToolSet` base class + `@tool` decorator + `Tool` descriptor. Registry methods: `register_toolset(cls, *, module, expose_mcp=False)`, `get_toolset`, `toolset_names`, `resolve_toolset`. Keep `get`/`run`/`names` flat-by-name for pipeline use. Drop `tags`, `register(tool)`. |
| #384 | Reshape: `Tool` becomes runtime descriptor returned by `@tool`. `ToolExecutionError` unchanged. Add `ToolSet`/`@tool` to the contracts surface. |
| #385 | Reshape: registry stores toolsets; tools registered only via toolsets. Validation of `expose_mcp` vs `mcp_safe` at register time. |
| #386 | Re-exports: `ToolSet`, `tool`, `Tool`, `ToolRegistry`, `ToolExecutionError`, `default_registry`. |
| #387, #390 | Input/output schemas unchanged. |
| #388 | Move `SearxngSearchTool.run()` body into a `@tool(...)`-decorated method on `WebResearchToolSet`. |
| #389 | **Replace**: register `WebResearchToolSet` in `research_agent/apps.py:ready()` with `expose_mcp=True`. Delete the `__init__.py` self-registration. |
| #391 | Move `FirecrawlScrapeTool.run()` body into a `@tool(...)`-decorated method on `WebResearchToolSet` (same toolset as search). |
| #392 | **Dissolved**: no separate registration; covered by #389. |
| #396 | Retitle: "Build toolset-to-MCP exposure layer in freedom-agents." Scope = `ToolSet`/`@tool`/`Tool`, registry, `run_tools_mcp` + `list_toolsets`, dynamic adapter, fastmcp dep, `expose_mcp` gating. Earlier appended refinement is superseded. |
| #397 | Replace with "Implement `run_tools_mcp` + runner inside `agents.tools.mcp`." |
| #398, #399 | Dissolve. Generic adapter exposes whatever the toolset's `@tool` methods declare. Replaced by a single new "Declare `WebResearchToolSet` in research-agent" ticket. |

**New tickets:**

- freedom-agents: `ToolSet` base + `@tool` decorator + `Tool` descriptor.
- freedom-agents: registry rewrite — toolset-centric + `expose_mcp` validation.
- freedom-agents: `agents.tools.mcp` package + `run_tools_mcp` management command.
- research-agent: `WebResearchToolSet` (search + scrape methods). Wire `ResearchAgentConfig.ready()` with `expose_mcp=True`.

---

## 14. Open

1. Cross-module toolset declaration shape (v2). Likely a `TOOLSETS` setting merged post-`ready()`.
2. STDIO subprocess crash handling — pi-side concern.
3. Startup log to stderr listing the resolved tool set — recommend yes (stdout is the MCP transport).
4. Whether `@tool` should auto-infer `input_model` / `output_model` from method type hints. Default: explicit; revisit if it becomes friction.
