# Cluster `reverify_db_install`: F-005/006/007/015 + Python 3.10 drop + install paths + AppHarness + hosting-cli on 0.10.0a2

Everything installs from PyPI (default index). No checkout was installed, no python ran from a checkout.
Venvs are mine (`$SB/envs/rdi-*`); the shared `alpha2` / `alpha` (0.10.0a1) / `stable` (0.9.12) / `driver` venvs were
used read-only for comparison. Date of the runs: 2026-10-07 (06:25-07:15 UTC). Every reflex command ran with
`REFLEX_TELEMETRY_ENABLED=false`; local HTTP clients ran with `NO_PROXY=localhost,127.0.0.1` (never exported to servers).

```
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/reverify_db_install      # work dir; the repo copy is DEST (this directory)
DEST=/home/user/reflex/prerelease_testing/2026-10-07/reverify_db_install
E=$SB/envs/rdi                      # my venv prefix: $E-<name>
```
Ports used: 3380-3390 / 8380-8390 only (one server at a time). All servers, browsers and orphaned node processes were
killed (checked with `lsof -iTCP -sTCP:LISTEN` and `pgrep`; `ss` is not installed). Resolved graphs: `freeze/*.txt`.
Tooling: uv 0.11.32, pip 26.2.1, Node 22.22.0, bun 1.4.2, Playwright 1.63 + `/opt/pw-browsers/chromium`.
`scripts/startsrv.sh`, `scripts/stopsrv.sh` start/stop `reflex run` detached and wait up to 6 min for the frontend;
`scripts/sync_dest.sh` copies artifacts to the repo with `tar` (no rsync here).

## Headline results

| # | Result | State |
|---|--------|-------|
| 1 | **NEW, HIGH.** A fresh `reflex[db]==0.10.0a2` install resolves **SQLAlchemy 2.1.3 without greenlet** (sqlmodel 0.0.48 widened `SQLAlchemy<2.1.0` to `<2.2.0`; SQLAlchemy 2.1 made greenlet an extra). `reflex/model.py:69` does `import sqlalchemy.ext.asyncio` at import time, so `class X(rx.Model, table=True)`, `rx.session()` and **every `reflex db *` command crash with `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed`**. Fresh `reflex[db]==0.9.12` fails identically today; a1's `sqlmodel<0.0.45` cap hid it. Workarounds: `pip install greenlet` (or `sqlalchemy[asyncio]`) or `sqlalchemy<2.1`. | new, see ISSUES |
| 2 | F-005 (#7462, sqlmodel cap lifted): resolves sqlmodel **0.0.48**; datetime round trip, dtapp flow and the 0.9.12-generated `UTCDateTime()` migration on a fresh DB all match 0.9.12 + sqlmodel 0.0.47. | **fixed** (once greenlet is present, see 1) |
| 3 | F-005 reverse direction (naive-datetime app made under sqlmodel 0.0.44): in-place `pip install [-U]` keeps 0.0.44 and everything keeps working; `uv pip install -U` moves to 0.0.48 and naive writes are rejected / reads become aware (upstream sqlmodel >=0.0.45 behaviour). `makemigrations` creates no spurious revision in either case. The documented `sa_type=DateTime(timezone=False)` / `NaiveDatetime` recipes restore the old behaviour. **#7462 has no changelog fragment** (confirmed). | changed / doc gap |
| 4 | F-006 (#7464, sibling floors): every in-place upgrade variant (pip -U --pre, pip -U, plain pip, uv --prerelease=allow with and without -U / --upgrade-package) moves **all 13 component packages** to the new train; `formapp` submits the fixed #7227 payload; plain `pip install reflex==0.10.0a2` (no `--pre`) now resolves the full train. uv without `--prerelease=allow` still refuses (clear hint), now even with explicit `reflex`+`reflex-base` pins. | **fixed** |
| 5 | Python 3.10 drop (#7449): uv and pip both refuse cleanly with the requires-python reason; 3.11 and 3.14 init/run (dev + prod) pass 14/14 checks each. | pass |
| 6 | F-007: `reflex run` under npm still ignores SIGTERM without a TTY (3/3 on a2, plus a1; bun exits cleanly). | **still broken** |
| 7 | F-015: the "Preferring npm" notice is still printed twice. | **still broken** (unchanged) |
| 8 | #7210 node check (fake node 18.0.0 / 22.21.0) and #7259 (`reflex db *` without the extra) still clean. | pass |
| 9 | AppHarness #7359: second app after a multi-module first app (with `rx.dynamic`) now starts cleanly (a1 control reproduces `KeyError`). Restarting the SAME multi-module app in one process is still broken (the PR itself says so). | fixed / known limitation |
| 10 | hosting-cli 0.2.0a1 + build-sdk 0.1.0a1 smoke; `0.1.73a1` is excluded by metadata and replaced on upgrade. | pass |

## 1. NEW: fresh `reflex[db]` has no greenlet (SQLAlchemy 2.1)

```
uv --no-config venv --python 3.12 $E-uvdb312
uv --no-config pip install --python $E-uvdb312/bin/python --prerelease=allow 'reflex[db]==0.10.0a2' 'pydantic<2.14'   # logs/1a-*.log, freeze/1a-*.txt
uv --no-config venv --python 3.12 $E-stabledb-fresh
uv --no-config pip install --python $E-stabledb-fresh/bin/python 'reflex[db]==0.9.12'
for v in uvdb312 stabledb-fresh; do $E-$v/bin/python -I $DEST/scripts/greenlet_probe.py envs/rdi-$v; done
```
| venv | sqlalchemy | greenlet | `class M(rx.Model, table=True)` |
|---|---|---|---|
| fresh `reflex[db]==0.10.0a2` (uv, and pip: `freeze/10-pip-db.txt`) | **2.1.3** | **not installed** | **ImportError** |
| fresh `reflex[db]==0.9.12` (today) | 2.1.3 | not installed | **ImportError** |
| shared `$SB/envs/stable` (resolved earlier) | 2.0.54 | 3.5.6 | ok |
| shared `$SB/envs/alpha` (0.10.0a1, sqlmodel 0.0.44) | 2.0.54 | 3.5.6 | ok |
| shared `$SB/envs/alpha2` (**this is the venv the campaign shares**) | 2.1.3 | **not installed** | **ImportError** |
| `reflex[db]==0.10.0a2` + `sqlalchemy[asyncio]` (`$E-a2db-gl`) | 2.1.3 | 3.5.6 | ok |
| `reflex[db]==0.10.0a2` + `sqlalchemy<2.1` (`$E-a2db-sa20`) | 2.0.54 | 3.5.6 | ok |

Why: PyPI times: SQLAlchemy 2.1.0 2026-09-24, 2.1.3 2026-10-03; sqlmodel 0.0.47 (`SQLAlchemy<2.1.0,>=2.0.14`) 2026-09-23,
**sqlmodel 0.0.48 (`SQLAlchemy<2.2.0,>=2.0.14`) 2026-10-06T21:44Z**; reflex 0.10.0a2 2026-10-07T05:38Z.
SQLAlchemy 2.1 METADATA: `Provides-Extra: asyncio` / `greenlet>=1; extra == "asyncio"` (no unconditional greenlet).
`reflex-0.10.0a2.dist-info/METADATA`: `db` extra = alembic, pydantic, sqlmodel only. `reflex/model.py:66-70`
(`if find_spec("sqlalchemy"): import sqlalchemy.ext.asyncio`) runs the moment `reflex.model` is imported, even for
apps that never use an async engine. In-place upgraders keep greenlet from the SQLAlchemy 2.0 install, so only
fresh resolutions (new venv, Docker build, CI, uv project lock, reflex-local-auth users, whose `reflex[db]>=0.8.1`
requirement also resolves to 2.1.3) hit it.

End-to-end: `dtapp` (`rx.Model` with `created_at: datetime`) on `$E-uvdb312`:
`reflex run` exits 1 with the traceback ending in the ImportError (`logs/15-dtapp-a2nogreenlet-run.log`);
`reflex db migrate|makemigrations|status` all print the same traceback (`logs/11-greenlet-reflex-db-cli.log`).
Same result on the 3.11 and 3.14 venvs and on a pip-built venv (`logs/36-greenlet-probe-other-pythons.txt`).
With greenlet present everything below works on SQLAlchemy 2.1.3, including `rx.asession()` with aiosqlite
(`logs/33-async-session-sqlalchemy21.txt`).
Fix directions (not applied): put `greenlet` (or `sqlalchemy[asyncio]`) in the `db` extra, import
`sqlalchemy.ext.asyncio` lazily in `reflex.model`, or cap `SQLAlchemy<2.1` until verified.

## 2. F-005, forward: sqlmodel cap lifted (#7462)

PR #7462 (read via the GitHub MCP): removes `<0.0.45` from the `db` extra, bumps `uv.lock` to sqlmodel 0.0.47, adds
`docs/database/tables.md` "Datetimes and SQLModel upgrades", edits the old `+refresh-dependencies.misc.md` fragment down to
"Allow wrapt 2.4 and 2.5.", and adds two tests. It adds **no fragment of its own**: the published
`CHANGELOG.md` v0.10.0a2 has no sqlmodel/datetime/#7462 line (checked on `origin/r/pre-2026.10.06-37579583012`; only the
wrapt entry referencing #7424), so the cap removal and the UTC-datetime consequences are not in the release notes.

Resolution (`logs/1a-*`, `freeze/1a-*`, `freeze/10-*`, `logs/31-uv-compile-sqlmodel.txt`):
- `uv pip install --prerelease=allow 'reflex[db]==0.10.0a2' 'pydantic<2.14'` and `pip install 'reflex[db]==0.10.0a2'` (no `--pre`):
  **sqlmodel 0.0.48**, SQLAlchemy 2.1.3, alembic 1.20.0, pydantic 2.13.5.
- `uv pip compile` with `sqlmodel>=0.0.45`: resolves (was unsatisfiable on a1). With `reflex-local-auth`: stays at
  reflex-local-auth **0.5.0** (a1 silently dropped to 0.4.0). `sqlmodel==0.0.44` / `==0.0.47` pins still resolve for opt-out.

Datetime matrix (`scripts/dt_matrix_probe.py`; three tables: SQLModel, `rx.Model` plain `datetime`, `rx.Model` with explicit
`DateTime(timezone=True)`; values aware 17:00Z, aware 19:00+02, naive 17:00; run on `$E-a2db-gl` = a2 + sqlmodel 0.0.48 + SQLAlchemy 2.1.3 + greenlet):
```
cd $W/run/dtm
P=$DEST/scripts/dt_matrix_probe.py
# A: 0.9.12 writes -> a2 reads+writes -> 0.9.12 re-reads;  B: reverse. alone: each by itself
$SB/envs/stable/bin/python -I $P /envs/stable/ $PWD/A.db write ; $E-a2db-gl/bin/python -I $P /envs/rdi-a2db-gl/ $PWD/A.db write ; $SB/envs/stable/bin/python -I $P /envs/stable/ $PWD/A.db read
```
`logs/9-dtmatrix-{A,B,alone-a2,alone-stable,alone}.txt`. Result: a2 alone is **line-for-line identical** to 0.9.12 + 0.0.47
(after stripping the version tags): plain `datetime` is `UTCDateTime()`; aware values (UTC and +02) are stored as UTC and read
back `+00:00`; naive writes and naive filters raise `StatementError ... must have timezone information`; the explicit
`DateTime(timezone=True)` table reads naive and accepts naive. Cross-version reads (A and B) agree in both directions.
SQLAlchemy 2.0.54 control (`$E-a2db-sa20`): same output. Reference a1 (sqlmodel 0.0.44): naive reads, offset dropped (`logs/9-dtmatrix-alone.txt`).
`scripts/dt_probe.py` (`logs/13-dt-probe-{a2,stable,a1}.txt`): a2 == 0.9.12 (UTC-aware, `+02:00` -> `10:00+00:00`, naive filter rejected); a1 differs.

Real app (`apps/dtapp`: `Post(rx.Model)`, `on_load` compares with `datetime.now(timezone.utc)`, Add aware / Add naive buttons;
Chromium in America/New_York; migration `alembic/versions/9b68327541da_.py` was generated by 0.9.12 and contains `sqlmodel.sql.sqltypes.UTCDateTime()`):
```
cp -r $DEST/apps/dtapp $W/run/dtapp-a2gl && cd $W/run/dtapp-a2gl && rm -f reflex.db
$E-a2db-gl/bin/reflex db migrate                                    # rc 0 (a1: AttributeError ... UTCDateTime)
$DEST/scripts/startsrv.sh $E-a2db-gl $PWD 3385 8385 $W/logs/14-dtapp-a2gl-run.log dev
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $DEST/scripts/drive_dtapp.py http://localhost:3385 $W/out/14-dtapp-a2gl a2gl
```
Result a2 and 0.9.12 are identical: on_load ok, Add aware ok (row `2026-10-07 06:36:35+00:00`, `rx.moment` shows `02:36 -04:00`),
**Add naive raises the toast `StatementError: ... Datetime values must have timezone information` and writes no row** (same on 0.9.12 + 0.0.47;
6 pass / 2 expected-fail checks on both; `logs/14-dtapp-*-driver.txt`, `out/14-dtapp-*`). No TypeError, no console errors.
`rm reflex.db && reflex db migrate` with the 0.9.12-generated migration: rc 0 on a2 (and on the SQLAlchemy 2.0 control; a1 rc 1). A migration generated by a2
(`reflex db init` in `run/dtapp-a2gen`) contains `UTCDateTime()`, replays on a fresh DB on a2 and 0.9.12, fails on a1; a second `makemigrations` adds no revision (`logs/35-a2-generated-migration.log`).
`apps/dbmig` (plain `sqlmodel.SQLModel` table, 0.9.12-generated migration): `rm reflex.db && reflex db migrate` rc 0, `status` shows head `ace2dea073f9`, `makemigrations` no spurious revision (`logs/12-dbmig-*.log`).

## 3. F-005, reverse: app made under sqlmodel 0.0.44 (naive datetimes), upgraded to 0.10.0a2

`apps/naiveapp`: `Event(rx.Model)` with plain `at: datetime`, handlers use `datetime.now()` and naive comparisons; project initialised
by `reflex[db]==0.9.11` + `sqlmodel==0.0.44` (SQLAlchemy 2.0.54, greenlet 3.5.6): migration has `sa.Column('at', sa.DateTime(), nullable=False)`,
two naive rows seeded (`out/17-naive/baseline-0.9.11-sm044.json`). Upgrade variants (`scripts/upgrade_sm044.sh`, `freeze/16-*`):

| upgrade command (from 0.9.11 + 0.0.44) | result |
|---|---|
| `pip install -U --pre 'reflex[db]==0.10.0a2'` / `pip install 'reflex[db]==0.10.0a2'` | reflex 0.10.0a2; **sqlmodel stays 0.0.44** (pip only-if-needed) |
| `uv pip install --prerelease=allow 'reflex[db]==0.10.0a2'` (no -U) | sqlmodel stays 0.0.44 |
| `uv pip install --prerelease=allow -U 'reflex[db]==0.10.0a2'` | **sqlmodel 0.0.44 -> 0.0.48, SQLAlchemy 2.0.54 -> 2.1.3**, pydantic -> 2.14.0b2 (prerelease=allow side effect); greenlet kept, so no ImportError |

`reflex db status|makemigrations|migrate` after upgrade (`logs/18-naive-*-dbcli.log`): rc 0 everywhere, **no new revision** (autogenerate runs with
`compare_type=False`), also on 0.0.48.
App behaviour (`scripts/drive_naive.py`, `out/17-naive/*.json`):
- pip-upgraded (0.0.44 kept): old rows load, naive Add works (4 rows), no toasts or console errors.
- uv `-U` (0.0.48): rows load but **display as `...+00:00`** (UTCDateTime attaches UTC to the stored wall-clock), `load` raises `TypeError: can't subtract
  offset-naive and offset-aware datetimes` (status stays `idle`, no ages), Add raises `StatementError ... must have timezone information` (`logs/19-naive-uvU-run.log`).
  This is sqlmodel >=0.0.45 behaviour that the a1 cap used to hide; #7462 documents it in `docs/database/tables.md` only.
- Recipes from that doc page on 0.0.48 (`out/17-naive/uvU-R1.json`, `uvU-R2.json`): `at: datetime = sqlmodel.Field(sa_type=DateTime(timezone=False))` and `at: NaiveDatetime`
  both restore naive reads/writes on the same DB file (4 rows, `recent` ages, no toasts); `makemigrations` after the model edit again creates no revision.

Rerun (baseline project + upgrade variants):
```
uv --no-config venv --python 3.12 $E-sm044 && uv --no-config pip install --python $E-sm044/bin/python 'reflex[db]==0.9.11' 'sqlmodel==0.0.44'
cp -r $DEST/apps/naiveapp $W/run/naive-seed && cd $W/run/naive-seed    # alembic/ was generated by 0.9.11 (reflex db init + makemigrations); then: $E-sm044/bin/reflex db migrate
$DEST/scripts/startsrv.sh $E-sm044 $PWD 3387 8387 $W/logs/17-naive-seed-run.log dev
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $DEST/scripts/drive_naive.py http://localhost:3387 $W/out/17-naive/baseline.json baseline 2    # seeds 2 naive rows
$DEST/scripts/stopsrv.sh envs/rdi-sm044 run/naive-seed    # 0.9.11 ignores SIGINT here: the script falls back to SIGKILL and kills the orphaned node
SB=$SB W=$W $DEST/scripts/upgrade_sm044.sh uvU uv --prerelease=allow -U 'reflex[db]==0.10.0a2'    # also: pipU (pip -U --pre), pipnoU (pip), uvnoU (uv, no -U)
# copy the seeded project (alembic/, naiveapp/, rxconfig.py, reflex.db) to $W/run/naive-uvU, run $SB/envs/rdi-sm044-uvU/bin/reflex db makemigrations, then start + drive_naive.py again
```

## 4. F-006 (#7464): component floors

`reflex-0.10.0a2` METADATA now requires `reflex-components-{code,core,gridjs,markdown,moment,plotly,radix,recharts}>=0.10.0a2`,
`-dataeditor/-react-player/-sonner>=0.10.0a1`, `-lucide>=1.1.0a1`, `reflex-hosting-cli!=0.1.73a1,>=0.2.0a1`, `reflex-base==0.10.0a2`.
Venv matrix: `scripts/install_matrix_upgrade.sh <label> <pip|uv> <args>` creates a seeded venv with `reflex==0.9.12` (components 0.9.x, hosting-cli 0.1.72),
runs the install, diffs the freezes (`freeze/up-*-{before,after}.txt`, `logs/3-upgrade-matrix-*.txt`):

| command (from 0.9.12) | rc | result |
|---|---|---|
| `pip install -U --pre reflex==0.10.0a2` | 0 | full train: all 13 components, hosting-cli 0.2.0a1, build-sdk 0.1.0a1 |
| `pip install -U reflex==0.10.0a2` (no --pre) | 0 | identical full train |
| `pip install reflex==0.10.0a2` (no -U, no --pre) | 0 | identical full train |
| `uv pip install --prerelease=allow reflex==0.10.0a2` | 0 | identical (also without -U) |
| `uv pip install --prerelease=allow -U reflex==0.10.0a2` / `--upgrade-package reflex` / `-U reflex` unpinned | 0 | identical (unpinned picks 0.10.0a2) |
| `uv pip install reflex==0.10.0a2` (no flag) | 1 | `No solution ... reflex-base==0.10.0a2 ... hint: ... pre-release marker ... try --prerelease=allow`; env untouched. Same as every alpha (pre-existing uv semantics) |
| `uv pip install reflex==0.10.0a2 reflex-base==0.10.0a2` (a1's "mixed graph" workaround) | 1 | now fails: `reflex-components-code>=0.10.0a2 ... pre-release markers`; there is no silent mixed graph any more (`logs/34-*`) |
| `pip install -U reflex` unpinned, no --pre | 0 | stays 0.9.12 (stable only), as expected |
Fresh venvs: `pip install reflex==0.10.0a2` (no --pre, `$E-pipnopre312`, `freeze/2b-pip-nopre.txt`) resolves the **full train** (pip accepts the pre-release floors; on a1
this resolved the mixed graph); `pip install 'reflex[db,pydantic]==0.10.0a2'` on 3.11 and 3.14 too (`freeze/6-py311.txt`, `6-py314.txt`).
Behavioural check (`apps/formapp` + `scripts/drive_form.py`, the in-place pip-upgraded venv `$E-up-pip-pre`, dev, 3380/8380):
```
cp -r $DEST/apps/formapp $W/run/formapp && cd $W/run/formapp
REFLEX_TELEMETRY_ENABLED=false $E-up-pip-pre/bin/reflex run --frontend-port 3380 --backend-port 8380
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $DEST/scripts/drive_form.py http://localhost:3380/
-> {"bool_input": true, "empty_input": "", "name_input": "foo"}      non-control ids submitted: none      (logs/4-formapp-upgraded-result.txt)
```
a1's in-place upgrade submitted `form_id`/`form_content_wrapper`/`submit` (10-06 `logs/1b-formapp-upgraded-result.txt`): fixed. SIGINT stops this a2 server in ~2 s.

## 5. Python 3.10 / 3.11 / 3.14 (#7449)

3.10 (`$E-py310`, `logs/5a-py310-uv.log`, `5b-py310-pip.log`):
- uv, with or without `--prerelease=allow`, for `reflex==0.10.0a2`, `reflex[db]==0.10.0a2` and `reflex-base==0.10.0a2`:
  `Because the current Python version (3.10.20) does not satisfy Python>=3.11,<4.0 and reflex==0.10.0a2 depends on Python>=3.11,<4.0 ... unsatisfiable`, rc 1. Clear.
- pip: `ERROR: Ignored the following versions that require a different python version: 0.10.0a2 Requires-Python <4.0,>=3.11` then
  `Could not find a version that satisfies the requirement reflex==0.10.0a2 (from versions: <every release>)` / `No matching distribution found`, rc 1.
  Clear on the cause (the version list is long, standard pip). Unpinned `pip install --pre reflex` / `uv pip install --prerelease=allow reflex` on 3.10
  silently falls back to 0.10.0a1 (the last alpha supporting 3.10); expected resolver behaviour.
- Metadata audit (`logs/32-requires-python-audit.txt`): all 16 installed reflex distributions (`reflex`, `reflex-base`, 11 components, hosting-cli, build-sdk) say `Requires-Python >=3.11`
  with classifiers 3.11-3.15.

3.11 (`$E-py311`, pip `reflex[db,pydantic]==0.10.0a2`) and 3.14 (`$E-py314`): `reflex --version` -> `0.10.0a2`, stdout clean, stderr empty;
`reflex init --template blank` rc 0 on both. App `apps/pyapp` (14 checks: optional/dict/dataclass/pydantic/Literal/Enum/datetime/Union/tuple/TypedDict vars, in-place mutation,
background task, ABC mixin, `from __future__ import annotations` state, client nav, reload, second tab; `scripts/drive_pyapp.py`):
```
cp -r $DEST/apps/pyapp $W/run/py311/pyapp && cd $W/run/py311/pyapp
$DEST/scripts/startsrv.sh $E-py311 $PWD 3381 8381 $W/logs/7-py311-dev-run.log dev          # PYTHONWARNINGS=default was set in the first runs
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $DEST/scripts/drive_pyapp.py http://localhost:3381 $W/out/7-py311-dev py311-dev 3.11
# prod: REFLEX_API_URL=http://localhost:3382 reflex run --env prod --frontend-port 3382 --backend-port 3382
```
3.11 dev 14/14 (console clean), 3.11 prod 14/14 (only the known-benign `/favicon.ico` 404), 3.14 dev 14/14 (clean), 3.14 prod 14/14 (favicon 404 only)
(`out/7-py311-*`, `out/8-py314-*`). Server logs only show the pre-existing `PydanticDeprecatedSince20: __fields__` lines from `reflex_base/utils/types.py`
under `PYTHONWARNINGS=default` (pydantic-model var) and the pre-existing SitemapPlugin "enabled by default" warning (also in the 0.9.12 logs).

## 6. F-007 / F-015 / #7210 / #7259

F-007 (`scripts/npm_sigterm_repro.sh <venv> <app_dir> <fp> <bp> <use_npm> <log>`):
```
$DEST/scripts/npm_sigterm_repro.sh $SB/envs/alpha2 $W/run/sigterm_a2_npm 3388 8388 1 $W/logs/21-sigterm-a2-npm.log
$DEST/scripts/npm_sigterm_repro.sh $SB/envs/alpha2 $W/run/sigterm_a2_bun 3389 8389 0 $W/logs/21-sigterm-a2-bun.log
```
a2 + npm, 3/3 runs (`logs/21-sigterm-a2-npm{,-run2,-run3}.log`): `RESULT: reflex CLI STILL RUNNING 30s after SIGTERM`; `npm run dev` is `<defunct>`, `node ... react-router dev --host`
re-parented to PID 1 and **still listens on the frontend port**; main thread `futex_do_wait`, reader thread `anon_pipe_read` (the orphan holds the stdout pipe).
a2 + bun: `RESULT: reflex CLI exited`, no listeners, `Info: Reflex app stopped.` Baselines in the same session: a1 + npm hangs (`logs/21-sigterm-a1-npm.log`), 0.9.12 + npm hangs identically (`logs/21-sigterm-stable-npm.log`).
Unchanged by this train (#7328's fix still only covers bun).

F-015: in `run/sigterm_a2_npm` (`reflex.lock/` has `package-lock.json` only), plain `reflex run` prints the
`Info: Preferring npm because reflex.lock/ has package-lock.json and no bun.lock. Run once with REFLEX_USE_NPM=0 ...` pair **twice**, right after "Compiling" (`logs/24-f015-plain-run.log`).
`_log_implicit_npm_notice` (`reflex/utils/js_runtimes.py:116`) is `functools.cache`d per path, so the two lines come from two processes (not traced). Unchanged.

#7210 (`apps/fakenode/{18.0.0,22.21.0}/node` shims that report the old version and otherwise exec the real node; `logs/22-fakenode-7210.log`): `reflex init` (REFLEX_USE_NPM=1) and `reflex run`
(REFLEX_USE_NPM=1) both exit 1 with `Reflex requires node version 22.22.0 or higher to run, but the detected version is 18.0.0` / `22.21.0`; no `package-lock.json`, no `node_modules`. Unchanged and correct.

#7259 (`logs/23-nodb-7259.log`, venv without the db extra, 3.12): `reflex db init|migrate|makemigrations|status` all print
`Database is not available. Please install the required packages: `pip install reflex[db]`.` and exit 1. 0.9.12 baseline: ImportError tracebacks (init, status), ModuleNotFoundError alembic (makemigrations),
"Database is not initialized" with exit 0 (migrate). Unchanged and correct.

## 7. AppHarness (#7359)

Venvs: `$E-harness-a2` = `reflex[testing]==0.10.0a2` + playwright 1.63 (`freeze/25-harness-a2.txt`); a1 control `$SB/envs/pymatrix_install-harness312`.
`scripts/harness_multimodule.py <venv-substr> <root> <out.json> <scenario>`; `AppHarness.create(root=...)` (no `app_source`) on a hand-written app whose
state lives in a SECOND module (`mm_one/states.py`, plus `mm_one/widgets.py` with `@rx.dynamic` for `dynamic*` scenarios); then a second app (`mm_two`, `app_source=` function) in the same process.
```
cd $W/run/harness && NO_PROXY=localhost,127.0.0.1 $E-harness-a2/bin/python $DEST/scripts/harness_multimodule.py /envs/rdi-harness-a2/ $PWD/a2-dynamic $W/out/26-harness/a2-dynamic.json dynamic
```
| scenario | a2 | a1 |
|---|---|---|
| `plain` (state in 2nd module) -> second app | pass | pass |
| `dynamic` (2nd-module state + `rx.dynamic`) -> second app | **pass**, `State._always_dirty_substates == []` after app one stops, app two roundtrip ok | **fails**: `State._always_dirty_substates == ['mm_one___states____widget_state']`, `[Reflex Backend Exception] KeyError: 'mm_one___states____widget_state'`, app two's click never updates |
| `dynamic-same` (app one again after app two) | app two ok; app one the second time **fails** (KeyError / frontend `Cannot read properties of undefined (reading '$$typeof')`) | not run |
| `plain-restart` / `dynamic-restart` (app one twice in a row) | **fails** both | `dynamic-restart` fails |
The a1 control proves the repro; a2 fixes the leak into the NEXT app. Restarting the same multi-module app in one process is still broken: `AppHarness._reload_state_module`
drops the states of every `<app>.*` module but cached submodules are not re-imported, so their states are never re-registered. PR #7359's description lists this as "Not changed ... also on main".
`logs/26-harness-*.log`, `out/26-harness/*.json`. The earlier two-single-module-apps test (`scripts/harness_test.py`, 21 checks on 10-06) was not re-run.

## 8. hosting-cli 0.2.0a1 / build-sdk 0.1.0a1 / 0.1.73a1

`logs/29-hostingcli-{alpha2,alpha,stable}.log` (same commands on each): `reflex --version` -> `0.10.0a2`; `reflex cloud --help` lists apps, config, create-token, gcp-standalone, project, providers, regions, scan, secrets, token, vmtypes, whoami
(identical to a1's hosting-cli 0.1.73a1); `reflex cloud apps list --json < /dev/null` and `reflex cloud apps list < /dev/null` with no token: **`Token is required for non-interactive mode.`, exit 1**;
`reflex login --help`, `reflex deploy --help`, `reflex logout` ok. 0.9.12 differs only by an extra "Unable to list deployments" line. `import reflex_build_sdk`, `import reflex_cli` ok (`logs/30-build-sdk-smoke.txt`);
hosting-cli 0.2.0a1 requires `reflex-build-sdk[httpx]!=0.1.1,<0.1.1.post,>=0.1.0a1`.
0.1.73a1 handling (`scripts/upgrade_hc073.sh`, env = the 10-06 a1 full-train freeze with hosting-cli 0.1.73a1 + build-sdk 0.0.5; `freeze/27-*`, `logs/27-*`):
`pip install -U reflex==0.10.0a2`, `pip install reflex==0.10.0a2` and `uv pip install --prerelease=allow reflex==0.10.0a2` all replace it with hosting-cli **0.2.0a1** (+ build-sdk 0.1.0a1), `pip check` clean.
`pip install reflex==0.10.0a2 reflex-hosting-cli==0.1.73a1` -> `ResolutionImpossible: The user requested reflex-hosting-cli==0.1.73a1; reflex 0.10.0a2 depends on reflex-hosting-cli!=0.1.73a1 and >=0.2.0a1`.
Forcing 0.1.73a1 onto an a2 env (`pip install --pre reflex-hosting-cli==0.1.73a1`): pip prints the dependency-conflict error text, installs it anyway, `pip check` reports it, and `reflex --version`, `reflex cloud --help`,
`reflex cloud apps list --json` (rc 1, token message) still behave normally (`logs/28-hc073-forced-on-a2.log`), so the exclusion is enforced at resolution time only.

## Benign / pre-existing observations
- `Database is not initialized, run [bold]reflex db init[/bold] first.` prints the raw rich markup (`[bold]`) when `reflex.model.get_engine()` is first used without alembic.ini: identical on 0.9.12 and a1.
- SitemapPlugin "enabled by default, but not explicitly added" warning on apps without `plugins=`: identical on 0.9.12.
- `reflex.Model` deprecation location points into `pydantic/_internal/_model_construction.py:156` (F-013, owned by `reverify_core`).
- 0.9.12 `reflex run` (and 0.9.11) does not stop on SIGINT without a TTY (needed SIGKILL + killing the orphaned node); a2 stops in ~2 s with bun.
- `reflex init` writes `AGENTS.md`/`CLAUDE.md` (excluded from the artifacts); init message still says "before running `uv run reflex run`".

## Not covered
- PostgreSQL / MySQL behaviour of the datetime change (10-06 covered PG for a1; a2 is the same sqlmodel as 0.9.12+0.0.47 on SQLite). Windows-specific paths.
- `reflex run` under Python 3.13; the mixed `pip` + `uv` project mode (`uv add`) was not re-run (resolution only via `uv pip compile`).
- The two-single-module-apps `harness_test.py` (21 checks) from 10-06 was not re-run; only the new multi-module scenarios.
- Root cause of F-015's double notice and of the npm hang were read from source/logs only, not traced with a debugger.
