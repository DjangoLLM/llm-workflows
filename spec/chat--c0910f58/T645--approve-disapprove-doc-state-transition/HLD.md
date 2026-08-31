# HLD: Approve/Disapprove Design Docs to Advance Linked Plane Stories

**Ticket:** #645 · `654f7acf-e737-4d83-9ed2-237c384fd34c`  
**Module:** `freedom-chat` / `chat--c0910f58`  
**Implementation repo:** `/Users/karthik/merge_conflicts/coding/plane-tui`  
**Design directory:** `spec/chat--c0910f58/T645--approve-disapprove-doc-state-transition`  
**Phase:** HLD

---

## Problem

Generated design docs can already be edited and viewed inside `DocTab.tsx`, and
agents can advance Plane stories themselves through the existing workflow prompts.
There is no manual human approval gate that lets a reviewer approve a doc and move
the linked story across a configured Plane state edge, or disapprove a doc while
recording the decision for later rework automation.

The key risk is an unsafe transition: the same `LLD.html` can be used for both
`Backlog -> Todo` and `LLD -> In Progress`, and the agent may have already moved
the story by the time a human clicks Approve.

---

## Goals

- Add Approve and Disapprove controls to the design-doc viewer chrome.
- Resolve the approval edge from the doc HTML override when present, otherwise
  from a profile-level current-state-to-next-state map.
- Re-fetch the story before transitioning and only proceed when the live state
  still matches the resolved edge's expected current state.
- Resolve state names to live Plane state IDs and fail loudly when a configured
  state name is missing or renamed.
- Persist Disapprove decisions with an optional note field now, without changing
  Plane state.
- Keep the agent's existing self-advance path intact; manual Approve is an
  additional path, not a replacement.

---

## Non-Goals

- No automatic doc-agent rework loop on Disapprove in this ticket.
- No removal or weakening of the existing agent prompt instruction to update
  work-item state.
- No path parsing to infer the task; use `selectedTaskId` and the registry
  `DesignDocument.task_id`.
- No implementation in `freedom-agents`; all code changes land in `plane-tui`.

---

## Proposed Design

### 1. Profile State-Edge Map

Extend `Profile` with a configurable map of literal workflow state names:

| Current state | Next state |
|---|---|
| `Backlog` | `Todo` |
| `Todo` | `HLD` |
| `HLD` | `LLD` |
| `LLD` | `In Progress` |

The backend config model in `core/core/config.py`, frontend `Profile` type, and
`web/frontend/src/lib/defaultPrompts.ts` mirror all carry this default. Keys and
values are state names, not IDs, because Plane state IDs are project-specific and
must be resolved against the live project state list at click time.

### 2. Per-Doc HTML Edge Override

Doc generation stamps an optional state pair into the generated HTML, for example
as metadata or a `data-*` attribute on the document root. The parser returns:

- `current_state`: required when an override is present.
- `next_state`: required when an override is present.
- `source`: `html_override` or `profile_map`.

The stamp is advisory configuration that survives filesystem rescans; the live
story state remains authoritative.

### 3. Backend Approval Endpoint

Add document-decision endpoints under the document registry/API boundary, because
that layer already owns registered docs, task links, and safe filesystem access:

| Endpoint | Behavior |
|---|---|
| `POST /api/documents/{doc_id}/approve` | Resolve edge, guard live state, resolve next ID, update task state |
| `POST /api/documents/{doc_id}/disapprove` | Persist decision record only |

Approve receives `project_id`, `task_id`, optional `profile`, and optionally the
current UI task context for validation. The server loads the registered document,
confirms it belongs to the same task, parses the HTML override if present, falls
back to the profile map, re-fetches task details, resolves both state names from
the live project states, then calls the existing repository update path used by
`postTaskStatus` / `update_task_state`.

Outcomes are explicit:

| Outcome | Response |
|---|---|
| Transition applied | Success payload with previous and new state names |
| Already advanced/stale | Non-error no-op payload with a clear conflict message |
| Unknown current/next state name | Error with the missing name and expected source |
| Missing doc/task/profile | Error with a specific reason |
| Worktracker update failure | Error surfaced to the UI, not swallowed |

### 4. Disapprove Decision Record

Add a small persisted decision model alongside `DesignDocument`:

| Field | Purpose |
|---|---|
| `id` | Decision row ID |
| `doc_id` | Registered document ID |
| `task_id` | Owning story/work item |
| `decision` | `disapproved` initially; leaves room for later audit history |
| `state_at_decision` | Live story state name when clicked |
| `note` | Optional reviewer note/reason, nullable now for forward compatibility |
| `created_at` | Timestamp |

Disapprove does not patch Plane. It records enough context for a follow-up ticket
to surface notes or re-summon the doc agent without a schema migration.

### 5. Doc Viewer UX

`DocTab.tsx` keeps rendering the sandboxed iframe and adds a viewer-chrome button
bar near the existing "edit with agent" control. The bar is outside the iframe so
document scripts cannot trigger approval.

Display rules:

- Show Approve/Disapprove only for real task docs, not scratch docs.
- Show Approve only when an edge can resolve from the HTML override or profile
  map for the story's live/current state.
- Keep buttons disabled while an approve/disapprove request is in flight.
- After Approve success, refresh tasks/details so the sidebar and selected story
  show the new state.
- After no-op/conflict, show the clear message and refresh details so the UI
  reflects the agent-advanced state.
- After Disapprove, show a saved-decision message and leave Plane untouched.

---

## Approval Flow

1. User clicks Approve in `DocTab.tsx`.
2. Frontend posts the doc ID plus selected project/task/profile context.
3. Backend loads the `DesignDocument` row and validates task ownership.
4. Backend parses the doc HTML stamp.
5. If no stamp exists, backend reads the active profile's state-edge map using
   the story's live current state as the key.
6. Backend re-fetches task details immediately before transition.
7. If live state differs from the edge current state, return no-op/conflict.
8. Backend resolves current and next names against live project states.
9. Backend updates the task through the existing worktracker repository path.
10. Frontend refreshes tasks/details and shows the resulting message.

---

## Files Touched

| File | Change |
|---|---|
| `core/core/config.py` | Add profile state-edge map with defaults and persistence |
| `web/frontend/src/lib/types.ts` | Mirror profile map type |
| `web/frontend/src/lib/defaultPrompts.ts` | Mirror default state-edge map |
| `server/documents/models.py` | Add document decision persistence model |
| `server/documents/dao.py` | Add decision write/read helpers |
| `server/documents/api.py` | Add approve/disapprove endpoints and HTML edge parser |
| `web/frontend/src/lib/api.ts` | Add document approve/disapprove API calls |
| `web/frontend/src/panes/tabs/DocTab.tsx` | Add button bar, loading state, messages, refresh hooks |
| Doc generation surface | Stamp optional current/next state pair into generated HTML |

---

## Validation Plan

1. Unit-test profile default persistence and frontend/backend default parity.
2. Unit-test HTML edge parsing for present, missing, malformed, and partial
   override stamps.
3. API-test Approve using profile-map edge resolution.
4. API-test Approve using HTML override edge resolution.
5. API-test stale/already-advanced story returns a clear no-op and does not call
   update.
6. API-test renamed/missing state returns a loud error naming the missing state.
7. API-test Disapprove creates a record with nullable note and no Plane update.
8. Frontend-test `DocTab` button visibility, loading state, success/conflict
   messaging, and task refresh calls.

---

## Acceptance Signals

- Approve resolves from HTML override first, otherwise from the profile map keyed
  by the story's live current state.
- A story already advanced by the agent produces a clear no-op/conflict message
  and never transitions to the wrong state.
- Unknown or renamed state names fail explicitly.
- Disapprove persists a decision with room for a future note/rework trigger and
  does not change Plane state.
- Existing agent self-advance behavior continues to work unchanged.
