# Adversarial artifact review

The independent reviewer confirmed that current reported behavior—including
the unique UUID migration limit and fresh-Bun browser crash—matches saved
evidence. Framework/package source is unchanged. Four reusable-driver issues
remain for a requested followup; no changes were made to these drivers after
the review, following the repository's review-and-wait instruction.

1. **P2 — The runtime browser driver's pass flag is narrower than its recorded
   diagnostics.** `lifecycle/browser_checks.py` checks page exceptions before
   marking success, but does not reject unexpected console errors or HTTP
   failures. It should capture console locations and request failures and
   enforce a narrow diagnostic allowance. Current evidence was manually
   reviewed, separately from this flag: dev and cold Todo have no console/page/
   observed-HTTP errors; ordinary/prefix prod each have one URL-less console
   404, no page exception and no failing observed HTML/JS/CSS request. The
   fresh-Bun scale case additionally has the independently reported stack
   overflow. `lifecycle/diagnostics-review.json` retains this inspection.
   The sample omits a favicon, but the console record alone cannot prove that
   URL. Do not describe these prod consoles as wholly clean.

2. **P2 — The ORM subprocess does not itself remove `PYTHONPATH`.**
   `services/migrations.py` sanitizes its database-command environment but
   builds the ORM child environment separately. Reuse the sanitized settings
   for every child. Every actual campaign invocation removed `PYTHONPATH` at
   the parent shell, so current runs did not inherit a checkout path. Future
   reruns must keep `env -u PYTHONPATH` until the driver is strengthened.

3. **P2 — Some unexpected failures can discard partial evidence.** Migration
   initialization, ORM/raw SQL operations or subprocess timeouts can raise
   before the result is written, after which TemporaryDirectory removes the
   fixture. HTTP/logging probes also write only after successful assertions.
   A followup should persist commands, revisions, rows and exceptions before
   raising. Current intended migration failures did save their CLI output,
   exact fields and before/after classification; ordinary cases pass. The
   generated unique-constraint revision itself was not archived on the initial
   failing return path. A separate repeat using the unchanged `scenario`
   helper retained the fixture, revisions and two original rows in
   `services/migrations-unique-retained-alpha.json`; the driver limitation
   remains for future unexpected failures.

4. **P2 — The Free-tier credential helper checks a lexical path prefix.**
   `enterprise/free_tier/app/fixture_setup.py` uses `Path.is_relative_to`
   before redirecting credentials. A manually supplied path containing `..`
   can pass that check while resolving outside `/private/tmp`. Current runs
   use safe paths created by `TemporaryDirectory`, and only fictional tokens
   reached the local API. Future direct helper reuse should canonicalize the
   path before checking its location. No helper change followed this review.

The final Free-tier app ran from the retained checkout fixture directory,
including its ignored `.web`, rather than a neutral temporary app directory.
This deviates from the campaign's preferred directory isolation. It does not
change the verified package provenance: `uv --no-config run --no-project`
selected the isolated interpreter, `PYTHONPATH` was absent, and both framework
origins are under that environment's site-packages. Its rerun instructions
should copy the app into a neutral directory, as the central guide requires.

Copied upstream example/demo/reference files are intentionally retained as
fixtures. Their existing style problems are documented in cluster reports;
they are not presented as new framework implementation. Targeted published-Ruff
checks and script syntax checks cover campaign sources. Framework coverage,
checkout Pyright and stub generation were not run.

The full campaign passes Ruff E4/E7/E9/F, and the root inventory/tooling/services/
runtime helpers pass isolated E4/E7/E9/F/I/B. A broad campaign check with I/B
does **not** pass: archived copies and fixtures retain import-order issues and
Overkey's existing `zip` lacks `strict`. Import classification also changes
between neutral and repository working directories. Both complete failing
check outputs are preserved in `validation/`; this report does not claim a
clean full-repository lint/format result.
The final Free-tier source comparison helper additionally has one formatting
wrap reported by `ruff format --check`; its log is retained. Git whitespace
diagnostics belong to captured output and one changelog snapshot, with none in
Python/shell/TOML sources. These results are summarized under `validation/`.

Reports use exact published graphs and site-packages origins. Source branches
were reference input only. Local service mutations, expected errors, fixture
corrections, transient unreproduced Grid.js errors and Bun shell-profile
append/rollback are explicitly recorded. Windows, actual cloud entitlement/
deployment, and external production IdP behavior remain distinct coverage gaps.
