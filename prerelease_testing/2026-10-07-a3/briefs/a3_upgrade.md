# Item `a3_upgrade` — in-place upgrades to 0.10.0a3 (from 0.9.12 and from 0.10.0a2), install paths, and the upgrade guide's samples

Ports: frontend 3200-3239, backend 8200-8239 (redis 8209). Work dir: $SB/apps/a3_upgrade/.
DEST: /home/user/reflex/prerelease_testing/2026-10-07-a3/a3_upgrade/
Venvs: make your own per app (the upgrade mutates them): build each from PyPI with the version you start from.

Read first: ../CAMPAIGN_STATE.md, ../AGENT_BRIEF.md, ../../2026-10-07/upgrade_sweep/NOTES.md (apps, drivers, exact flows — COPY them),
`git -C /home/user/reflex show 555b667c1:docs/changelog/upgrading/upgrading-to-0-10.md`, `...:docs/vars/base_vars.md`,
`...:docs/hosting/self-hosting.md`, `...:docs/database/tables.md`.

## Do
1. 0.9.12 → a3 in place (same venv, same app dir, keep .web/ and reflex.lock/) for form-designer, github-stats, clock and twitter
   (disk prod and Redis prod), driving the same flows as the a2 pass; then a cold run (`rm -rf .web`). Diff .web/package.json.
   Redis-pickled 0.9.12 sessions must survive the upgrade (0.10 loads 0.9 state).
2. a2 → a3 in place with pip (`pip install -U --pre reflex==0.10.0a3`) and uv (`uv pip install -U --prerelease=allow reflex==0.10.0a3`):
   confirm reflex-base moves to 0.10.0a3 too (the published wheel pins `reflex-base==0.10.0a3`) and that nothing else moves
   unexpectedly (freeze diff). Also `pip install --pre reflex==0.10.0a3` into a fresh venv and a fresh `reflex[db]` without
   `--pre` resolution checks (what does a stock `pip install reflex` give today?).
3. Upgrade guide: run every code sample of upgrading-to-0-10.md on a3 (and the ones that claim to work on 0.9 on 0.9.12): the
   `default_value()` / `get_fields()[...]` recipes, ClassVar recipe, class-default assignment scope examples, background-task
   inherited-handler example, the state-store note. Check each statement against observed behavior; report wrong or misleading ones.
4. Quick smoke of `reflex component` (#7497 pointer text and exit code), `reflex init --template blank` + run dev/prod on Python 3.11
   and 3.14, and `reflex run --json` stopped with SIGINT and SIGTERM while a slow consumer reads the pipe (#7428: no truncated
   JSON line, shutdown within ~30 s, exit code) vs a2.
Write one inbox file per finding. Copy artifacts to DEST as you go; commit per the protocol.
