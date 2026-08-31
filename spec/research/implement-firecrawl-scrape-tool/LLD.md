# LLD: Implement FirecrawlScrapeToolSet

**Plane ticket:** #391
**Module:** research-agent (freedom-agents)
**Parent HLD:** `./HLD.md`
**State:** HLD → LLD
**Date:** 2026-05-20

This LLD turns the HLD into ordered, decision-complete implementation steps. No code is included; the HLD §4–§7 already pin the shapes.

---

## 0. Pre-flight checks

1. Confirm `agents.core.tools` exposes `ToolSet`, `tool`, and `ToolExecutionError` (the #380 surface). If absent, surface the gap to the user before proceeding — this story cannot land first.
2. Confirm `research_agent/tools/scrape_url/schema.py` exists with `ScrapeUrlInput` and `ScrapeUrlOutput` matching the HLD field list (#390). If absent, surface the gap — schema is a hard prerequisite.
3. Confirm `httpx` resolves from the active interpreter inside `DjangoAgent/research-agent`. No new entry in `pyproject.toml` is expected (HLD §8 calls it a transitive dep); verify before writing import.
4. Confirm `research_agent/tools/scrape_url/__init__.py` will exist (created by #390); this story must not modify it (HLD §3, AC §10.6).

If any pre-flight item fails, halt and report — do not paper over with placeholders.

## 1. Module skeleton

- Create file `research_agent/tools/scrape_url/firecrawl.py`.
- Top-of-file imports, in this order: stdlib (`os`, typing helpers), third-party (`httpx`, `pydantic` symbols only if needed for type hints), first-party (`agents.core.tools` symbols, then `research_agent.tools.scrape_url.schema` symbols).
- Define one module-level constant for the `provider_body` truncation cap (HLD §7). Value: 2048 bytes. Name: `_PROVIDER_BODY_MAX_BYTES`. Single source of truth — referenced from the error-construction helper in §5.
- No module-level logger, no module-level HTTP client, no registry mutation, no decorators applied at import time other than `@tool` on the method.

## 2. Class declaration

- Class name: `FirecrawlScrapeToolSet`, single base `ToolSet`.
- Class attribute `name = "scrape_url"` (HLD §4 — used by registry in #392; sets `ToolExecutionError.tool_name` default for callers).
- No other class attributes. No docstring beyond a single line naming the provider.

## 3. `__init__`

- Signature: `def __init__(self) -> None`.
- Body order:
  1. Call `super().__init__()`.
  2. Read `FIRECRAWL_URL` from `os.environ`, default `""`; strip whitespace.
  3. Read `FIRECRAWL_API_KEY` from `os.environ`, default `""`; strip whitespace.
  4. If URL is empty → raise `ToolExecutionError("config: FIRECRAWL_URL missing", tool_name="scrape_url")`. Message string is exact (AC §10.2).
  5. If key is empty → raise `ToolExecutionError("config: FIRECRAWL_API_KEY missing", tool_name="scrape_url")`. Exact message.
  6. Persist `self._base_url = url.rstrip("/")` (so concat with `/v1/scrape` is well-formed regardless of trailing slash in env).
  7. Persist `self._api_key = key`.
- No additional validation (e.g. URL scheme parsing). Loud-fail responsibility lies with the HTTP call.
- No `input_snapshot` on the config error because no input has been received at construction time.

## 4. The `scrape_url` method

- Decorate with `@tool(input_model=ScrapeUrlInput, output_model=ScrapeUrlOutput, mcp_safe=True)`. Exactly these three kwargs; no `name=` override (defaults to the function name, which matches the `ToolSet.name`).
- Signature: `def scrape_url(self, input: ScrapeUrlInput) -> ScrapeUrlOutput`.
- Param name is `input` (matches HLD §4). Accept the linter warning rather than rename — keeps consistency with the search_web sibling and the `@tool` contract.
- Body broken into four explicit phases (functions/inline blocks — implementer's call, but the boundaries are fixed):
  1. **Build request artifacts** — URL string, headers dict, JSON body dict per HLD §5 Request. `formats` is materialised as a fresh `list(input.formats)` (no aliasing of the pydantic field).
  2. **Issue HTTP call** — `with httpx.Client(timeout=30.0) as client:` then `client.post(...)`. Wrap only the `client.post` call in a `try/except httpx.RequestError`. Do not catch broader `Exception`.
  3. **Validate response envelope** — status check, JSON parse, `success` flag, key presence (§5 below).
  4. **Map to `ScrapeUrlOutput`** — construct the pydantic model from a dict assembled in one place. Let `ValidationError` propagate (HLD §6 last row).
- Method must return the constructed `ScrapeUrlOutput`. No other return paths.

## 5. Response validation order

Failures raise `ToolExecutionError`. Order matters — earlier checks short-circuit later assumptions.

1. **HTTP status**: if `response.status_code` not in 200..299 inclusive → raise with message naming the status. Populate `provider_status=response.status_code` and `provider_body=response.text[:_PROVIDER_BODY_MAX_BYTES]`.
2. **JSON parse**: call `response.json()`. On `ValueError`/`json.JSONDecodeError` → raise with message "response body is not JSON"; include truncated `provider_body`.
3. **Top-level shape**: if parsed payload is not a `dict` → raise "response body is not a JSON object".
4. **`success` flag**: if `payload.get("success") is False` (explicit `False`, not just falsy) → raise "provider reported success=false", include `provider_body`.
5. **Required keys** — checked in this exact order; each missing key raises with the missing dotted path in the message:
   1. `data` present and is a dict.
   2. `data.metadata` present and is a dict.
   3. `data.metadata.url` present and non-empty string.
   4. `data.metadata.statusCode` present (type-check deferred to pydantic — no `int()` cast).

Every raised `ToolExecutionError` in this method carries `tool_name="scrape_url"` and `input_snapshot={"url": str(input.url), "formats": list(input.formats)}`. Centralize construction in a small private helper inside the module (e.g. `_raise_exec_error(...)`) to keep call sites short — the helper is *not* exported and has no class binding.

## 6. Mapping to `ScrapeUrlOutput`

Construct the output kwargs dict in one place, in this order, so the final pydantic constructor reads top-to-bottom against the HLD §5 table:

1. `url` ← `metadata["url"]`.
2. `title` ← `metadata.get("title")` (may be `None`).
3. `markdown` ← `data["markdown"]` if `"markdown" in input.formats` else `None`. Use direct key access (not `.get`) when format requested — a missing key when requested is a contract violation; raise `ToolExecutionError("missing data.markdown for requested format")`. Same rule for `text` and `html`.
4. `text` ← analogous.
5. `html` ← analogous.
6. `status_code` ← `metadata["statusCode"]`.
7. `provider` ← literal `"firecrawl"`.
8. `provider_metadata` ← dict with three fixed keys, in order: `og`, `links`, `language`.
   - `og` ← dict comprehension over `metadata.items()` keeping keys starting with `"og:"` or `"twitter:"` (HLD §5 `og` rule, refinement-confirmed). Always present, possibly `{}`.
   - `links` ← `data.get("links", [])`. Pass through unchanged; do not validate element types.
   - `language` ← `metadata.get("language")`. May be `None`.

Final step: `return ScrapeUrlOutput(**kwargs)`.

## 7. Error-construction helper

- Module-private function (or staticmethod — implementer's call, no functional difference). Inputs: message, optional `provider_status`, optional `provider_body`, and the `input` object (for snapshot).
- Truncation of `provider_body` lives inside this helper using `_PROVIDER_BODY_MAX_BYTES`. Callers pass the raw text; only the helper slices.
- Helper raises (does not return); annotate return type `NoReturn`.

## 8. Files touched

| File | Action |
|---|---|
| `research_agent/tools/scrape_url/firecrawl.py` | **create** — sole code deliverable |
| `research_agent/tools/scrape_url/__init__.py` | **untouched** — no re-export (AC §10.6, HLD §3) |
| `research_agent/tools/scrape_url/schema.py` | **untouched** — consumed only |
| `pyproject.toml` | **untouched** unless §0.3 finds `httpx` missing, in which case stop and ask |

No migrations, no settings changes, no admin, no URLconf.

## 9. Verification (manual, dev-machine)

Tests are out of scope (HLD §9). The implementer should still do a smoke import to catch syntax/typo issues:

1. `python -c "from research_agent.tools.scrape_url.firecrawl import FirecrawlScrapeToolSet"` — must succeed without env vars set (import alone has no side effects).
2. With env vars unset: instantiating `FirecrawlScrapeToolSet()` must raise `ToolExecutionError` whose message is exactly `config: FIRECRAWL_URL missing`.
3. With only `FIRECRAWL_URL` set: instantiating must raise `config: FIRECRAWL_API_KEY missing`.
4. With both set to dummy values: instantiation must succeed; no network is touched at construction.

No live Firecrawl call is required for this story. End-to-end behaviour is owned by #392 + the consuming meml app.

## 10. Definition of done (mirrors HLD §10, restated as a checklist)

- [ ] File exists at `research_agent/tools/scrape_url/firecrawl.py`.
- [ ] `FirecrawlScrapeToolSet(ToolSet)` declared with `name = "scrape_url"`.
- [ ] `__init__` raises the two exact-string config errors when env vars are absent/empty.
- [ ] `@tool(input_model=ScrapeUrlInput, output_model=ScrapeUrlOutput, mcp_safe=True)` decorates a single method `scrape_url(self, input)`.
- [ ] HTTP call is `POST {FIRECRAWL_URL}/v1/scrape` via `httpx.Client(timeout=30.0)` with the bearer header and JSON body shape in HLD §5.
- [ ] Response → `ScrapeUrlOutput` mapping matches HLD §5 (incl. the `og` rule and the "requested format missing → raise" rule in §6 above).
- [ ] All non-success paths raise `ToolExecutionError` with `tool_name` and `input_snapshot`; HTTP errors additionally carry `provider_status` and truncated `provider_body`.
- [ ] No registry mutation at import; `__init__.py` of the package unchanged.
- [ ] Manual smoke checks in §9 pass.

## 11. Open points deferred to follow-up tickets

- Registry self-registration (#392).
- Async client variant.
- Retry / backoff policy.
- Shared `httpx.Client` lifecycle.
- Unit tests against a recorded Firecrawl fixture.

None of these block this story.
