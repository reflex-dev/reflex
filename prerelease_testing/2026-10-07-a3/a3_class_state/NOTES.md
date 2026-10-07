# Item `a3_class_state` — N-005, N-039, N-008, N-006, N-040, N-004 on reflex 0.10.0a3 + regressions from #7495 / #7494

Status: **done** (Phase A positive controls on 0.10.0a2 + 0.9.12 baselines; Phase B on 0.10.0a3, Python 3.11-3.14, dev and prod+redis e2e).
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

## Phase B (a3 published; shared `$SB/envs/a3` = reflex 0.10.0a3 / reflex-base 0.10.0a3, sqlalchemy 2.1.4, greenlet 3.5.6)
Published sources verified identical to `555b667c1` (`reflex_base/vars/base.py` md5 b123b233..., `reflex/state.py` 192fd44c...).
Own a3 venvs: `bin/build_a3_venvs.sh` → `a3_class_state-a3` (3.12), `-a3-py311`, `-a3-py313`, `-a3-py314`, each
`'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' pytest pytest-mock` (freezes in `logs/venv/freeze-*.txt`).

### Python level on a3 (commands)
```bash
cd $W && bin/py_orig.sh a3
bin/tpv_run.sh $W/logs/tpv a3=a3_class_state-a3 a3py311=a3_class_state-a3-py311 a3py313=a3_class_state-a3-py313 a3py314=a3_class_state-a3-py314
$SB/envs/driver/bin/python -I bin/compare_t.py logs/tpv a2 s0912 a3 a3py311 a3py313 a3py314 > logs/tpv/compare_all.txt
cd probes && EXPECT_VENV=a3_class_state-a3 $SB/envs/a3_class_state-a3/bin/python -I adv7495.py > ../logs/adv/adv7495.a3.txt
for m in dev prod; do REFLEX_ENV_MODE=$m EXPECT_VENV=a3 $SB/envs/a3/bin/python -I guard7495.py > ../logs/adv/guard7495.a3.$m.txt; done
cd $W && bin/schema_matrix.sh logs/schema_matrix.phaseB.txt a3 alpha2 stable
bin/disk_matrix.sh logs/disk_matrix.txt a3 alpha2 stable          # StateManagerDisk, shared REFLEX_STATES_WORKDIR, writer x reader
cd orig/rc_scripts/schema && SCHEMA_DEFAULT=0 $SB/envs/a3/bin/python -I $W/probes/upgrade_pickle.py a3 $W/out/schema/saved-{stable,alpha2}.bin
```
### Python level on a3 (results)
- **N-005 fixed** (`logs/py/a3/storage_assign_matrix.txt`): every str-annotated plain value / plain-returning factory keeps
  `is_client_storage=True` and the declared name+options (all 3 storage types); storage-annotated plain values are now ACCEPTED and
  kept (a2 raised TypeError). `cs_storage_default_probe`: plain → LocalStorage `box_pref`. derive_g_assign: `ls_plain`, `ls_fac_plain`,
  `ck` stay storage, cookie compiled with `maxAge 3600`. derive_i_storage_legacy: newstyle stays storage.
- **N-039 fixed** on 3.11/3.12/3.13/3.14 (`logs/tpv/compare_all.txt`): monkeypatch/mock 0 errors/0 leaks/15 visible of 15; getattr
  restore 0/0/15; delattr 0/0/0; `test_min.py` 2 passed; `test_t1_pytest.py` 22 passed; explorer files 10/10 and 5/6 (the one failure
  is `test_monkeypatch_setattr_mock`, an N-040 Mock-is-called rejection, same on a2); blast radius: nothing leaks.
- **N-008 fixed** (`logs/py/a3/derive_f_dunder.dev.txt`, `logs/adv/guard7495.a3.dev.txt`): `_sneaky__name` raises in dev; own/mixin/
  base/`_Under`/`__Dunder`/ComponentState-template/local(+renamed) mangled names accepted; a non-state helper's mangled name and an
  unrelated `_Other__x` now raise (as on 0.9.12); prod accepts everything (no guard in prod since a1).
- **N-006 partially fixed** (`logs/py/a3/derive_e_format.txt`): the BackendVarFormatError text now names `S._size.default_value()`,
  `ClassVar[...]` and a regular state var; the silent paths (`str(S._x)+"px"`, `"%s" % S._x`, `f"{S._x!s}"` embed
  `Field(default=16, ...)`) and `rx.box(id=S._label)` → `TypeError: expected string or bytes-like object, got 'Field'` are unchanged.
- **N-040 unchanged** (t2 totals a3 = a2: raises 179/255, user code ran in 42); now documented in base_vars.md (#7496 warning box).
- **N-004 as documented**: schema hash a3 == a2 (`bbd147dc...`); a3↔a2 load both ways; 0.9.12→a3 loads (same default);
  a3→0.9.12 `StateSchemaMismatchError` (Redis/pickle) / silent fresh state (disk); a3 pickle = only field values (no dirty_vars/
  dirty_substates/_backend_vars, no `_replaced_defaults`); a3 loading 0.9.12/a2 pickles drops their stale keys, dirty sets clean,
  re-serializes in the new format (`logs/upgrade_pickle.a3.txt`). Disk store (`logs/disk_matrix.txt`): a3→a3, a3→a2, a2→a3,
  0.9.12→a3 keep the session; a3→0.9.12 and a2→0.9.12 start fresh and the 0.9.12 write then replaces the 0.10 session.

### Adversarial #7495 probes on a3 (`logs/adv/adv7495.a3.txt` vs `.a2.txt` / `.s0912.txt`; also `-py311`, `-py314`)
| case | a3 | a2 | 0.9.12 |
|---|---|---|---|
| `del S.x` with nothing assigned | no-op, descriptor kept, instances fine | descriptor DELETED, instances `AttributeError` | attribute deleted, instances read default |
| assign 10, `del` twice | 10 → 0 → 0 | AttributeError | assignment ignored |
| `S.count = 10; S.count = S.count` | silently **undoes** to 0 (documented "assigning the Var back undoes") | TypeError | ignored |
| 20 assignments then 21 restores / 20 nested monkeypatches | stops at 4 (16-entry limit, documented) | TypeError | ignored |
| config 10 + 17 sequential patch round trips | 10, depth 1 | TypeError, leaks 116 | ignored |
| config 10 + rejected monkeypatch (wrong type / Var / Field / raising factory) | 10 (pytest 9 records the undo only after a successful setattr) | 10 | ignored |
| config 10 + rejected `mock.patch.object(..., Other.y)` (Var) | **0 — config lost** | 10 | ignored |
| config 10 + rejected `mock.patch.object(..., 'bad')` | 10 | 10 | ignored |
| patch 99, code assigns 77, undo | **99 leaks** | 77 + TypeError | 0 |
| config 10 + `monkeypatch.delattr` | during 0, after **0 (config lost)** | AttributeError during, 10 after | 0 |
| non-LIFO `mock.patch` start/stop | ends at original 0 (better than plain Python's 1) | TypeError | ignored |
| parent via child / grandchild / mixin / shadowing child / ComponentState instance | all restore; mixin patch reaches only states created during it (documented) | TypeError / AttributeError at undo, leaks | ignored |
| `reset()` after assignment / after restore | 10,[7] / 0,[1] | 10,[7] / AttributeError | ignored |
| storage factory calls at assignment (declared, assigned, both) | exactly 1 each, then the value is the default | n/a | ignored |
| storage options after plain assignment (Cookie max_age/path/same_site/secure, LocalStorage sync, SessionStorage) | kept, type preserved | dropped (plain str) | ignored |
| `Optional[str]` storage `= None` / `Union[str,int]` `= 5` | **storage dropped silently** (compiled entry None) | same | kept |
| pickle after assignment | `__getstate__` = field values only; no `_replaced_defaults`; schema unchanged | carries dirty_vars/_backend_vars | — |
| 8 threads assign/restore | no error, but final default corrupted (stale patched value/factory) | 12000 TypeErrors + corrupted | ignored |
| app module reloaded 20× (each assigns 10) | 10, bounded depth, patch/undo fine | TypeError on undo | ignored |
| declared non-storage `default_factory`, assign plain str | factory **called** at assignment; raising factory → raw RuntimeError | accepted, not called | ignored |
Pytest form of the leaks: `probes/undo_edge/test_undo_edge.py` (a3: 4 failed/4 passed; a2: 1 failed + 1 error; `logs/adv/test_undo_edge.txt`).

### E2E on a3 (Chromium via Playwright, $SB/envs/driver; one server at a time; redis on 8109)
```bash
cp -r $W/orig/core/core_a2 $W/run/core-a3 && PIDTAG=srv bin/start_app.sh a3 $W/run/core-a3 3101 8101 $W/run/logs/core-a3-dev.raw.log --loglevel debug
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python orig/core/drivers/drive_core.py http://localhost:3101 out/e2e core-a3-dev home,cs,storage,dunder
setsid redis-server --port 8109 --save '' --appendonly no &
CORE_API_URL=http://localhost:3104 REFLEX_REDIS_URL=redis://localhost:8109 PIDTAG=srv bin/start_app.sh a3 $W/run/core-a3-prod 3104 3104 <log> --env prod --loglevel debug
#   (wait on http://localhost:3104/ — /storage answers 307 in prod; then the same drive_core.py with label core-a3-prod-redis)
# n005 app: cp -r orig/n005/app run/stor-a3; dev 3102/8102; prod STOR_API_URL=http://localhost:3105 ... 3105 3105; driver orig/n005/drivers/drive_stor.py <base> out/e2e/stor-a3-*.json
# csbox: cp -r orig/hyd/csbox run/csbox-<v>; RVH_VENV=<v> ... 3103/8103 (dev) or REFLEX_API_URL=http://localhost:3106 ... 3106 3106 (prod+redis); driver orig/hyd/csbox_check.py
# extra app: cp -r apps/clse2e run/clse2e-<v>; dev 3108/8108; driver bin/drive_clse2e.py <base> out/e2e/clse2e-<v>-dev.json
# fleet (N-004): for v in stable alpha2 a3; cp -r orig/n004/fleet_app run/fleet/fleet_$v; redis-cli -p 8109 flushall;
#   MODE=new bin/fleet_phase.sh stable "1:stable(new)"; bin/fleet_phase.sh a3 "2:stable->a3(forward)"; ... (see logs/fleet/chain_summary.txt)
```
| check | a3 dev | a3 prod+redis (9 granian workers) | a2 dev (control) |
|---|---|---|---|
| core_a2 `/storage`: `ls_plain_key`, `lscs_key`, cookie `ck_key` written, new tab restores | **pass** | **pass** | fail (none written) |
| core_a2 `/storage` reset writes assigned defaults back; fresh browser writes nothing on first load | pass | pass | — |
| core_a2 `/` F-004, `/cs` per-instance defaults + `type(self).count=77; reset()`, EditableText, `/dunder` | pass (identical to a2) | pass; tab2 count_b 20 in prod (runtime assignment is per worker, now documented) | — |
| n005 app: 8/8 persisted in a new tab | **pass** | **pass** | 4/8 |
| csbox: `plain` instance persists | pass; **anomaly**: `none` and `plain` share `box_pref`, reload shows the other's value (a3_class_state-9) | same | plain not persisted; 0.9.12 all three share the key |
| clse2e: LocalStorage(sync=True) syncs across tabs after plain assignment; cookie keeps SameSite=Strict/max_age; storage-annotated var accepts a plain value and persists; SessionStorage kept | pass | — | sync/cookie/session NOT stored; annotated var TypeError at import |
| clse2e: `Optional[str]` storage assigned None | **fail** (k_opt never written) — a3_class_state-8 | — | same |
| N-004 fleet chain (prod, one Redis) | 0.9.12→a3 kept; a3→a3 kept; **a3→0.9.12 fresh** (no traceback, nothing logged); 0.9.12→a3 kept; a3→a2 kept; a2→a3 kept; a3 d5→d7 kept; fleet-state schema hash identical on a2 and a3 (`1d9811b8...`) | | |
Console: only benign lines (vite, React DevTools, HydrateFallback, "Disconnect websocket on page navigation/pagehide" — same on a2) and the
prod `/favicon.ico` 404. Server logs: the known #7499 `Expected field 'St.ls_declared_fac' / 'St.ann' to receive type LocalStorage` lines
(same count on a2), no tracebacks. `[ERROR] Unexpected exit from worker-1` appears only when my stop script SIGTERMs the process group.

## Findings written (board/findings-inbox/)
a3_class_state-1 N-005 fixed · -2 N-039 fixed · -3 N-008 fixed · -4 N-006 changed (message fixed, silent paths remain) ·
-5 N-004 behaves as documented · -6 N-040 unchanged (documented) · -7 NEW low: undo-stack restore loses/leaks defaults in 4 patch
patterns (regression vs a2) · -8 NEW low: None/non-str storage assignment still drops storage · -9 NEW low (docs): ComponentState
named storage shares one browser key · -10 NEW low: concurrent assign/restore not thread-safe.

## Not covered
- A real AppHarness run reusing one state module across two apps (covered only by the Python-level module-reload case).
- Disk store across real server restarts (`reflex run` wipes `.states` at start; covered at Python level with StateManagerDisk).
- clse2e in prod (storage options are compiled the same way; core_a2/n005/csbox ran in prod+redis).
