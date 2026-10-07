# Cluster `reverify_db_install` — re-verify F-005/F-006/F-007/F-015 + Python 3.10 drop + install paths on 0.10.0a2

Ports: frontend 3380-3399, backend 8380-8399. Work dir: $SB/apps/reverify_db_install/. DEST: /home/user/reflex/prerelease_testing/2026-10-07/reverify_db_install/
Venv under test: $SB/envs/alpha2 (make your own venvs for install-path checks). Baselines: $SB/envs/alpha (0.10.0a1), $SB/envs/stable (0.9.12).

Read first: $SB/CAMPAIGN_STATE.md, /home/user/reflex/prerelease_testing/2026-10-06/FINDINGS.md FINDING-005/006/007/015, /home/user/reflex/prerelease_testing/2026-10-06/upgrades_a/NOTES.md VERIFICATION (sqlmodel),
/home/user/reflex/prerelease_testing/2026-10-06/pymatrix_install/NOTES.md. COPY scripts out before running.

## Re-verify
1. F-005 (#7462, cap lifted): `uv --no-config pip install --python <venv> --prerelease=allow 'reflex[db]==0.10.0a2' 'pydantic<2.14'`
   → which sqlmodel resolves (expect ≥0.0.45, currently 0.0.48)? Re-run /home/user/reflex/prerelease_testing/2026-10-06/upgrades_a/verification/sqlmodel-datetime/scripts/dt_matrix_probe.py
   and the dtapp flow; re-run /home/user/reflex/prerelease_testing/2026-10-06/pymatrix_install/apps/dbmig: the 0.9.12-generated migration with
   `sqlmodel.sql.sqltypes.UTCDateTime()` must now apply on a fresh db (`rm reflex.db && reflex db migrate`); the aware
   datetime round trip must match 0.9.12+0.0.47. ALSO the other direction the changelog does not mention: an app
   created under sqlmodel 0.0.44 (naive datetimes, migrations with plain `sa.DateTime()`) upgraded to alpha2 →
   `reflex db makemigrations` must not generate spurious revisions and naive inserts must keep working ("Support SQLModel UTC
   datetime migrations without downgrades" #7462 — read the PR via the GitHub MCP tool to learn what it actually does, then
   test exactly that). Note that #7462 has NO changelog fragment in the new train — confirm and record as a doc gap.
2. F-006 (#7464): seeded venv `pip install reflex==0.9.12` then `pip install -U --pre reflex==0.10.0a2` (and the uv and
   plain-pip variants from /home/user/reflex/prerelease_testing/2026-10-06/pymatrix_install/NOTES.md): all component packages must now move to the new train; run
   /home/user/reflex/prerelease_testing/2026-10-06/pymatrix_install/apps/formapp + scripts/drive_form.py → the #7227 payload must be the fixed one. Also a no-`--pre`
   `pip install reflex==0.10.0a2`: what resolves now that floors are pre-release pins? (Expect pip to accept the explicit
   pre-release floors; record the exact graph.) And `uv pip install reflex==0.10.0a2` without --prerelease=allow.
3. Python 3.10 drop (#7449): `uv venv --python 3.10` + `uv pip install reflex==0.10.0a2` must be refused with a clear
   requires-python message (not a confusing resolution error); pip as well. 3.11 must work: init + run + drive a small app
   on 3.11 (dev + prod). 3.14 quick smoke.
4. F-007: /home/user/reflex/prerelease_testing/2026-10-06/pymatrix_install/scripts/npm_sigterm_repro.sh on alpha2 (npm and bun) — unchanged? F-015 duplicate notice —
   unchanged? #7210 node check still works (fake node 18)? `reflex db *` without the db extra (#7259) still clean?
5. AppHarness (#7359): /home/user/reflex/prerelease_testing/2026-10-06/pymatrix_install/harness-style test — two apps sequentially where the FIRST app defines a
   state in a second module (and one using `rx.dynamic`); the second app must start cleanly (this is the new fix).
6. hosting-cli 0.2.0a1 + build-sdk 0.1.0a1 smoke: `reflex cloud --help`, `reflex cloud apps list --json` with no token
   non-interactively (expect exit 1 with the token message), `reflex --version`; confirm `reflex-hosting-cli 0.1.73a1` is
   excluded by reflex's metadata (`!= 0.1.73a1`) and what happens to a venv that already has 0.1.73a1 on upgrade.
Copy artifacts to DEST as you go.
