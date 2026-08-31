# HLD: Implement FirecrawlScrapeToolSet

**Plane ticket:** #391
**Module:** research-agent (freedom-agents)
**Work item:** Implement `FirecrawlScrapeTool.run()` in `firecrawl.py`
**State:** Todo → HLD
**Date:** 2026-05-20
**Parent HLD:** `DjangoAgent/research-agent/spec/research-agent/typed-search-and-scrape-tool-module/HLD.md` (§6.3)
**Sibling stories:** #380 (ToolSet/registry framework, shipped), #390 (ScrapeUrl schema, shipped), #392 (registry self-registration, separate)

---

## 1. Purpose

Ship the Firecrawl-backed implementation of the `scrape_url` tool as a `ToolSet` subclass. Given a URL and a list of requested formats, call Firecrawl's `/v1/scrape` HTTP API, map the response into the shipped `ScrapeUrlOutput`, and surface any failure as `ToolExecutionError`.

**Naming note.** The ticket title says `FirecrawlScrapeTool.run()` (parent HLD's earlier per-tool `Tool` Protocol). The framework that actually landed in #380 uses `ToolSet` + `@tool`. This story implements the `ToolSet` shape; no `run()` method is created.

## 2. Scope

| In scope | Out of scope |
|---|---|
| `research_agent/tools/scrape_url/firecrawl.py` with `FirecrawlScrapeToolSet(ToolSet)` | `ScrapedPage` model (already collapsed in #390) |
| Env-driven config read in `__init__`, raising `ToolExecutionError("config: <var> missing")` per missing var | Self-registration into `default_registry` (#392) |
| Single `@tool`-decorated method `scrape_url` calling Firecrawl `/v1/scrape` synchronously via `httpx.Client` | Caching, retries, async client, multi-page crawl |
| Response → `ScrapeUrlOutput` mapping per §5 | Unit/integration tests (out per refinement; may follow in sibling) |
| Loud failure with no silent coercion: non-2xx, transport error, malformed body, missing required keys → `ToolExecutionError` | Provider abstraction beyond Firecrawl |

## 3. File Layout

```
research_agent/
  tools/
    scrape_url/
      __init__.py    # existing; do NOT re-export firecrawl module here (avoid registry side effects)
      schema.py      # shipped in #390
      firecrawl.py   # this story
```

No `__init__.py` re-export of the new module — keeps `research_agent.tools.scrape_url` import-cheap and side-effect-free until #392 wires the registry.

## 4. Class Shape

```python
import os
from typing import Any

import httpx
from pydantic import HttpUrl

from agents.core.tools import ToolSet, ToolExecutionError, tool
from research_agent.tools.scrape_url.schema import ScrapeUrlInput, ScrapeUrlOutput


class FirecrawlScrapeToolSet(ToolSet):
    name = "scrape_url"

    def __init__(self) -> None:
        super().__init__()
        url = os.environ.get("FIRECRAWL_URL", "").strip()
        key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
        if not url:
            raise ToolExecutionError("config: FIRECRAWL_URL missing", tool_name="scrape_url")
        if not key:
            raise ToolExecutionError("config: FIRECRAWL_API_KEY missing", tool_name="scrape_url")
        self._base_url = url.rstrip("/")
        self._api_key = key

    @tool(input_model=ScrapeUrlInput, output_model=ScrapeUrlOutput, mcp_safe=True)
    def scrape_url(self, input: ScrapeUrlInput) -> ScrapeUrlOutput:
        ...
```

The decorator returns the function unchanged; calling `scrape_url(input)` in-process invokes the body directly. Registry discovery is via the `__agent_tool__` marker, which #392 will wire up.

## 5. Request / Response Mapping

### Request

- Method: `POST`
- URL: `f"{self._base_url}/v1/scrape"`
- Headers:
  - `Authorization: Bearer {self._api_key}`
  - `Content-Type: application/json`
- Body: `{"url": str(input.url), "formats": list(input.formats)}` — pass `formats` through verbatim. Schema's `Literal` already constrains the set.
- Transport: `httpx.Client(timeout=30.0)` instantiated per call (`with httpx.Client(...) as client:`). No shared client in v1 — simplifies thread-safety and avoids needing teardown hooks on `ToolSet`.

### Response → `ScrapeUrlOutput`

Firecrawl response shape (relevant subset):
```json
{
  "success": true,
  "data": {
    "markdown": "...",
    "text": "...",
    "html": "...",
    "links": ["..."],
    "metadata": {
      "url": "https://final.example/path",
      "title": "Page Title",
      "statusCode": 200,
      "language": "en",
      "og:title": "...",
      "twitter:card": "summary"
    }
  }
}
```

Mapping table:

| `ScrapeUrlOutput` field | Source |
|---|---|
| `url` | `data.metadata.url` (final URL after redirects) |
| `title` | `data.metadata.title` (may be `None`) |
| `markdown` | `data.markdown` if `"markdown" in input.formats` else `None` |
| `text` | `data.text` if `"text" in input.formats` else `None` |
| `html` | `data.html` if `"html" in input.formats` else `None` |
| `status_code` | `data.metadata.statusCode` |
| `provider` | hard-coded `"firecrawl"` |
| `provider_metadata` | `{"og": <see below>, "links": data.get("links", []), "language": data.metadata.get("language")}` |

### `provider_metadata.og`

Flat dict copying every `data.metadata` key whose name starts with `og:` or `twitter:`, prefixes preserved:

```python
og = {
    k: v
    for k, v in data["metadata"].items()
    if k.startswith(("og:", "twitter:"))
}
```

- Keys kept verbatim (e.g. `"og:title"`, `"twitter:card"`).
- Always populated; empty dict `{}` when no such keys exist.
- Fields already lifted into other `ScrapeUrlOutput` columns (`url`, `title`, `statusCode`, `language`) are not duplicated into `og`.
- Despite the name `og`, twitter card metadata is included (name retained from parent HLD).

## 6. Failure Modes

All failures raise `ToolExecutionError` with `tool_name="scrape_url"` and `input_snapshot={"url": str(input.url), "formats": list(input.formats)}`.

| Condition | Extras on `ToolExecutionError` |
|---|---|
| Non-2xx HTTP response | `provider_status=response.status_code`, `provider_body=response.text[:N]` (truncated, see §7) |
| Transport error (`httpx.RequestError` — timeout, connect refused, DNS) | message includes underlying exception class |
| Response body is not JSON / not an object | message names the violation |
| `success: false` in body | `provider_body` carries the body |
| Missing required keys: `data`, `data.metadata`, `data.metadata.url`, `data.metadata.statusCode` | message names the missing path |
| `ValidationError` from `ScrapeUrlOutput(...)` | **not caught** — propagates as a programming/contract error |

No silent coercion: e.g. if `statusCode` is a string, do not `int()`-cast — let `ScrapeUrlOutput` validation fail loudly.

## 7. Operational Notes

- `provider_body` is truncated to a reasonable cap (e.g. 2 KB) to avoid stuffing megabytes of HTML into an exception when Firecrawl returns an error page. Hard-coded constant in module — no config knob.
- Logging: none in this story (no logger configured yet at module level); failures travel via exception.
- Imports are side-effect-free. No registry mutation at import time. `httpx` and `os` only — no Django coupling.
- `FirecrawlScrapeToolSet()` may raise during construction (missing env). Callers (registry, tests) must be prepared to handle that, exactly as #380's contract expects.

## 8. Dependencies

- `httpx` (already a transitive dep).
- `pydantic >= 2` (transitive).
- `agents.core.tools` for `ToolSet`, `@tool`, `ToolExecutionError` (from #380).
- `research_agent.tools.scrape_url.schema` for `ScrapeUrlInput`, `ScrapeUrlOutput` (from #390).

## 9. Out of Scope

- Registry registration / MCP exposure (#392).
- Async variant of `scrape_url`.
- Retries, backoff, circuit-breaking.
- Shared `httpx.Client` lifecycle.
- Tests (per refinement note in the ticket — sibling story may follow).

## 10. Acceptance Criteria

1. `research_agent/tools/scrape_url/firecrawl.py` exists and defines `FirecrawlScrapeToolSet(ToolSet)` with class attribute `name = "scrape_url"`.
2. `__init__` reads `FIRECRAWL_URL` and `FIRECRAWL_API_KEY` from `os.environ` and raises `ToolExecutionError("config: FIRECRAWL_URL missing")` or `ToolExecutionError("config: FIRECRAWL_API_KEY missing")` respectively when absent or empty.
3. A single `@tool(input_model=ScrapeUrlInput, output_model=ScrapeUrlOutput, mcp_safe=True)` method `scrape_url` issues `POST {FIRECRAWL_URL}/v1/scrape` via `httpx.Client` with the bearer header and body shape in §5.
4. Successful response maps to `ScrapeUrlOutput` exactly per the table and `og` rule in §5.
5. Non-2xx, transport error, malformed/non-object body, `success: false`, or missing required keys raise `ToolExecutionError` (with `tool_name` and `input_snapshot` set; `provider_status` / `provider_body` set on HTTP errors). No silent coercion.
6. No registry side effects on import; `research_agent/tools/scrape_url/__init__.py` is unchanged.
