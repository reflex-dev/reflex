# Campaign artifact validation

Final syntax/evidence checks inspect Git-visible campaign files, excluding
ignored virtual environments, frontend builds, installed dependencies and
SQLite databases. The counts and any errors are recorded in
[`../artifact-audit.json`](../artifact-audit.json). Python files are parsed
without importing checkout code; JSON documents and every nonempty JSONL line
are decoded. Central report links and forbidden generated paths are checked.

The complete campaign passes the published Ruff 0.16.10 checks
`--isolated --select E4,E7,E9,F`. This includes the final Free-tier drivers.
The root inventory/tooling/services/runtime helpers also passed isolated
E4/E7/E9/F/I/B; cluster reports record their own targeted checks.

The broader I/B checks do not pass across all retained upstream fixtures.
[`ruff-campaign-context.log`](ruff-campaign-context.log) and
[`ruff-campaign-isolated.log`](ruff-campaign-isolated.log) preserve the failures,
including imported demo style and Overkey's existing `zip` without `strict`.
No full repository lint, formatting, coverage or checkout type-check success is
claimed. No framework code was changed or installed from the checkout.

`git diff --cached --check` reports whitespace in retained raw logs, HTTP/HTML
captures and text output, plus a trailing blank line in the enterprise
changelog-head snapshot. Python,
shell and TOML sources have no Git whitespace diagnostics. The bounded summary
is [`whitespace-review.json`](whitespace-review.json); evidence was preserved
without stripping its bytes. The Free-tier comparison helper also has one
formatting-only wrap reported by `ruff format --check`, documented in that
cluster's report and `logs/final-format.log`. It was left unchanged after
adversarial review.

The final read-only review is in [`../REVIEW.md`](../REVIEW.md). Its driver
limitations remain for a requested followup; manual diagnostics and exact
published dependency graphs support the current findings.
