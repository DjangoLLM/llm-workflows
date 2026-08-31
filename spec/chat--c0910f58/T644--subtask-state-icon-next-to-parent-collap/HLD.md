# HLD: Subtask State Icon in Task Tree

**Plane:** CODIN-644  
**Work item:** `fc9ac27f-6da3-4b9d-9a15-c541ff74db69`  
**Module:** `chat` (`c0910f58-1125-408b-832b-641e047b8407`)  
**Phase:** Todo -> HLD  
**Design directory:** `spec/chat--c0910f58/T644--subtask-state-icon-next-to-parent-collap/`

## 1. Scope

Add a compact workflow-state indicator to existing subtask rows in the task tree. The indicator is a one-character colored dot placed immediately after the existing collapse caret column and before the task identifier/title content.

This is a frontend-only change in the `plane-tui` React/Vite app. The design does not add backend fields, new task-tree data loading, parent rollups, or a new tree renderer.

## 2. Target Surface

Implementation belongs in the `plane-tui` repository, app `web/frontend/`.

Primary component:

- `web/frontend/src/components/tasks/TaskRow.tsx`

Supporting context:

- `web/frontend/src/hooks/useTaskTree.ts`: provides flat tree rows with `depth`, `parentId`, `hasChildren`, and `isExpanded`.
- `web/frontend/src/lib/types.ts`: `TaskSummary.state` already includes `{ name, group, color }`.
- `web/frontend/src/lib/presenter.ts`: already groups top-level tasks by state.
- `web/frontend/src/components/LifecycleBadge.tsx`: existing one-glyph badge vocabulary for agent lifecycle, but not the state source for this feature.

The legacy `tui` name is not a signal to change Python/Textual code. The live task tree is the React frontend.

## 3. Existing Behavior

The tree already renders hierarchical rows with:

- One caret slot per row: expanded, collapsed, or blank for leaf rows.
- Depth indentation from `paddingLeft: depth * 2ch`.
- Section headers that communicate state for top-level tasks.
- Per-task state data already present on every row, including subtasks.

Subtask rows currently do not show their own workflow state in the row.

## 4. Proposed Design

Introduce a fixed-width state-icon slot immediately to the right of the caret slot in `TaskRow`.

Rendering rule:

- If `depth === 0`, render the new slot as empty/non-visible so top-level rows remain visually unchanged.
- If `depth > 0`, render a single dot glyph (`●`) in that slot.
- The dot represents the row task's own `task.state`, not the parent state and not any aggregate child state.

The caret slot remains responsible only for expand/collapse affordance:

- Expandable subtasks show both the caret and the state dot.
- Leaf subtasks keep the blank caret slot and still show the state dot in the adjacent state slot.
- The existing row indentation remains on the row container, so the caret and dot inherit the same depth alignment.

Visual target:

```text
▸ 644 · Parent task
  ▸ ● 645 · Subtask with its own children
    ● 646 · Leaf subtask
  ● 647 · Another leaf subtask
```

## 5. State Color Contract

Use the authentic Plane state color first:

1. If `task.state.color` is present, use it directly as the dot color.
2. If no state color is present, fall back by `task.state.group`.
3. If the group is unknown or missing, use the backlog/muted fallback.

Fallback palette:

| State group | Fallback color intent |
| --- | --- |
| `backlog` | muted gray |
| `unstarted` | blue |
| `started` | amber |
| `completed` | green |
| `cancelled` | red |
| custom/unknown | muted gray |

The LLD should bind these intents to existing frontend tokens/classes if available; otherwise it may use small local constants in `TaskRow.tsx`.

## 6. Accessibility

The dot must not rely on color alone.

Each rendered subtask dot should expose the state name through:

- `title={task.state.name}`
- an accessible label equivalent to the state name, for example `aria-label={task.state.name}`

If the component uses a decorative wrapper plus a screen-reader label, the observable accessibility contract is still: a subtask row exposes its own state name next to the state dot.

## 7. Layout Constraints

The new state slot is a dedicated one-character column, not text appended into the task title.

Design constraints:

- Do not change the caret column width or its click behavior.
- Keep columns aligned between expandable and leaf subtasks.
- Preserve top-level task row visual layout.
- Avoid changing the tree flattening algorithm, section grouping, and row selection behavior.

The exact CSS class names should follow existing `TaskRow.tsx` conventions during LLD/implementation.

## 8. Testing Strategy

Add focused frontend test coverage around `TaskRow` or the existing task-tree rendering tests.

Required cases:

- A top-level task does not render a state dot.
- A leaf subtask renders a dot despite having a blank caret slot.
- An expandable subtask renders both the caret and the state dot.
- The dot uses `state.color` when supplied.
- The group fallback is used when `state.color` is absent.
- The dot exposes the state name via title/accessibility label.

Existing `TasksPane`/`TaskRow` tests should continue to pass.

## 9. Out of Scope

- Parent-row state rollups or aggregate indicators.
- State indicators on top-level task rows.
- Backend/API/data-model changes.
- Changes to `LifecycleBadge` or running-agent count display.
- Rebuilding the task tree or moving grouping logic.
- Python/Textual TUI work.

## 10. Acceptance Mapping

| Requirement | Design answer |
| --- | --- |
| Dot on each subtask row | Render when `depth > 0` |
| Dot directly right of caret | Add a fixed state slot after the existing caret slot |
| Own state, not parent rollup | Read from the current row's `task.state` |
| Color from Plane state | Prefer `task.state.color` |
| Fallback colors | Map by `task.state.group` |
| Accessible name | Provide `title` and accessible label using `task.state.name` |
| Expandable subtasks | Keep caret and render dot |
| Leaf subtasks | Blank caret slot plus dot slot |
| Top-level rows unchanged | Empty/non-visible state slot for `depth === 0`, no top-level dot |
| Tests | Add coverage for rendering, color, fallback, and accessibility |

