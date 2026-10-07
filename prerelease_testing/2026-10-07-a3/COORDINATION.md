# Coordination protocol — 0.10.0a3 re-verification (branch `claude/reflex-prerelease-testing-t0sd90`)

Same protocol as the a2 pass ([../2026-10-07/COORDINATION.md](../2026-10-07/COORDINATION.md)); this file only restates
what differs. Several sessions may work this pass at once without talking to each other; git is the only shared state.

## 1. What we are doing
Confirm that the must-fix findings of the a2 pass ([../2026-10-07/RELEASE_PLAN.md](../2026-10-07/RELEASE_PLAN.md)) are
fixed in the published **reflex 0.10.0a3 / reflex-base 0.10.0a3** train plus **reflex-enterprise 0.9.7a5**, by re-running
the ORIGINAL failing repros, and hunt for regressions the fixes introduced. Compact context:
[CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md). Hard rules for every agent: [AGENT_BRIEF.md](./AGENT_BRIEF.md). Per-item
assignments: [briefs/](./briefs/). Results land in [FINDINGS.md](./FINDINGS.md) and [RELEASE_PLAN.md](./RELEASE_PLAN.md)
(orchestrator only).

## 2. Board (`board/`)
- `items/<item>.md` — work items (ports, brief, model). `status: claimed-by-orchestrator` items are run from the
  orchestrating session; leave them alone.
- `claims/<item>.md` — claim with `scripts/claim.sh <item>` (first push wins), release with
  `scripts/release.sh <item> done|blocked|abandoned "<note>"`. A claim older than 4 hours with no commits under the
  item's directory is stale and may be taken over (say so in the claim file).
- `results/<item>.md` — the item's structured report (`CLUSTER:/SUMMARY:/TESTS:/REVERIFIED:/ISSUES:/NOT_COVERED:`).
- `findings-inbox/<item>-<n>.md` — one file per re-verified or new finding, template below. Never edit FINDINGS.md.

```
ITEM: <item>
KIND: reverify | new | verify
REF: <N-0xx / F-0xx from the a2 pass, or ->
TITLE: <one line>
SEVERITY: critical|high|medium|low
STATUS: fixed | still-broken | changed | new | confirmed | refuted
REGRESSION_VS_0.9.12: yes|no|unknown
REGRESSION_VS_0.10.0a2: yes|no|unknown
REPRO: <exact commands, self-contained>
EVIDENCE: <paths under prerelease_testing/2026-10-07-a3/<item>/>
ROOT_CAUSE_GUESS: <file:line in the published package, or unknown>
```

## 3. Working
- Environments: `scripts/bootstrap_envs.sh <scratch-dir> --enterprise` (PyPI only, plus the user-supplied offline
  enterprise a5 wheel, which is NOT in the repo). Export `SB=<scratch-dir>`.
- Artifacts for an item go under `prerelease_testing/2026-10-07-a3/<item>/`: `NOTES.md` with exact rerun commands, app
  sources without `.web/`, `node_modules/`, venvs, `.states/`, `reflex.lock/`, `*.db`; drivers; trimmed logs; screenshots.
  Keep an item under ~10 MB.
- Commit small and often (`git add prerelease_testing/2026-10-07-a3/<item>`, commit, `git pull --rebase`, push). Never
  force-push, never rewrite history, never touch another item's directory or claim. Commit messages end with your
  session's attribution lines.
- Ports: only your item's range.

## 4. Verification of new findings
`verify_*` items ask you to reproduce another item's NEW finding from its written repro alone and try to refute it
(environment quirk, API misuse, pre-existing on 0.9.12/a2, benign). Append `## VERIFICATION` to that item's NOTES.md and
write a `KIND: verify` inbox file.
