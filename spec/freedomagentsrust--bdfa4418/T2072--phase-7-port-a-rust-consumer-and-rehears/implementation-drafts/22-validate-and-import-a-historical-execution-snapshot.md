# 22. Validate and import a historical execution snapshot

## Parent

CODING-2072. See [implementation specification](../SPEC.md).

## What to build

Operators can validate a versioned history snapshot and import it into SQLite with preserved identities and relationships.

## Acceptance criteria

- [ ] Implement the snapshot manifest, checksums, record versions, and explicit source mappings in Rust.
- [ ] Reject duplicate/conflicting IDs, malformed records, unknown required status, broken references, and cycles before publishing imported history.
- [ ] Preserve JSON/null/times/lineage and mark missing legacy attempts unknown rather than inventing them.
- [ ] Imported records stay historical/read-only and cannot create dispatch intent; counts and canonical values match fixtures.

## Blocked by

- Draft 21: Port the research scrape-and-summary consumer to Rust under CODING-2072.

## Constraints

Pure Rust execution with SQLite initially. No Python/JavaScript execution workers, UI implementation, or database replacement. Use public behavior tests and the supported framework capabilities. Preserve generated-contract ownership. No agents launch as part of creating this ticket.

