# Item `a3_class_state` — N-005, N-039, N-008, N-006, N-040, N-004 on reflex 0.10.0a3 + regressions from #7495 / #7494

Status: **Phase A (positive controls + baselines on 0.10.0a2 / 0.9.12) in progress; a3 not yet published.**
Everything installs from PyPI; nothing runs from the checkouts; every probe asserts the venv it imported reflex from.

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_class_state            # work dir (this directory's content is a copy of it, minus .web/venvs/raw logs)
P=/home/user/reflex/prerelease_testing/2026-10-07   # the a2 pass (original repros, read-only)
export REFLEX_TELEMETRY_ENABLED=false
```
Ports: frontend 3100-3119, backend 8100-8119, redis 8109 (`bin/start_app.sh` refuses anything else).

## Setup (Phase A)
Original repros copied UNCHANGED into `$W/orig/` (not mirrored into DEST: they live under `$P`):
```bash
mkdir -p $W/orig && cd $W/orig
mkdir -p rc_scripts && cp -r $P/reverify_core/scripts/. rc_scripts/
cp -r $P/reverify_core/verification/n005-storage-assign n005; cp -r $P/reverify_core/verification/n004-schema-rollback n004
mkdir -p tp_min && cp -r $P/thirdparty_a2/pytest_probe/. tp_min/
mkdir -p tpv && cp -r $P/thirdparty_a2/verification/{run_all.sh,probes,reqs} tpv/
mkdir -p hyd && cp $P/reverify_hydration/probes/cs_storage_default_probe.py hyd/ && cp -r $P/reverify_hydration/src/csbox hyd/csbox
mkdir -p core && cp -r $P/reverify_core/{core_a2,drivers,bin} core/
```
Own venvs (PyPI only, exact pins of the a2 pass + pytest 9 + pytest-mock):
```bash
cd $SB && for n in a2 s0912; do uv --no-config venv --python 3.12 $SB/envs/a3_class_state-$n &&
  uv --no-config pip install --python $SB/envs/a3_class_state-$n/bin/python --prerelease=allow -r $W/orig/tpv/reqs/$n.all.txt; done
```
Shared read-only venvs used: `alpha2` (0.10.0a2), `stable` (0.9.12), `driver` (playwright).

## Runners (`bin/`)
| script | what |
|---|---|
| `bin/py_orig.sh <venv>` | ORIGINAL Python repros, unchanged: derive_f_dunder (N-008), derive_e_format (N-006), derive_g_assign / derive_i_storage_legacy / storage_assign_matrix / cs_storage_default_probe (N-005), derive_a/b/b_reset/workarounds (context), dev+prod → `logs/py/<venv>/` |
| `bin/tpv_run.sh <outdir> <label>=<venv>...` | ORIGINAL N-039/N-040 verifier probes (t1_*, t2_*, test_min*.py, explorer pytest files) → `logs/tpv/` |
| `bin/compare_t.py <outdir> <label>...` | side-by-side t1 per-mechanism counts + per-cell table, t2 totals |
| `bin/schema_matrix.sh <out> <venv>...` | ORIGINAL derive_h_schema.py save/load matrix (defaults 0/5) + `probes/pickle_keys.py` (reflex-free dump of each pickle's keys) |
| `probes/adv7495.py` | NEW adversarial #7495/#7494 cases (needs pytest venv): `EXPECT_VENV=<v> $SB/envs/<v>/bin/python -I adv7495.py` → `logs/adv/adv7495.<label>.txt` |
| `probes/guard7495.py` | NEW dev-guard cases (N-008 follow-up), `REFLEX_ENV_MODE=dev|prod` → `logs/adv/guard7495.<venv>.<mode>.txt` |
| `bin/start_app.sh`, `stop_app.sh`, `wait_up.sh`, `ports.py`, `sync_dest.sh` | server helpers (setsid + pidfile in `$W/pids`), copy to DEST |

## Phase A results (positive controls on 0.10.0a2, baselines on 0.9.12)
All positive controls reproduce on a2 exactly as reported in the a2 pass, so the harness is sound:
- N-005 (`logs/py/alpha2/storage_assign_matrix.txt`): str-annotated plain value / plain-returning factory → `is_client_storage=False`,
  compiled=None (all 3 storage types); storage-annotated plain value → `TypeError: Invalid default`. `cs_storage_default_probe`: plain
  → `is_client_storage=False`. 0.9.12: assignment ignored, storage kept.
- N-008 (`logs/py/alpha2/derive_f_dunder.dev.txt`): `d._sneaky__name = 1 -> 'accepted'` on a2; 0.9.12 raises (dev AND prod on 0.9.12).
- N-006 (`logs/py/alpha2/derive_e_format.txt`): message "... Use a regular state var instead." (no default_value()/ClassVar).
- N-039 (`logs/tpv/`): `test_min.py` a2 `1 failed, 1 passed, 1 error` / 0.9.12 `2 passed`; t1 matrix a2 monkeypatch 15/15/15,
  mock 15/15/15, getattr-restore 15/15/15, value-restore 1/1/15, delattr 1/0/0; `test_t1_pytest.py` a2 `8 failed, 14 passed, 6 errors`,
  0.9.12 `9 failed, 13 passed` (no errors; patch invisible).
- N-040 (`logs/tpv/t2_*`): a2 raises 179/255, user code ran in 42; 0.9.12 0/0.
- N-004 (`logs/schema_matrix.phaseA.txt`): a2-saved → 0.9.12 `StateSchemaMismatchError` (d0 and d5); a2-saved pickle carries the
  `_PREVIOUS_RELEASE_PICKLE_KEYS` entries (`dirty_vars`, `dirty_substates`, `_backend_vars` all empty); schema hash a2 `bbd147dc...`,
  0.9.12 `fae0a0e8...` (legacy, includes defaults). No `_replaced_defaults` anywhere.
- Adversarial baselines: `logs/adv/adv7495.{a2,s0912}.txt`, `logs/adv/guard7495.{alpha2,stable}.{dev,prod}.txt`.
