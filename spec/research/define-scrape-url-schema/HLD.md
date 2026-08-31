# HLD: Define ScrapeUrlInput / ScrapeUrlOutput

**Plane ticket:** #390
**Module:** research-agent (freedom-agents)
**Work item:** Define `ScrapeUrlInput`, `ScrapeUrlOutput` in `schema.py`
**State:** Todo → HLD
**Date:** 2026-05-20
**Parent HLD:** `DjangoAgent/research-agent/spec/research-agent/typed-search-and-scrape-tool-module/HLD.md` (§6)

---

## 1. Purpose

Ship the typed input/output Pydantic schemas for the `scrape_url` tool so downstream stories (Firecrawl adapter, registry wiring, MCP exposure, pipeline integration) have a stable contract to import. This story delivers schemas only — no provider implementation, no registry registration, no execution.

**Deviation from parent HLD §6:** the parent defines two output models, `ScrapedPage` and `ScrapeUrlOutput(page: ScrapedPage)`. We collapse to a single `ScrapeUrlOutput` with the page fields inline. The wrapper added no behavior in v1 (single-page fetch, no sibling fields) and only forced callers to write `output.page.markdown` instead of `output.markdown`. If sibling fields ever land (e.g., `warnings`, multi-page), the inline fields can be promoted into a nested model at that point.

## 2. Scope

| In scope | Out of scope |
|---|---|
| `ScrapeUrlInput`, `ScrapeUrlOutput` Pydantic v2 models in `research_agent/tools/scrape_url/schema.py` | `FirecrawlScrapeTool` or any provider adapter |
| `formats` literal set: `markdown`, `text`, `html`, `links` (aligned enhancement over parent HLD §6.1, which omits `links`) | Tool runtime, registry registration, MCP server wiring |
| Package marker file `research_agent/tools/scrape_url/__init__.py` re-exporting both models | Caching, retries, multi-page crawl shape |
| Round-trip-friendly defaults via `Field(default_factory=...)` for mutable fields | Separate `ScrapedPage` wrapper model (collapsed — see §1) |

## 3. File Layout

```
research_agent/
  tools/
    scrape_url/
      __init__.py        # re-exports the three models
      schema.py          # this story
```

`research_agent/__init__.py` and `research_agent/tools/__init__.py` are created as empty package markers if they don't already exist.

## 4. Model Contracts

Adapted from parent HLD §6, with two changes: (a) `formats` accepts `"links"` in addition to `markdown | text | html` — symmetric with Firecrawl's `/v1/scrape` capability used in parent §6.3; (b) the `ScrapedPage` wrapper is collapsed into `ScrapeUrlOutput` (see §1).

```python
from typing import Any, Literal
from pydantic import BaseModel, Field, HttpUrl


class ScrapeUrlInput(BaseModel):
    url: HttpUrl
    formats: list[Literal["markdown", "text", "html", "links"]] = Field(
        default_factory=lambda: ["markdown"]
    )


class ScrapeUrlOutput(BaseModel):
    url: HttpUrl                       # final URL after redirects
    title: str | None = None
    markdown: str | None = None
    text: str | None = None
    html: str | None = None
    status_code: int
    provider: str
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
```

Notes:
- `HttpUrl` is used both on input and output; output `url` reflects the final URL after redirects (set by the adapter, not validated against the input).
- All textual format fields are `str | None` so an adapter populates only the formats requested.
- `provider_metadata` is the documented escape hatch (parent HLD §6.2) — opaque, provider-specific (e.g., Firecrawl `og`, `links`, `language`).
- `default_factory` is used instead of mutable literal defaults to avoid the shared-default pitfall.

## 5. `__init__.py`

```python
from .schema import ScrapeUrlInput, ScrapeUrlOutput

__all__ = ["ScrapeUrlInput", "ScrapeUrlOutput"]
```

Imports stabilize the public surface so downstream stories use `from research_agent.tools.scrape_url import ScrapeUrlInput` and not the schema module path.

## 6. Validation Behavior (inherited from Pydantic v2)

| Input case | Behavior |
|---|---|
| `url` not a valid URL | `ValidationError` |
| `formats` contains a value outside the Literal | `ValidationError` |
| `formats` omitted | defaults to `["markdown"]` |
| `ScrapeUrlOutput.status_code` missing or non-int | `ValidationError` |
| `provider_metadata` omitted | defaults to `{}` |

No custom validators in this story; loud failure on bad input is sufficient (parent HLD §9, "v1: fail loudly").

## 7. Testing

Unit tests (added next to the module, e.g., `tests/unit/test_scrape_url_schema.py`) cover:
- Default `formats` is `["markdown"]` and is a fresh list per instance.
- All four literal values accepted; unknown values rejected.
- `ScrapeUrlOutput` builds with only required fields (`url`, `status_code`, `provider`).
- `ScrapeUrlOutput.model_validate({...})` round-trips.
- `provider_metadata` accepts arbitrary JSON-compatible dicts.

Test file is in scope as a sibling deliverable but not blocking the schema ship — the model definitions are the contract.

## 8. Dependencies

- `pydantic >= 2` (already a transitive dep of the agents framework).
- No runtime imports of Firecrawl, HTTPX, or the registry — schema module stays import-cheap and side-effect-free.

## 9. Out of Scope

- Firecrawl adapter (separate work item).
- Registry registration / MCP exposure (separate work items).
- Renaming or restructuring `research_agent/` beyond creating the `tools/scrape_url/` package.
- Backwards-compatibility shims (no prior implementation).

## 10. Acceptance Criteria

1. `research_agent/tools/scrape_url/schema.py` exists and defines exactly the two models with the field shapes in §4.
2. `formats` Literal includes `markdown`, `text`, `html`, `links`.
3. `research_agent/tools/scrape_url/__init__.py` re-exports both models.
4. `python -c "from research_agent.tools.scrape_url import ScrapeUrlInput, ScrapeUrlOutput"` succeeds with no side effects.
