# Required coding-agent driver revision

CODING-2056 depends on commit `a9e1911dbe5ad4c53b659b80d995fb57339e0f0d` from the containing `meml` repository branch
`wt/CODIN-2056-typed-codex-inference`.

That revision adds explicit Codex CLI forwarding for `--model` and
`--output-last-message`. It also applies the process deadline to startup, stdin,
stdout and stderr draining, and exit. Timeout, cancellation, and stream failures
terminate and reap the child process. Command logs omit the prompt and remaining
arguments.

The driver regression suite at that revision reports `45 passed, 2 deselected`.
The package-integration slice must publish or otherwise pin an installable package
containing this revision. An editable sibling checkout is not delivery evidence.

Integration with CODING-2042 must retain `codex_cli` while accepting that ticket's
removal of `pi_worker`. This branch keeps `pi_worker` only because it is present in
the current integration base; it must not be restored after CODING-2042 lands.
