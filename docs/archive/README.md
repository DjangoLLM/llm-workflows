# Legacy planning archive

`legacy-specs-2026-09-22.tar.gz` contains the 89 legacy files removed from `spec/` on 2026-09-22. Original repository-relative paths are preserved, including the `spec/` prefix. Every archived file was checked byte-for-byte against its source before removal.

The archive excludes the maintained `spec/VISION.md` and `spec/README.md`. The root `CONTEXT.md` also remains accessible. Archival does not mean these old proposals were implemented or remain approved.

Archive size: 258,726 bytes. Original file contents: 983,880 bytes.

SHA-256:

```text
19a11e346a0371d6917075ba645e572527ce5ac2f45ca345cd576cfbfb163e4a
```

From the repository root, list the archived paths without extracting them:

```sh
tar -tzf docs/archive/legacy-specs-2026-09-22.tar.gz
```

Read one document without restoring it to the working tree:

```sh
tar -xOzf docs/archive/legacy-specs-2026-09-22.tar.gz spec/migration-assessment-tauri-graphql.md
```

To inspect the full archive, including relative links between review artifacts, extract into a fresh temporary directory:

```sh
legacy_spec_dir=$(mktemp -d /tmp/freedom-agents-legacy-specs.XXXXXX)
tar -xzf docs/archive/legacy-specs-2026-09-22.tar.gz -C "$legacy_spec_dir"
```

Keep the archive out of routine agent context. To reactivate a particular proposal, select it with the user, reconcile it with the current vision, restore its required documents to their exact ticket paths, and register it in `spec/README.md`.

Future completed specs follow the Git-backed retirement policy in `AGENTS.md` and `spec/README.md`; they are not appended to this archive.
