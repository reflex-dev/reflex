# reverify_a2 — reflex 0.9.9a2 enterprise re-verification artifacts

Re-verification (2026-08-28) that reflex 0.9.9a2 (PyPI, published 2026-08-28) restores
reflex-enterprise 0.9.4 compatibility broken on 0.9.9a1, via the deprecation shims from
PR #6967 (bundled_libraries) and PR #6985 (DECORATED_PAGES, get_config(reload=True)).
Result: FINDING-021/022/023 all VERIFIED-FIXED; mantine regression sweep clean.
Full narrative: the "## 0.9.9a2 re-verification (enterprise)" section of ../FINDINGS.md.

## Rerun

```bash
SB=<scratch dir>; mkdir -p $SB/apps/reverify_ent && cd $SB/apps/reverify_ent
uv venv venv --python 3.11
uv pip install --python venv/bin/python --prerelease=allow 'reflex==0.9.9a2' 'reflex-enterprise==0.9.4'

# offline shim probes (FINDING-001/021/022/023 + get_config surface):
./venv/bin/python probe_shims_a2.py                     # from this dir; exits 0, prints warnings
./venv/bin/python ../ent_map_dnd/repro_finding001_dnd_can_drop.py   # FINDING-022; exit 0 on a2

# FINDING-021 e2e: copy ../ent_aggrid/minimal, rm -rf reflex.lock .web .states, then
cd minimal && CI=1 REPRO_LAMBDA=1 REFLEX_TELEMETRY_ENABLED=false ../venv/bin/reflex run \
    --loglevel debug --frontend-port 3202 --backend-port 8202
#  drive: <driver-venv>/python drive_minimal_a2.py http://localhost:3202 out.png

# FINDING-023 e2e: pristine copy of reflex-enterprise/demos/flow (UNMODIFIED), ports 3203/8203,
#  CI=true; drive with ../ent_misc/drive_flow.py -> 11/11.
# mantine sweep: pristine demos/mantine, ports 3204/8204; ../ent_misc/drive_mantine.py -> 11/11.
# ag_grid formatters: copy ../ent_aggrid/demo_098 (the reflex>=0.9.8-fixed demo), install
#  faker==36.2.2 pandas==2.2.3 aiosqlite greenlet, alembic upgrade head, ports 3205/8205,
#  CI=1; drive: ../ent_aggrid/drive_aggrid.py <base> <shots> / /formatters
```

Env notes (same as a1 runs): CI=1 bypasses the rxe login gate in dev; do NOT override the
ambient NO_PROXY for `reflex run` (bun needs registry.npmjs.org whitelisted); use
NO_PROXY=localhost,127.0.0.1 only on driver/curl processes.

## Contents

- `probe_shims_a2.py` / `probe_shims_a2.out` — offline probes: dynamic.bundled_libraries,
  reflex.page.DECORATED_PAGES, LiteralLambdaVar.create bare (designed ValueError, no
  AttributeError) and after bundle_library. ALL PASS, each shim warns exactly once.
- `repro_dnd_can_drop_a2.out` — ent_map_dnd minimal trigger on a2: exit 0 (was exit 1 on a1).
- `drive_minimal_a2.py` — FINDING-021 driver (grid + lambda cell_renderer + tomato color +
  sort via row-index, since AG Grid reorders rows by transform, not DOM order).
- `logs/` — full `reflex run --loglevel debug` logs for all four servers.
- `shots/` — screenshots + report.json per driver run (min_lambda_a2.png matches the 0.9.8
  baseline ../ent_aggrid/shots_minimal/min_lambda_098.png, including the pre-existing
  quoted `"John"` cell text).
