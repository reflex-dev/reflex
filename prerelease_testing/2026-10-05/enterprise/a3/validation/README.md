# Artifact validation

Published Ruff in an isolated environment checks all saved a3 Python sources
with E4/E7/E9/F. The new cookie sources additionally pass I/B and formatting.
Agent reports retain focused lint/format logs for their selected helpers.
Copied upstream fixtures are reference/test input, not new framework code.

`artifact-audit.json` covers Python AST parsing without importing apps, JSON and
JSONL parsing, every local Markdown target and generated-file exclusions across
the a3 tree. The central campaign's `artifact-audit.json` separately checks all
Git-visible campaign files and central document links. An initial all-files
audit caught four ignored generated lock files in the copied stable snapshots;
those copied directories were removed before the final successful audit.
Staging also identified ignored generated external assets and app-local
requirements in the stable snapshot. Those copies were removed, the collector
now excludes them, and its final source/evidence hash manifest was refreshed.

`cleanup.json` confirms no listeners on all 13 inspected app/backend/provider/
account-fixture ports. Each agent also records its process cleanup. Runtime
environments remain under `/private/tmp` for independent reproduction. Explicit
Bun paths avoided installation and shell-profile changes.

Git whitespace inspection retains raw logs verbatim: 4,180 diagnostics occur
in logs/HTML, with none in Python/shell/TOML or Markdown. Framework unit
tests/coverage, checkout lint/Pyright and
stub regeneration are outside this published-package validation. No framework
or package implementation files were changed. Browser failures in findings
12–14 remain failures despite passing artifact checks.
