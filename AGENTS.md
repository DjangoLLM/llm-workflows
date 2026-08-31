# Agent Notes

- For managed Temporal steps, make sure the `AgentConfig.result_type` matches the actual payload shape expected by the workflow activity.
- If a workflow activity is declared as returning `dict`, the underlying agent step must return structured data, not a plain string.
- When adding a new LLM-backed pipeline step, prefer an explicit result type or output schema so Temporal does not fail on argument/result decoding.
- For Plane design-doc phases, do not stop at `HLD.md` or `LLD.md`. The doc watcher discovers reviewable HTML artifacts, so create or update the matching `HLD.html` or `LLD.html` in the same ticket design directory whenever producing an HLD or LLD deliverable.
- Keep all user-reviewable design artifacts for a Plane ticket in that ticket's exact `spec/<module>/<ticket>/` directory, with supporting assets below it, so relative references and watcher discovery continue to work.
