# Reflex pre-release testing

This directory lives only on the long-lived branch **`testing/prerelease`**. It holds everything a pre-release QA pass
needs: the regime (this file), the findings registry, reusable fixtures with expected results, the agent brief, the
environment bootstrap, and the history of every past pass. The method itself — phases, rubric, scripts — is the
`prerelease-test` skill in `.claude/skills/prerelease-test/` on `main`; this branch is its working memory.

| path | what it is |
|---|---|
| [`REGISTRY.md`](./REGISTRY.md) | every finding from every pass (deduplicated across ID schemes), its status as of the latest release, where its repro lives, and the "re-verify on every pass" shortlist |
| [`fixtures/`](./fixtures/README.md) | reusable apps, drivers, probes and scripts by area, each with run commands and the expected result on the latest release |
| [`AGENT_BRIEF.md`](./AGENT_BRIEF.md) | the brief every exploration / verification agent gets (hard rules, environment, deliverables); copy and fill per pass |
| [`CAMPAIGN_STATE.template.md`](./CAMPAIGN_STATE.template.md) | the compact per-pass context agents read first |
| [`scripts/bootstrap_envs.sh`](./scripts/bootstrap_envs.sh) | builds the PyPI-only venvs (`new`, `prev`, `ctrl-X`, `driver`, `new-ent`, `prev-ent`) |
| [`history/`](./history/README.md) | findings and release plans of every past pass (0.9.9a1 … 0.10.0a5), with a pointer to the full 320 MB archive |
| `runs/<date>-v<version>/` | the working directory of the current / most recent pass (created per pass) |

## Branch workflow

- `testing/prerelease` = `main` + this directory only. Nothing outside `prerelease-testing/` is ever changed here, so
  bringing it up to date never conflicts: at the start of a pass, `git fetch origin && git rebase origin/main`, then
  `git push --force-with-lease origin testing/prerelease`. (Rebasing keeps the branch a single linear stack of QA commits
  on top of main; merge `origin/main` instead if several people are working the branch at once.)
- Never merge this branch into `main` and never push framework fixes to it: fixes go on their own branches as PRs
  against `main`, one per finding, regression test first.
- Commit small and often during a pass (`git add prerelease-testing/runs/<run>/<item>`), but keep bulk OUT of git:
  logs, screenshots, frame dumps and results stay in the scratch dir (`$SB`); commit only fixtures, NOTES.md, findings and
  small trimmed evidence for a finding (target ≤ 2 MB per item, ≤ 10 MB per pass). The previous archive grew to 320 MB
  in six weeks because every run output was committed.

## Running a pass (e.g. 0.10.1)

1. **Scope.** Find the pre-release branch (`git ls-remote --heads origin 'r/pre-*'`) and tag, read every `CHANGELOG.md`
   top entry, and run the skill's discovery script:
   `uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref v<NEW>`.
   List `git log --oneline v<PREV>..v<NEW>` and read the PRs behind anything non-obvious.
2. **Set up.** Create `runs/<date>-v<NEW>/`, copy `AGENT_BRIEF.md` and `CAMPAIGN_STATE.template.md` into it and fill the
   placeholders. Build the venvs:
   ```
   NEW_VERSION=<NEW> PREV_VERSION=<PREV> CTRL_VERSIONS="<versions needed as positive controls>" \
     ENT_SPEC='reflex-enterprise[mcp]==<ENT>'   # or ENT_WHEEL=<user-supplied offline wheel>
     prerelease-testing/scripts/bootstrap_envs.sh "$SB" --enterprise
   ```
   Run it from a neutral directory (never from the checkout). Clone reflex-examples to `$SB/downloads/` (commit in
   `fixtures/upgrade/README.md`).
3. **Preflight** (orchestrator, Phases 0/1/5 of the skill): publish check, the published reflex wheel's `reflex-base`
   pin, every changed source file byte-identical between `v<NEW>` and the installed `new` venv, the `.pyi` audit
   (`check_release_versions.py --specs … && xargs audit_pyi.py …`, chained with `&&`), changelog / docs check, and a
   blank-app smoke in dev and prod with `drive_app.py`.
4. **Re-verify.** From `REGISTRY.md` take the "re-verify on every pass" shortlist plus everything the new changes touch.
   Each fixture area's README says how to run its checks and what 0.10.0 produced. Run the positive control first.
5. **Hunt.** For each change since `<PREV>`, a focused agent explores it end to end (real apps, real Chromium, dev and
   prod, memory and Redis), compares against `prev`, and reports in the brief's structured format. Two agents at a time on
   a 4-CPU machine; one app server set per agent; ports per `fixtures/README.md`.
6. **Verify.** Every claimed issue goes to an independent verifier that reproduces it from the written repro alone and
   tries to refute, narrow or reclassify it.
7. **Report.** `runs/<run>/FINDINGS.md` (re-verification table first, then numbered new findings with repro, evidence and
   regression status, verifier verdicts, cluster summaries) and `RELEASE_PLAN.md` (fix before release = confirmed
   regression vs the previous release, security-relevant, significant user impact, or trivially small; everything else is
   filed; maintainer decisions called out). Templates: the skill's `references/reporting.md`.
8. **Close out** once the release ships: move the run's top-level docs and item NOTES into `history/<date>-v<NEW>/`, fold
   any new or improved fixture into `fixtures/<area>/` (with its expected result on the released version), update
   `REGISTRY.md` statuses, and delete the rest of `runs/<run>/`.

## Environment notes that cost time when forgotten

- Everything installs from PyPI into throwaway venvs; never `uv sync` / `pip install -e` / run python from a checkout
  (`/home/user/reflex/reflex/` shadows the installed package). Run `uv` with `--no-config` and cwd=`$SB`.
- Client-side HTTP needs `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1`; never export those into the reflex
  server's environment (bun installs then fail through the proxy).
- `REFLEX_TELEMETRY_ENABLED=false` always; enterprise apps from the PyPI wheel need `CI=true`.
- Prod serves frontend and backend on one port (`--frontend-port P --backend-port P`, `REFLEX_API_URL=http://localhost:P`);
  prod with Redis runs 2×CPU+1 granian workers.
- Chromium: `/opt/pw-browsers/chromium`; Playwright's `extra_http_headers` do not reach the websocket upgrade.
- Disk fills up fast: delete each app's `.web/` and `node_modules/` after use.
- The known-benign console and log noise is listed in `AGENT_BRIEF.md`; the known open findings are in `REGISTRY.md`.
