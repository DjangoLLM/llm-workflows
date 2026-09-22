# Source directory layout

Status: retirement pending. Implementation and verification complete.

Move the installable library into `src/`, preserving public `agents.*`
imports and Django app identity. Keep tests, docs, specs, and project configuration
at the repository root. Move the standalone research sample into examples.
Update package discovery, development test paths, and maintained documentation.

This changes filesystem organization only. No inference split criterion is
triggered. Preserve existing work and leave generated local artifacts untouched.
Packaging maps the import package `agents` directly to `src`, without an extra
`agents` directory. An editable install provides that mapping during development.

Verify the non-live suite and a clean package build, including Django migrations
and management commands. Retirement covers only this spec and requires exact
content recoverable from Git.


Verification: 282 non-live tests passed. A clean package build includes all Python
source files. The refreshed editable installation resolves `agents` directly to
`src/__init__.py`. `git diff --check` passed. This untracked spec is retained
until its exact content is recoverable from Git.
