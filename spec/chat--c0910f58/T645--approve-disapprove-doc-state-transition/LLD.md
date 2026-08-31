# LLD: Approve/Disapprove Design Docs to Advance Linked Plane Stories

**Ticket:** #645 · `654f7acf-e737-4d83-9ed2-237c384fd34c`  
**Module:** `freedom-chat` / `chat--c0910f58`  
**Implementation repo:** `/Users/karthik/merge_conflicts/coding/plane-tui`  
**Design directory:** `spec/chat--c0910f58/T645--approve-disapprove-doc-state-transition`  
**Phase:** LLD candidate

---

## 1. Scope and Existing Anchors

This work adds a human approval gate to registered design-document tabs in
`plane-tui`. It does not replace the existing agent self-advance prompts. Manual
Approve is an additional path that advances the linked Plane story only when the
resolved edge still matches the story's live state. Manual Disapprove records a
decision and never changes Plane state.

Implementation stays out of `freedom-agents`. That repo only hosts this design
document for the ticket.

Existing anchors in `plane-tui`:

| Surface | Current role | Planned change |
|---|---|---|
| `web/frontend/src/panes/tabs/DocTab.tsx` | Renders sandboxed registered doc iframe and "edit with agent" viewer chrome | Add app-owned Approve/Disapprove controls, request state, and user messages |
| `web/frontend/src/lib/api.ts` | Wraps config, document, and worktracker calls | Add typed document decision calls |
| `web/frontend/src/lib/types.ts` | Frontend API and store types | Add profile state-edge map and document decision payload/result types |
| `web/frontend/src/stores/tasksStore.ts` | Owns selected task, details, live states, and refreshes | Use existing `refreshTasks` and `loadDetails` after decisions |
| `core/core/config.py` | Backend `Profile` model and persisted profile JSON | Add persisted default state-edge map |
| `web/frontend/src/lib/defaultPrompts.ts` | Frontend mirror for workflow defaults | Add frontend default state-edge map beside prompt defaults |
| `server/documents/models.py` | Registered `DesignDocument` model | Add persisted document decision model |
| `server/documents/dao.py` | Async document persistence helpers | Add decision write/list helpers and keep document lookup authoritative |
| `server/documents/api.py` | Document list/serve API and registry boundary | Add approve/disapprove endpoints and HTML edge parser |
| `core/core/plane_client.py` | Worktracker repository abstraction | Reuse `get_task_details`, `get_states`, and `update_task_state`; surface exceptions |

---

## 2. Configuration Contract

Add a profile field named `state_edge_map`.

| Property | Decision |
|---|---|
| Shape | Map from current Plane state name to next Plane state name |
| Default | `Backlog` to `Todo`, `Todo` to `HLD`, `HLD` to `LLD`, `LLD` to `In Progress` |
| Persistence | Stored in profile JSON by `Config.save_profiles` and loaded by `Profile.__init__` |
| Backward compatibility | Missing, null, or non-object values fall back to the default map |
| Name authority | Names are literal Plane state names; IDs are resolved from live project states at approve time |
| Frontend mirror | `Profile` type and default exports include the same default map |

All profile update call sites that currently preserve `agent_prompts`,
`module_folders`, and recent selections must also preserve `state_edge_map`.
This includes project selection, module selection, and module-folder updates.

Do not add a UI editor for the map in this ticket unless existing profile-edit
forms fail without the new field. The minimum requirement is that existing
profiles keep the default map and programmatic profile updates do not erase it.

---

## 3. HTML Edge Override Contract

Generated design HTML may carry an optional edge stamp. The parser accepts the
existing HLD-style stamp and a root attribute pair:

| Source | Fields |
|---|---|
| `meta name="plane-state-edge"` | Text value in the form `Current->Next` |
| Root `data-plane-current-state` and `data-plane-next-state` | Separate current and next names |

Resolution rules:

1. If a complete HTML override exists, it wins over the profile map.
2. If both supported stamp forms exist and disagree, return a loud malformed
   override error rather than guessing.
3. If only one side of a root attribute pair exists, return a loud malformed
   override error.
4. If no complete override exists, use the live story state name as the key into
   the active profile's `state_edge_map`.
5. Whitespace around names is trimmed. Empty names are invalid.
6. The HTML stamp is configuration only. The live story state remains the guard
   authority immediately before transition.

The parser must read only the registered primary HTML file from the
`DesignDocument` row: `root_dir` plus `rel_path`, with the same containment
principle already used by document serving.

---

## 4. Data Model

Add `DocumentDecision` beside `DesignDocument`.

| Field | Type | Constraints / purpose |
|---|---|---|
| `id` | string | Primary key generated at write time |
| `doc_id` | string | FK-like link to `DesignDocument.id`; keep as string or Django FK based on local migration style |
| `task_id` | string | Owning story at decision time |
| `decision` | string | Initially `approved` or `disapproved`; approve history is useful audit data even when a transition no-ops |
| `state_at_decision` | string | Live story state name when the decision request was handled |
| `resolved_current_state` | string, nullable | Edge current state used for approve; null for disapprove if no edge was needed |
| `resolved_next_state` | string, nullable | Edge next state used for approve; null for disapprove |
| `edge_source` | string, nullable | `html_override` or `profile_map` for approve; null for disapprove |
| `note` | text, nullable | Reviewer note/reason, present now for future rework automation |
| `outcome` | string | `transitioned`, `noop_conflict`, `failed`, or `recorded` |
| `message` | text | Human-readable result saved for audit/debugging |
| `created_at` | string | UTC ISO timestamp |

Indexes:

| Index | Purpose |
|---|---|
| `task_id`, `created_at` | Review decision history for a story |
| `doc_id`, `created_at` | Review decision history for a document |

Approve must write a decision record for successful transitions and conflict
no-ops. For validation failures before the document and task are known, no
record is required. For update failures after the edge and live state are known,
write a failed decision when possible, then return an error.

Disapprove always writes a `recorded` decision and leaves Plane untouched.

---

## 5. Backend API Contract

Add document decision endpoints under the existing documents router.

| Method and path | Purpose |
|---|---|
| `POST /api/documents/{doc_id}/approve` | Resolve edge, guard live state, transition by live state ID |
| `POST /api/documents/{doc_id}/disapprove` | Persist a reviewer decision without Plane transition |

Approve request fields:

| Field | Required | Notes |
|---|---|---|
| `project_id` | yes | Used for task details, states, and update |
| `task_id` | yes | Must match `DesignDocument.task_id` |
| `profile` | no | Same profile index semantics as existing document listing/worktracker calls |
| `note` | no | Optional audit note |

Disapprove request fields:

| Field | Required | Notes |
|---|---|---|
| `project_id` | yes | Used to capture live state name |
| `task_id` | yes | Must match `DesignDocument.task_id` |
| `profile` | no | Same profile index semantics |
| `note` | no | Optional reviewer note/reason |

Approve success and no-op response fields:

| Field | Meaning |
|---|---|
| `status` | `transitioned` or `noop_conflict` |
| `message` | Clear user-facing message |
| `doc_id` | Registered document ID |
| `task_id` | Linked story ID |
| `state_at_decision` | Live story state observed before any transition |
| `expected_current_state` | Resolved edge current state |
| `next_state` | Resolved edge next state |
| `edge_source` | `html_override` or `profile_map` |
| `updated_task` | Returned task summary for transition success; absent for no-op |

Disapprove response fields:

| Field | Meaning |
|---|---|
| `status` | `recorded` |
| `message` | Confirms no Plane state change |
| `decision_id` | Persisted decision row |
| `doc_id` | Registered document ID |
| `task_id` | Linked story ID |
| `state_at_decision` | Live story state at click time |

Error handling:

| Condition | Response |
|---|---|
| Unknown doc ID | 404 with `document_not_found` |
| Task mismatch between request and registry | 409 with `document_task_mismatch` |
| Missing project or task | 400 with explicit missing field |
| Scratch document or scratch task | 400 with `task_document_required` |
| Missing edge in profile map | 409 with current state and profile source |
| Malformed HTML override | 400 with parser-specific message |
| Unknown current or next state name | 409 naming the missing state and source |
| Live story state differs from resolved current | 200 `noop_conflict`, not an exception |
| Worktracker update failure | 502 or 500 with surfaced failure message, never silent false |

---

## 6. Backend Approval Flow

Approve endpoint steps:

1. Load the `DesignDocument` row by `doc_id`.
2. Reject scratch or mismatched task context.
3. Resolve the profile with the same helper used by worktracker-backed document
   listing.
4. Re-fetch task details immediately and capture the live state name.
5. Parse the registered HTML file for a complete override.
6. If no override exists, look up the live state name in `profile.state_edge_map`.
7. Resolve both current and next state names against `repo.get_states(project_id)`
   using exact names. Reject unknown or duplicated names loudly.
8. Compare live task state name to the resolved current state name.
9. If the names differ, persist a `noop_conflict` approval decision and return a
   clear no-op message without calling update.
10. Call `repo.update_task_state(project_id, task_id, next_state_id)`.
11. Persist a `transitioned` approval decision with the edge and message.
12. Return the updated task summary and message.

Name matching is exact and case-sensitive for configured state names. This avoids
silently approving a typo or renamed workflow state. The UI may display available
state names from the existing `states` store, but the backend remains the source
of truth.

Disapprove endpoint steps:

1. Load the `DesignDocument` row by `doc_id`.
2. Reject scratch or mismatched task context.
3. Resolve profile and re-fetch task details to capture `state_at_decision`.
4. Persist a `disapproved` decision with optional note.
5. Return `recorded` and do not call `update_task_state`.

---

## 7. Frontend Behavior

`DocTab.tsx` adds a compact action bar in the existing viewer chrome, outside the
sandboxed iframe and near the current "edit with agent" control.

Visibility:

| Condition | Behavior |
|---|---|
| No selected project | Hide decision controls |
| No selected real task or scratch task selected | Hide decision controls |
| `doc.docId` missing | Hide decision controls |
| Selected task details still loading | Disable controls |
| Real task doc selected | Show Disapprove and show Approve when the current state can resolve locally from HTML metadata already known or profile map |

Because the HTML file is sandboxed and not currently parsed client-side, the
minimum implementation may show Approve for any real task doc and let the
backend return missing-edge or malformed-override messages. If a lightweight
metadata endpoint is added to support stricter visibility, it must reuse the same
server parser and must not duplicate parsing logic in the browser.

Approve interaction:

1. Read `selectedProjectId`, `selectedTaskId`, `details.task.state.name`, and
   `recentProfileIndex`.
2. Disable both decision buttons while the request is in flight.
3. POST the approve request through `api.ts`.
4. Show the returned success or no-op message in viewer chrome.
5. Refresh the module task list through `refreshTasks`.
6. Refresh selected task details through `loadDetails` if the same task is still
   selected.
7. On API error, show the `ApiError.message` text and keep the current selection.

Disapprove interaction:

1. Prompt for an optional note only if a small existing modal/input pattern is
   already available. Otherwise send no note in this ticket and leave note entry
   UI for the follow-up.
2. Disable both decision buttons while saving.
3. POST the disapprove request through `api.ts`.
4. Show the saved-decision message.
5. Refresh details only if needed to keep live state text current; do not call a
   state update path.

Button copy:

| Control | Text | Disabled text |
|---|---|---|
| Approve | `Approve` | `Approving...` |
| Disapprove | `Disapprove` | `Saving...` |

The message area should be small, persistent until the next decision click, and
use existing pane colors. Avoid modal-only feedback for approve results because
conflict/no-op is an expected outcome when the agent already advanced the story.

---

## 8. API Client and Types

Add frontend types for:

| Type | Fields |
|---|---|
| `StateEdgeMap` | Record from state name to next state name |
| `DocumentDecisionRequest` | `project_id`, `task_id`, optional `profile`, optional `note` |
| `DocumentApproveResult` | Response fields from the approve endpoint |
| `DocumentDisapproveResult` | Response fields from the disapprove endpoint |

Add `approveDocument` and `disapproveDocument` functions in `api.ts`. These use
the normal `request` helper, not `worktrackerRequest`, because the endpoints live
on the local app backend and the backend resolves worktracker credentials from
the profile.

Update every frontend profile update payload to include `state_edge_map` when it
exists on the active profile. This prevents profile persistence from dropping the
new field when users select projects/modules or set module folders.

---

## 9. Migration and Compatibility

Database:

| Migration | Change |
|---|---|
| `documents` next migration | Create `DocumentDecision` table and indexes |

Config:

| Existing profile JSON | Behavior |
|---|---|
| No `state_edge_map` | Runtime profile gets the default map |
| Empty map | Treat as configured empty map only if explicitly persisted; approve then reports no edge for current state |
| Invalid map shape | Fall back to default and avoid crashing config load |

The default map is intentionally mirrored in backend and frontend. Tests should
assert the expected keys and values on both sides so future prompt/workflow edits
do not drift silently.

---

## 10. Validation Plan

Backend unit/API tests:

1. Config loads old profile JSON and exposes default `state_edge_map`.
2. Config saves `state_edge_map` without dropping existing profile fields.
3. HTML parser accepts meta stamp, root data stamp, and missing stamp.
4. HTML parser rejects partial, empty, and disagreeing stamps.
5. Approve with profile-map edge transitions `HLD` to `LLD` when live state is
   `HLD`.
6. Approve with HTML override uses the override ahead of the profile map.
7. Approve with already-advanced story returns `noop_conflict` and never calls
   `update_task_state`.
8. Approve with unknown current or next state name returns an explicit error.
9. Approve with task mismatch returns conflict and does not touch Plane.
10. Worktracker update exception is surfaced and does not become a silent false.
11. Disapprove creates a decision row with nullable note and does not call
    `update_task_state`.
12. DAO tests cover decision insertion and task/doc history ordering.

Frontend tests:

1. `api.ts` posts approve/disapprove payloads to the new local endpoints.
2. `DocTab` hides controls for scratch/no-task contexts.
3. `DocTab` disables controls during requests.
4. Approve success refreshes tasks and selected details, then shows the success
   message.
5. Approve no-op refreshes tasks/details and shows the conflict message.
6. Approve API error shows the server message and does not mutate local task
   state optimistically.
7. Disapprove shows saved-decision feedback and does not call status update.
8. Profile-preserving flows keep `state_edge_map` in update payloads.

Manual check:

1. Open a registered `LLD.html` for a real task in `HLD`.
2. Click Approve and confirm the story advances to `LLD`.
3. Move the story again through the agent or status modal, then click Approve on
   a stale doc and confirm the UI shows the no-op conflict.
4. Click Disapprove and confirm a decision record appears while Plane state does
   not change.

---

## 11. Implementation Sequence

1. Add backend profile `state_edge_map` defaults, persistence, and config tests.
2. Mirror the type/default in frontend profile types and defaults, then update
   profile-preserving call sites.
3. Add `DocumentDecision` model, migration, DAO helpers, and DAO tests.
4. Add the HTML edge parser in `server/documents/api.py` or a small documents
   helper module, with parser tests.
5. Add approve/disapprove endpoint request and response schemas, then implement
   validation, profile resolution, live-state fetch, edge resolution, guard,
   state ID lookup, decision persistence, and update call.
6. Add API tests for transition success, HTML override, profile fallback,
   no-op conflict, unknown state names, task mismatch, update failure, and
   disapprove persistence.
7. Add frontend API functions and result types.
8. Extend `DocTab.tsx` with the action bar, loading state, message state, and
   refresh calls.
9. Add frontend tests for visibility, loading, success/no-op/error messages,
   refreshes, and disapprove behavior.
10. Run focused backend and frontend tests before broad validation.

---

## 12. Acceptance Checklist

- Approve resolves from HTML override first, otherwise from the profile map
  keyed by the story's live current state.
- Approve re-fetches the story and guards against stale/already-advanced state
  before updating.
- Unknown or renamed state names fail loudly with the missing name and source.
- A stale story returns a clear no-op message and never transitions to the wrong
  state.
- Disapprove persists a decision with nullable note and never changes Plane.
- Existing agent self-advance prompts and update path remain intact.
- All implementation changes land in `plane-tui`; this repo contains only the
  design document for this ticket.
