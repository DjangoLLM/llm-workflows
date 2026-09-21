# FreedomAgentsRust implementation breakdown

Published as 27 Implementation children across eight Stories. Core working is task 16, completing Phase 5. Later tasks integrate and deliver the proven core. All tasks inherit pure Rust execution and SQLite initially. Tracker blocker links are authoritative.

## Published ticket map

+1. CODING-2074: Run a typed Rust code step from a standalone consumer
2. CODING-2075: Validate execution definitions and dispatch through one Rust catalog
3. CODING-2076: Prove supported host capabilities for headless execution
4. CODING-2077: Execute and reopen a code pipeline in SQLite
5. CODING-2078: Record step failures and preserve valid lineage
6. CODING-2079: Make ledger completion idempotent under competing attempts
7. CODING-2080: Persist one native typed inference result in Rust
8. CODING-2081: Complete a typed Rust tool round trip inside the agent loop
9. CODING-2082: Bound validation repair, deadlines, and cancellation
10. CODING-2083: Run a Rust code-and-agent workflow on Temporal
11. CODING-2084: Resume a Temporal agent across recorded turns and tool activities
12. CODING-2085: Expose worker health, cancellation, and graceful shutdown
13. CODING-2086: Reconcile duplicate workflow starts across crashes
14. CODING-2087: Retry branches without changing recorded decisions
15. CODING-2088: Recover tool effects with stable invocation keys
16. CODING-2089: Pass the integrated headless core recovery gate
17. CODING-2090: Compose execution contributions from two reusable Apps
18. CODING-2091: Start and control workflows through protected GraphQL commands
19. CODING-2092: Recover separate-worker updates through cursor subscriptions
20. CODING-2093: Expose permitted Rust tools over MCP STDIO
21. CODING-2094: Port the research scrape-and-summary consumer to Rust
22. CODING-2095: Validate and import a historical execution snapshot
23. CODING-2096: Resume interrupted imports without publishing partial history
24. CODING-2097: Rehearse versioned workflow cutover and rollback
25. CODING-2098: Install and run packaged Rust artifacts in a clean Project
26. CODING-2099: Back up, restore, and upgrade the SQLite runtime safely
27. CODING-2100: Verify and record the integrated Rust release

1. [Run a typed Rust code step from a standalone consumer](T2066--phase-1-establish-the-pure-rust-core-and/implementation-drafts/01-run-a-typed-rust-code-step-from-a-standalone-consumer.md)
   - Parent: CODING-2066. Blocked by: none.
   - Delivers: A separate headless Rust program executes a registered deterministic code step and receives a typed result through the new public core.

2. [Validate execution definitions and dispatch through one Rust catalog](T2066--phase-1-establish-the-pure-rust-core-and/implementation-drafts/02-validate-execution-definitions-and-dispatch-through-one-rust-catalog.md)
   - Parent: CODING-2066. Blocked by: 1.
   - Delivers: An application composes step, tool, and agent definitions once and either starts with a valid catalog or fails with an actionable configuration error.

3. [Prove supported host capabilities for headless execution](T2066--phase-1-establish-the-pure-rust-core-and/implementation-drafts/03-prove-supported-host-capabilities-for-headless-execution.md)
   - Parent: CODING-2066. Blocked by: 2.
   - Delivers: The same core consumer can use host-supplied execution capabilities without depending on GraphQL request context or violating framework Module rules.

4. [Execute and reopen a code pipeline in SQLite](T2067--phase-2-persist-managed-runs-and-code-st/implementation-drafts/04-execute-and-reopen-a-code-pipeline-in-sqlite.md)
   - Parent: CODING-2067. Blocked by: 3.
   - Delivers: A Rust caller runs two code steps, closes the process, and reads their durable output and lifecycle from a reopened SQLite store.

5. [Record step failures and preserve valid lineage](T2067--phase-2-persist-managed-runs-and-code-st/implementation-drafts/05-record-step-failures-and-preserve-valid-lineage.md)
   - Parent: CODING-2067. Blocked by: 4.
   - Delivers: Preprocessing, execution, and postprocessing failures remain auditable, while related steps retain correct directed lineage.

6. [Make ledger completion idempotent under competing attempts](T2067--phase-2-persist-managed-runs-and-code-st/implementation-drafts/06-make-ledger-completion-idempotent-under-competing-attempts.md)
   - Parent: CODING-2067. Blocked by: 5.
   - Delivers: Repeated completion and concurrent writers preserve the accepted result rather than letting a late attempt overwrite it.

7. [Persist one native typed inference result in Rust](T2068--phase-3-implement-typed-rust-agents-tool/implementation-drafts/07-persist-one-native-typed-inference-result-in-rust.md)
   - Parent: CODING-2068. Blocked by: 6.
   - Delivers: A managed Rust agent calls the configured provider and returns a nested typed result persisted in SQLite.

8. [Complete a typed Rust tool round trip inside the agent loop](T2068--phase-3-implement-typed-rust-agents-tool/implementation-drafts/08-complete-a-typed-rust-tool-round-trip-inside-the-agent-loop.md)
   - Parent: CODING-2068. Blocked by: 7.
   - Delivers: An agent selects a permitted Rust tool, receives its validated result, and produces a checked final answer.

9. [Bound validation repair, deadlines, and cancellation](T2068--phase-3-implement-typed-rust-agents-tool/implementation-drafts/09-bound-validation-repair-deadlines-and-cancellation.md)
   - Parent: CODING-2068. Blocked by: 8.
   - Delivers: Malformed model output can be corrected within a fixed budget, while timeout/cancellation reliably ends owned local work and records failure.

10. [Run a Rust code-and-agent workflow on Temporal](T2069--phase-4-execute-rust-pipelines-through-t/implementation-drafts/10-run-a-rust-code-and-agent-workflow-on-temporal.md)
   - Parent: CODING-2069. Blocked by: 9.
   - Delivers: A Rust client submits a workflow to a Rust worker and receives the result of a code step followed by typed inference.

11. [Resume a Temporal agent across recorded turns and tool activities](T2069--phase-4-execute-rust-pipelines-through-t/implementation-drafts/11-resume-a-temporal-agent-across-recorded-turns-and-tool-activities.md)
   - Parent: CODING-2069. Blocked by: 10.
   - Delivers: A worker restart resumes a multi-turn agent using completed Temporal activity results rather than restarting its conversation.

12. [Expose worker health, cancellation, and graceful shutdown](T2069--phase-4-execute-rust-pipelines-through-t/implementation-drafts/12-expose-worker-health-cancellation-and-graceful-shutdown.md)
   - Parent: CODING-2069. Blocked by: 11.
   - Delivers: Operators can diagnose startup and stop or cancel work without silently losing lifecycle state.

13. [Reconcile duplicate workflow starts across crashes](T2070--phase-5-prove-core-recovery-idempotency/implementation-drafts/13-reconcile-duplicate-workflow-starts-across-crashes.md)
   - Parent: CODING-2070. Blocked by: 12.
   - Delivers: Repeated or concurrent submissions create one logical run even if the process dies between SQLite commit and Temporal acknowledgement.

14. [Retry branches without changing recorded decisions](T2070--phase-5-prove-core-recovery-idempotency/implementation-drafts/14-retry-branches-without-changing-recorded-decisions.md)
   - Parent: CODING-2070. Blocked by: 13.
   - Delivers: A branch retry keeps its accepted agent choice; explicit reconsideration records a new decision and audit link.

15. [Recover tool effects with stable invocation keys](T2070--phase-5-prove-core-recovery-idempotency/implementation-drafts/15-recover-tool-effects-with-stable-invocation-keys.md)
   - Parent: CODING-2070. Blocked by: 14.
   - Delivers: A completed external mutation is deduplicated on retry, while an ambiguous non-idempotent action waits for explicit resolution.

16. [Pass the integrated headless core recovery gate](T2070--phase-5-prove-core-recovery-idempotency/implementation-drafts/16-pass-the-integrated-headless-core-recovery-gate.md)
   - Parent: CODING-2070. Blocked by: 15.
   - Delivers: A fresh Rust consumer demonstrates durable code-plus-agent execution and recovery without GraphQL or a UI.

17. [Compose execution contributions from two reusable Apps](T2071--phase-6-integrate-the-rust-core-with-reu/implementation-drafts/17-compose-execution-contributions-from-two-reusable-apps.md)
   - Parent: CODING-2071. Blocked by: 16.
   - Delivers: A clean consumer Project installs two Apps and obtains matching worker/API runtime catalogs through supported generated registration.

18. [Start and control workflows through protected GraphQL commands](T2071--phase-6-integrate-the-rust-core-with-reu/implementation-drafts/18-start-and-control-workflows-through-protected-graphql-commands.md)
   - Parent: CODING-2071. Blocked by: 17.
   - Delivers: A generated client contract can start/read/control a run while raw generated writes cannot fabricate outcomes.

19. [Recover separate-worker updates through cursor subscriptions](T2071--phase-6-integrate-the-rust-core-with-reu/implementation-drafts/19-recover-separate-worker-updates-through-cursor-subscriptions.md)
   - Parent: CODING-2071. Blocked by: 18.
   - Delivers: A subscriber sees committed lifecycle changes from a separate worker and catches up after disconnect without losing state.

20. [Expose permitted Rust tools over MCP STDIO](T2071--phase-6-integrate-the-rust-core-with-reu/implementation-drafts/20-expose-permitted-rust-tools-over-mcp-stdio.md)
   - Parent: CODING-2071. Blocked by: 18.
   - Delivers: An MCP client discovers and invokes the same validated Rust tools through the native runtime.

21. [Port the research scrape-and-summary consumer to Rust](T2072--phase-7-port-a-rust-consumer-and-rehears/implementation-drafts/21-port-the-research-scrape-and-summary-consumer-to-rust.md)
   - Parent: CODING-2072. Blocked by: 19, 20.
   - Delivers: A reusable Rust consumer validates a URL, retrieves content through the configured native HTTP tool, and produces a typed agent summary.

22. [Validate and import a historical execution snapshot](T2072--phase-7-port-a-rust-consumer-and-rehears/implementation-drafts/22-validate-and-import-a-historical-execution-snapshot.md)
   - Parent: CODING-2072. Blocked by: 21.
   - Delivers: Operators can validate a versioned history snapshot and import it into SQLite with preserved identities and relationships.

23. [Resume interrupted imports without publishing partial history](T2072--phase-7-port-a-rust-consumer-and-rehears/implementation-drafts/23-resume-interrupted-imports-without-publishing-partial-history.md)
   - Parent: CODING-2072. Blocked by: 22.
   - Delivers: A failed import can resume safely, while changed snapshots and identity conflicts fail without exposing a partial successful import.

24. [Rehearse versioned workflow cutover and rollback](T2072--phase-7-port-a-rust-consumer-and-rehears/implementation-drafts/24-rehearse-versioned-workflow-cutover-and-rollback.md)
   - Parent: CODING-2072. Blocked by: 23.
   - Delivers: New requests move to Rust workflows while legacy histories remain separate, and a rollback rehearsal preserves later Rust work.

25. [Install and run packaged Rust artifacts in a clean Project](T2073--phase-8-package-and-verify-the-rust-migr/implementation-drafts/25-install-and-run-packaged-rust-artifacts-in-a-clean-project.md)
   - Parent: CODING-2073. Blocked by: 24.
   - Delivers: A clean consumer installs the reusable App and pinned Rust artifacts, starts the worker, and executes the reference workflow.

26. [Back up, restore, and upgrade the SQLite runtime safely](T2073--phase-8-package-and-verify-the-rust-migr/implementation-drafts/26-back-up-restore-and-upgrade-the-sqlite-runtime-safely.md)
   - Parent: CODING-2073. Blocked by: 25.
   - Delivers: Operators can restore a consistent ledger and upgrade it without losing identities or silently accepting an incompatible schema.

27. [Verify and record the integrated Rust release](T2073--phase-8-package-and-verify-the-rust-migr/implementation-drafts/27-verify-and-record-the-integrated-rust-release.md)
   - Parent: CODING-2073. Blocked by: 26.
   - Delivers: One release acceptance record proves the complete installed runtime across execution, recovery, transports, consumer migration, and operations.

