# upgrade_packaging — reflex 0.10.1a1 vs 0.10.0 (2026-10-24)

Item: in-place upgrades of reflex-examples apps, `.web/package.json` diffs, Bun 1.4.4, install matrix (Python
3.11-3.15, pip + uv), `#7440` reflex.model without greenlet, mixed sibling floors, sdists (`#7411`), `reflex init`
(`#7556`), third-party sweep, docs `#7646`.

Environment: `SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa`, work dir
`W=$SB/apps/upgrade_packaging/upgrade` (staged with `fixtures/upgrade/bin/stage.sh`, `VENV_PREFIX=upgrade_packaging`,
`NEW=new`, `PREV=prev`). Ports 3460-3499 / 8460-8499. Every command below runs with cwd=`$SB` (never a checkout) and
`uv --no-config`.

Rerun recipe (from a fresh shell):
```bash
export SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
export W=$SB/apps/upgrade_packaging/upgrade NEW=new PREV=prev VENV_PREFIX=upgrade_packaging
cd $SB && bash /home/user/wt-testing/prerelease-testing/fixtures/upgrade/bin/stage.sh
```

## Harness notes (not product findings)

- The shared `$SB/envs/prev` venv is NOT a pure 0.10.0 graph: it was built with `--prerelease=allow`, so it holds
  reflex-components-code 0.10.1a1, reflex-components-moment 0.10.1a1, reflex-components-lucide 1.1.1a1 and
  reflex-hosting-cli 0.2.1a1 next to reflex/reflex-base/core/radix/dataeditor 0.10.0. Every 0.10.0 baseline in this
  item uses its own venv resolved WITHOUT a prerelease flag (`uv pip install 'reflex[db]==0.10.0'` or pip without
  `--pre`), which yields the final 0.10.0 train (code/moment 0.10.0, lucide 1.1.0, hosting-cli 0.2.0).
- `/apps/upgrade_sweep` (filesystem root) pre-existed from an earlier campaign; a first staging attempt of this item
  briefly created `/apps/upgrade_packaging` (an `export A=.. B=$A` ordering slip) and was removed again.

## Sections

(filled in incrementally below)
