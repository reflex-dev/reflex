---
name: prerelease-test
description: Run the independent pre-release QA campaign for a Reflex release train. Discovers what shipped by reading every CHANGELOG.md on the pre-release branch, checks each package actually published to PyPI, then exercises the new features end-to-end in real apps driven by a real browser using ONLY published packages, upgrade-tests reflex-examples apps from the previous stable, regression-tests reflex-enterprise demos, audits wheel/sdist packaging, and produces a triaged FINDINGS.md plus a fix-before-release plan. Use this whenever a Reflex release is being prepared or checked — the user mentions a pre-release, an alpha/beta/rc, an `r/pre-*` branch, "about to release", release QA, validating a release candidate, or re-verifying that release-blocking fixes landed in a newer alpha. Also use it for the narrower slices on their own: smoke-testing published packages, upgrade/regression testing example apps against a new version, or auditing that packages ship their `.pyi` stubs in both wheel and sdist.
---

# Reflex pre-release testing

This skill runs the QA campaign that stands between a pre-release and a release: independent,
adversarial, end-to-end exercise of what actually got published, from the perspective of a user
who runs `pip install reflex` and opens a browser.

Its value comes from three habits, not from breadth of assertions:

1. **Only published packages.** Everything installs from PyPI into throwaway venvs. The checkout
   has unreleased code, different metadata, and a different dependency graph — testing it tells
   you nothing about what users will get, and a package that failed to publish is itself a
   release blocker you would otherwise miss.
2. **Baseline against the previous stable.** A defect that also reproduces on the last release is
   a bug; one that only reproduces on the new version is a regression and usually a blocker.
   Without the baseline run you cannot tell them apart, and the triage that follows is guesswork.
3. **Adversarially verify before reporting.** Have a second agent reproduce each claimed issue
   from the written repro alone and actively try to refute it. In practice this refutes or
   reclassifies a meaningful share of findings — and it is what makes the report trustworthy
   enough for maintainers to act on directly.

## Deliverables

Produce these under `prerelease-testing/<date>-<version>/` in the repo and commit them to a work
branch as you go (never to `main`):

- `FINDINGS.md` — executive summary, numbered findings with repro + evidence + regression status,
  refuted claims, and per-cluster summaries. Templates: `references/reporting.md`.
- `RELEASE_PLAN.md` — triage into fix-before-release vs file-as-issue. Rubric below.
- One directory per test cluster containing the sample app sources (no `.web/`, `node_modules/`,
  venvs), the driver scripts, `NOTES.md` with exact rerun commands, logs and screenshots.
- `README.md` — what each cluster covers and how to reuse it for the next release.

Findings must be reproducible by a stranger from `NOTES.md` alone. That is the bar: a fix agent
gets handed the finding and nothing else.

## Phases

Work these in order. Phases 2–5 can overlap; 0 and 1 gate everything.

### Phase 0 — Scope discovery

Find the pre-release branch (`git ls-remote --heads origin 'r/pre-*'`, or the user names it), then
read **every** `CHANGELOG.md` on it: the root one plus `packages/*/CHANGELOG.md`. The top entry of
each is what this train ships.

Run the discovery script to extract every package's version and confirm each is published:

    uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref <git-ref>

(Script paths in this skill are repo-root-relative — the repo has its own unrelated `scripts/`
directory, so the prefix matters.) It exits 1 when a package is confirmed missing and 2 when a
check could not complete, so a proxy hiccup never reads as a missing package. An unpublished
version is a finding in its own right — report it immediately rather than working around it.

Read the linked PRs for anything whose intent is not obvious from the changelog line; the GitHub
MCP tools (`mcp__github__pull_request_read`) do this well. Understanding what a change was *for*
is what lets you test it as a user rather than as a checklist.

### Phase 1 — De-risk with a smoke test

Before any fan-out: one venv, `reflex init --template blank`, `reflex run`, then drive it in
Chromium with `.claude/skills/prerelease-test/scripts/drive_app.py`. This shakes out environment
problems (proxy, bun installs, browser path) once, in a context where you can debug them, instead
of inside ten parallel agents.

The scripts carry PEP 723 metadata, so `uv run --script <path>` runs each one in its own isolated
environment (the driver pulls in playwright that way); running them with an existing driver venv's
interpreter works too.

Also confirm the dependency graph resolves the way the changelog says it should (e.g. optional
dependencies genuinely absent, sub-packages pinned as intended).

### Phase 2 — Feature exploration fan-out

Decompose the changelog into clusters of related changes and give each to its own agent, with an
adversarial verification stage behind it. See `references/clusters.md` for how to cut the clusters
and a standing coverage list; `references/orchestration.md` for the Workflow script, schemas and
port map.

The instruction that makes this productive: **real-world exploration, not coverage filling.**
Combine each new feature with the things users actually combine it with — State vars,
`rx._x.client_state`, `rx.ComponentState`, `@rx.memo` wrapping, `rx.foreach`/`rx.cond`, event
chains, background tasks, multiple pages and navigation, dev *and* prod mode. Bugs live in the
interactions, and the original PR's tests already cover the happy path.

Every run inspects all four channels: server log, browser console (errors *and* warnings), network
tab (failed requests, 4xx/5xx), and the rendered page. Findings frequently show up in a channel
nobody asserted on.

### Phase 3 — Upgrade regression

Users upgrade in place; that path has its own failure modes (lockfile migration, pruned packages,
stale `.web/`). Clone `reflex-dev/reflex-examples`, pick apps that span the feature surface —
including ones using third-party packages (`reflex-local-auth`, `reflex-global-hotkey`) and
`reflex[db]`/API apps — then for each:

1. Install the **previous stable** (no `--prerelease` flag, so requirements resolve as a user's
   would), run it, and drive its real user flows in the browser. This is your baseline.
2. Upgrade the *same* venv and *same* app directory in place to the new version, preserving
   `.web/` and `reflex.lock/`. Watch the first run's log closely — that is where migration
   happens. Re-drive the identical flows and compare.
3. Do one cold run (`rm -rf .web`) to check the fresh-install path converges to the same state.

Diff `.web/package.json` before and after; unexpected dependency changes are findings.

### Phase 4 — Enterprise regression

Downstream breakage is the most common release blocker, because removing a public name is
invisible until something imports it. Install the **published** `reflex-enterprise` (never the
checkout) against the new reflex and run its demos — ag-grid, map, dnd, mantine, flow, the MCP
plugin, OIDC. Baseline against the previous stable whenever something fails, so you can say
whether the new release broke it.

Before running anything, grep the published enterprise wheel for names the changelog says moved or
were removed; that finds the breakage in seconds instead of hours.

### Phase 5 — Packaging audit

Audit every package in the train; the discovery script feeds it the whole list. Chain the two with
`&&`, never a pipe — a pipe reports only the audit's exit status, so a package whose PyPI check
never completed would be dropped from the list and the audit would still print PASS over what was
left. The `&&` is what makes that impossible: the audit runs only when discovery exits 0.

    uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py \
      --ref <ref> --specs > specs.txt \
      && xargs uv run --script .claude/skills/prerelease-test/scripts/audit_pyi.py \
        --manifest-ref <ref> < specs.txt

It verifies each package ships its own generated `.pyi` stubs in **both** wheel and sdist, that
they are byte-identical between the two, that no package leaks another package's stubs, and that
counts line up with `pyi_hashes.json` (a package absent from the manifest must ship none).

Stub content hashes legitimately differ from the committed manifest because the build hook
regenerates them at release time — compare *presence and counts*, and wheel against sdist.

### Phase 6 — Triage and report

Write `FINDINGS.md` first (everything confirmed), then `RELEASE_PLAN.md` splitting findings into:

**Fix before release** — anything meeting one of:
- a confirmed regression against the previous stable,
- security-relevant (path traversal, unauthenticated input handling, injection),
- significant user impact, or trivially small to fix (a one-line guard, a missing default).

**File as issues, fix after** — everything else, including pre-existing defects the campaign
happened to surface. Downstream (enterprise) issues go to that project's tracker, not this repo's.

Also flag decisions only a maintainer can make — an undocumented behavior change is either a bug
or a missing changelog entry, and which one it is is their call. Ask rather than assume.

### Phase 7 — Re-verify the next build

When a new alpha ships with the fixes, re-run the *original failing repro* for each finding
(not just the unit tests) against the new published packages, plus a general smoke. Append the
pass/fail table to `FINDINGS.md`. When the final ships, do one last stock-install smoke:
`pip install reflex==<final>` with no prerelease flag, init, run, browser, and confirm the
resolved graph is all-final.

## Working rules

- **Isolation.** Every agent gets its own venv and its own reserved port range; never install into
  a shared venv. See the port map in `references/orchestration.md`.
- **The traps are real.** `references/agent-brief.md` is the brief to hand every agent — it carries
  the environment gotchas (checkout shadowing, proxy variables breaking installs) and the list of
  known-benign console noise. Agents that skip it rediscover the same problems and report noise as
  findings.
- **Concurrency.** Dev servers are heavy (bun + vite + granian). On a 4-CPU box run about two
  agents at a time and one dev server per agent; more just makes everything slow and flaky.
- **Commit as you go.** Each cluster's artifacts land on the work branch when that cluster
  finishes, so a long campaign is never one unrecoverable batch.
- **Never fix framework code during the campaign.** Testing and fixing are separate engagements
  with separate review standards; mixing them costs you the independence that makes the findings
  credible. Record the repro and move on. (If the user then asks for fixes, that is a new task —
  one PR per finding, regression test first, `references/reporting.md` has the PR conventions.)

## Scaling the campaign

Full campaign is roughly 30 agents over several hours. Scale down by dropping whole phases rather
than by testing each phase more shallowly — a shallow pass produces false confidence:

- **Quick check** (~30 min): phases 0, 1, 5, plus grep-based downstream checks from phase 4.
- **Standard** (~2 h): add phase 2 over the three or four highest-risk clusters.
- **Full**: everything, with adversarial verification on every claimed issue.

Ask the user which they want if the request is ambiguous and the difference matters.
