# Coordination protocol for uncoordinated agents (branch `claude/reflex-prerelease-testing-t0sd90`)

Several sessions, on different machines, work this campaign at the same time without talking to each
other. Git is the only shared state. The rules below make that safe. Read this whole file before doing anything.

## 1. What we are doing
Re-verifying the [2026-10-06 findings](../2026-10-06/FINDINGS.md) against the published
**reflex 0.10.0a2 train** (`r/pre-2026.10.06-37579583012`) and finishing the clusters that were interrupted.
[CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md) is the compact context (what shipped, which fix targets which
finding). [AGENT_BRIEF.md](./AGENT_BRIEF.md) carries the hard rules (PyPI-only isolated venvs, never install
from a checkout, real browser runs, baseline against 0.9.12 and 0.10.0a1, report don't fix). Per-item
assignments are in [briefs/](./briefs/).

## 2. The board
- `board/items/<item>.md` — one file per work item: what it covers, which brief, port range, suggested model.
- `board/claims/<item>.md` — exists only while someone owns the item. Create it to claim, edit it to release.
- `board/results/<item>.md` — the item's final structured report (the `CLUSTER:/SUMMARY:/TESTS:/ISSUES:` block
  from the brief), written by whoever finished it.
- `board/findings-inbox/<item>-<n>.md` — one file per NEW or RE-VERIFIED finding (template below). Never edit
  `FINDINGS.md` directly; the orchestrator merges the inbox into it.
- Artifacts for an item go under `prerelease_testing/2026-10-07/<item>/` (NOTES.md with exact rerun commands,
  app sources without `.web/`/`node_modules/`/venvs/`.states/`/`reflex.lock/`/`*.db`, drivers, trimmed logs,
  screenshots; keep an item under ~10 MB).

## 3. Claiming (first push wins)
```
scripts/claim.sh <item>        # creates board/claims/<item>.md with your session id + time, commits, pulls --rebase, pushes
```
If the push is rejected and after `git pull --rebase` a claim file for the item already exists from someone
else, you lost the race: pick another item. A claim older than 4 hours with no commits touching the item's
directory is stale: you may take it over (say so in the claim file). Claim at most two items at a time.
Items marked `status: claimed-by-orchestrator` in `board/items/` are being run from the orchestrating session;
do not take them.

## 4. Working
- Build your own environments with `scripts/bootstrap_envs.sh <scratch-dir>` (creates `alpha2`, `alpha`
  (0.10.0a1), `stable` (0.9.12) and `driver` venvs from PyPI only). Export `SB=<scratch-dir>`; every brief refers
  to `$SB/envs/...`. Chromium: the Playwright-installed one (`playwright install chromium` in the driver venv)
  or `/opt/pw-browsers/chromium` where present.
- Enterprise items need the **offline `reflex-enterprise 0.9.7a4` wheel supplied by the user** (it bypasses the
  login gate). It is proprietary and is NOT in this repo: ask the user for it and put it at
  `$SB/downloads/enterprise_wheel/reflex_enterprise-0.9.7a4-py3-none-any.whl` before running
  `scripts/bootstrap_envs.sh --enterprise`. Without it, use PyPI `reflex-enterprise==0.9.7a4` with `CI=true`
  (the dev login-gate bypass the 10-05 campaign used) and say so in your NOTES.md.
- Paths in briefs written as `/home/user/reflex/...` mean *your checkout root*; `prerelease_testing/2026-10-06/...`
  artifacts (apps, drivers, verification scripts) are there to be copied and re-run.
- Ports: use the item's range only. Different machines cannot collide; two items on one machine must not share.
- Commit small and often: `git add prerelease_testing/2026-10-07/<item>` then `git commit`, `git pull --rebase`,
  `git push`. Never `--force`, never rewrite history, never commit build outputs or venvs (`.gitignore` covers
  the usual ones; check `git status` before adding). Never touch another item's directory or claim file.
- Attribution: commit messages end with your session's attribution lines (whatever your harness prescribes).

## 5. Finishing
1. Copy the final artifacts, write `NOTES.md`, and put the structured report in `board/results/<item>.md`.
2. One inbox file per finding you confirmed or re-verified (`board/findings-inbox/<item>-<n>.md`):
   ```
   ITEM: <item>
   KIND: new | reverify
   REF: <F-00N from 2026-10-06 if reverify, else ->
   TITLE: <one line>
   SEVERITY: critical|high|medium|low
   STATUS: fixed | still-broken | changed | new
   REGRESSION_VS_0.9.12: yes|no|unknown
   REGRESSION_VS_0.10.0a1: yes|no|unknown
   REPRO: <exact commands, self-contained>
   EVIDENCE: <paths under prerelease_testing/2026-10-07/<item>/>
   ROOT_CAUSE_GUESS: <file:line in the published package, or unknown>
   ```
3. Edit `board/claims/<item>.md` to `status: done` (or `blocked: <why>`), commit, pull --rebase, push.
   The orchestrator merges results into `FINDINGS.md` and `RELEASE_PLAN.md`; you do not need to.

## 6. Verification of other people's claims
Items named `verify_*` ask you to reproduce someone else's inbox finding from its written repro alone and try
to refute it (environment quirk, API misuse, pre-existing on 0.9.12, benign). Append a `## VERIFICATION`
section to that item's NOTES.md and write your verdict as a new inbox file with `KIND: verify`.
