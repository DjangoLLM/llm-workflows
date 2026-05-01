# Claude Notes

- For managed Temporal steps, make sure the `AgentConfig.result_type` matches the actual payload shape expected by the workflow activity.
- If a workflow activity is declared as returning `dict`, the underlying agent step must return structured data, not a plain string.
- When adding a new LLM-backed pipeline step, prefer an explicit result type or output schema so Temporal does not fail on argument/result decoding.
