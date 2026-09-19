# Cluster `dev_server_cli` — reflex 0.9.12a1 pre-release QA

Explorer-agent notes. Everything here was run against **packages installed from PyPI only**;
nothing was installed from the `/home/user/reflex` checkout, and no `python` was ever run with
the checkout as cwd (each app module starts with
`assert "/home/user/reflex" not in rx.__file__`).

Ports used: frontend 3380-3389, backend 8380-8389 (reserved range 3380-3399 / 8380-8399).
No redis was needed. All servers/browsers were killed; see **Cleanup** at the bottom.

## Environments

```
$SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
$SB/envs/shared   # 0.9.12a1 train  (prebuilt, read-only)
$SB/envs/prev     # 0.9.11.post1    (prebuilt, read-only)
$SB/envs/driver   # playwright 1.63; chromium at /opt/pw-browsers/chromium
```

`uv pip freeze --python $SB/envs/shared/bin/python | grep -i reflex` (the venv actually used):

```
reflex==0.9.12a1
reflex-base==0.9.12a1
reflex-components-code==0.9.6a1
reflex-components-core==0.9.10a1
reflex-components-dataeditor==0.9.3a1
reflex-components-gridjs==0.9.2a1
reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.4a1
reflex-components-moment==0.9.4
reflex-components-plotly==0.9.7a1
reflex-components-radix==0.9.10a1
reflex-components-react-player==0.9.2
reflex-components-recharts==0.9.4a1
reflex-components-sonner==0.9.4a1
reflex-hosting-cli==0.1.72
```

Baseline venv (`$SB/envs/prev`): `reflex==0.9.11.post1`, `reflex-base==0.9.11.post1`,
`reflex-components-core==0.9.9`, `-radix==0.9.9`, `-recharts==0.9.3`, `-sonner==0.9.3`,
`-code==0.9.5`, `-markdown==0.9.3`, `-plotly==0.9.6`, `-gridjs==0.9.1`, `-dataeditor==0.9.2`,
`reflex-hosting-cli==0.1.72`.

To rebuild either from scratch (run from a neutral dir, **never** from the checkout):

```bash
cd $SB
uv venv $SB/envs/mine --python 3.11
uv pip install --python $SB/envs/mine/bin/python --prerelease=allow \
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
  'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
  'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
  'reflex-components-sonner==0.9.4a1'
```

## Apps in this directory

| dir | what it is |
|---|---|
| `dsc/` | main probe app: `rx.State` + event chain + background task + `rx._x.client_state` + `@rx.memo` + `rx.ComponentState` + `rx.foreach` + `rx.cond` + 3 pages incl. a dynamic route. `rxconfig.py` imports a sibling `settings.py` (for #7075). A `modules_report` computed var renders the backend worker's pid / `len(sys.modules)` / RSS / which heavy modules are imported (for #7049). |
| `dsc_prev/` | byte-identical copy of `dsc/` run against 0.9.11.post1 for baselines |
| `hrapp/` | #7117 app: wraps a local npm package by directory (`@masenf/hello-react@../hello-react`) **and** by tarball (`@masenf/hello-react-tgz@../hello-react/masenf-hello-react-0.1.0.tgz`). `hello-react/` is the local package (a real React component rendering a `label` prop and its `children`). |
| `hrapp_prev/` | same app on 0.9.11.post1 (reproduces the truncation bug) |
| `nonode/` | blank app used for the node-less test (#7202) |

`scripts/` holds the drivers, `logs/` the server logs, `shots/` the screenshots + captured
browser-event JSON.

## Rerun commands

Everything below assumes `export SB=/tmp/.../scratchpad`, `export D=$SB/apps/dev_server_cli`,
`export PORTS_PY=$SB/bin/ports.py`, and `REFLEX_TELEMETRY_ENABLED=false`.
Playwright/curl need proxy bypass on the client side: prefix with
`NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1` (curl: `--noproxy '*'`).

```bash
# --- #6981 signals: launches reflex in its own process group, signals it, reports exit code
python3 $D/scripts/signal_test.py $SB/envs/shared $D/dsc      LABEL TERM proc  $D/logs 3380 8380
python3 $D/scripts/signal_test.py $SB/envs/shared $D/dsc      LABEL TERM group $D/logs 3380 8380
python3 $D/scripts/signal_test.py $SB/envs/prev   $D/dsc_prev LABEL TERM proc  $D/logs 3381 8381

# --- what the backend port does after a SIGTERM that did not stop the process
python3 $D/scripts/sigterm_port_probe.py $SB/envs/shared $D/dsc      3382 8382 new  $D/logs
python3 $D/scripts/sigterm_port_probe.py $SB/envs/prev   $D/dsc_prev 3383 8383 prev $D/logs

# --- #7089 nocompile marker + #7049 startup timing + #7193 JSON logs (backend-only)
PORTS_PY=$SB/bin/ports.py $D/scripts/backend_only_run.sh \
    $SB/envs/shared $D/dsc 8380 $D/logs/07089_new_backendonly.log --json --loglevel debug
# then a full run and check the page shows the edited heading:
cd $D/dsc && reflex run --frontend-port 3380 --backend-port 8380 --json --loglevel debug
$SB/envs/driver/bin/python $D/scripts/drive.py http://localhost:3380 $D/shots/nocompile_new

# --- #7114 backend port stays open across a hot reload (run while the dev server is up)
$SB/envs/driver/bin/python $D/scripts/ping_probe.py 8380 32 $D/logs/reload_probe_new.tsv
#   ...and while it runs, edit $D/dsc/dsc/dsc.py (change HEADING) to trigger the reload

# --- #7129 bun/npm lockfile switching
PORTS_PY=$SB/bin/ports.py $D/scripts/lockswitch.sh $SB/envs/shared $D/dsc A_npm 3386 8386 $D/logs 1  # npm
PORTS_PY=$SB/bin/ports.py $D/scripts/lockswitch.sh $SB/envs/shared $D/dsc B_bun 3386 8386 $D/logs    # bun

# --- #7117 local package specifiers
cd $D/hrapp      && reflex run --frontend-port 3384 --backend-port 8384   # 0.9.12a1 -> works
cd $D/hrapp_prev && $SB/envs/prev/bin/reflex run --frontend-port 3385 --backend-port 8385  # 0.9.11 -> fails
grep -o '"[^"]*masenf[^"]*": *"[^"]*"' .web/package.json

# --- #7202 node-less
STRIPPED=$(python3 -c "import os;print(':'.join(p for p in os.environ['PATH'].split(':') if p and not any(os.path.exists(os.path.join(p,b)) for b in ('node','npm','npx','bun'))))")
env PATH="$STRIPPED" HOME=$D/nonode_home reflex init --name nonode --template blank
cd $D/nonode && env PATH="$STRIPPED" HOME=$D/nonode_home reflex run --frontend-port 3389 --backend-port 8389
```

## Results per changelog item

### #6981 — SIGTERM exits cleanly  — PARTIAL PASS + one regression

The changelog line ("no longer reports *Starting frontend failed with exit code 143* and now
exits cleanly") holds **only when the signal reaches the whole process group**:

| case | version | exit code | time | survivors | ports freed |
|---|---|---|---|---|---|
| dev, SIGTERM to **process group** | 0.9.12a1 | **0** | 0.20 s | none | yes |
| dev, SIGTERM to **the pid only** | 0.9.12a1 | **never exits** (>30 s) | — | reflex + bun + node | **no** |
| dev, SIGTERM to **the pid only** | 0.9.11.post1 | **never exits** (>30 s) | — | reflex + bun + node | frontend port still bound |
| `--backend-only`, SIGTERM to pid | 0.9.12a1 | 0 | fast | none | yes |

No "exit code 143" line appeared in any 0.9.12a1 log. Evidence:
`logs/sigres_N1_new_dev_TERM_proc.json`, `logs/sigres_N2_new_dev_TERM_group.json`,
`logs/sigres_P1_prev_dev_TERM_proc.json`.

* **Pre-existing, both versions (NOT a regression):** a plain `kill <pid>` / `docker stop`
  (SIGTERM to PID 1 only, no group signal) does **not** stop `reflex run` in dev mode. The
  granian worker dies but the parent, bun and vite stay up forever.
* **New in 0.9.12a1 (regression):** after that stuck SIGTERM, the *backend port stays bound and
  accepts connections that are never answered*. 0.9.11.post1 released the port, so clients got
  an immediate `ECONNREFUSED`. See `logs/portprobe_new.json` vs `logs/portprobe_prev.json`:

  ```
  0.9.12a1 : before=200/0.01s   after_sigterm_8s = TIMEOUT_NO_REPLY_6s
  0.9.11   : before=200/0.00s   after_sigterm_8s = CONNECTION_REFUSED
  ```

  This is a side effect of #7114 moving the listening socket into the supervisor. Anything that
  health-checks the backend (load balancer, `docker stop` grace period, k8s readiness probe)
  now hangs where it used to fail fast.
* **Cosmetic anomaly:** the clean group-SIGTERM shutdown still logs
  `[ERROR] Unexpected exit from worker-1` at ERROR level before `Info: Reflex app stopped.`,
  on an entirely intentional shutdown (`logs/sig_N2_new_dev_TERM_group.log`).

### #7089 — backend-only run must not leave a compile-skip marker — PASS

`.web/nocompile` was absent before, during and after a `reflex run --backend-only`
(`DEV_RELOAD_MARKER` — a different file, `.web/.reflex_dev_backend_started` — is the one that
appears). End-to-end proof: the page source was edited between the two runs
(`HEADING = "dsc v4-nocompile"`), and after the backend-only run the subsequent full
`reflex run` served the **new** heading, i.e. the frontend was recompiled.
Evidence: `logs/07089_new_backendonly.log`, `shots/nocompile_new_1_index.png`,
`shots/nocompile_new_events.json` (`heading :: dsc v4-nocompile`, 0 console errors, 0 HTTP>=400).
Source confirms the fix in `reflex/utils/exec.py::run_backend` (`nocompile.unlink(missing_ok=True)`
when `frontend_present` is false).

### #7114 — backend port stays open across a hot reload — PASS

`/ping` probed at 20 Hz for 32 s while `dsc/dsc.py` was edited mid-window:
**623 requests, 0 refused, 0 errors, max latency 0.166 s** (`logs/reload_probe_new.txt`,
`logs/reload_probe_new.tsv`). The reload really happened inside the window — the JSON log shows
`Changes detected, reloading workers..` → `Stopping worker-1` → `Spawning worker-1 with PID: 2223`
(`logs/full_dev_json.log` L101-L160). An earlier 30 s run gave the same result
(584 requests, 0 refused — `logs/03_probe_new.txt`). A browser page held open across the reload
picked up the new heading and kept firing events (`shots/after_hot_reload.png`).

Caveat — see #6981 above and the handover item below: the same mechanism means a backend that
**cannot** come back leaves the port accepting-but-hanging instead of refusing.

### #7117 — local package specifiers not truncated — PASS (confirmed fix, baseline reproduces the bug)

`.web/package.json` on **0.9.12a1**:

```
"@masenf/hello-react": "../hello-react"
"@masenf/hello-react-tgz": "../hello-react/masenf-hello-react-0.1.0.tgz"
```

Both forms install and render; the wrapped React component receives its `label` prop and its
`children` (a State var), works inside `rx.foreach`, and State events update it
(`shots/7117_dir_and_tgz.png`, labels `['HELLO:from-dir','HELLO:a','HELLO:b','HELLO:from-tgz']`,
zero console errors).

**0.9.11.post1 baseline reproduces the reported truncation** — `logs/7117_prev.log`:

```
error: Could not find package.json for "file:.." dependency "@masenf/hello-react"
error: @masenf/hello-react@.. failed to resolve
error: @masenf/hello-react-tgz@.. failed to resolve
```

Note (not a bug): wrapping the *same* `tag` from two different libraries raises
`ValueError: Can not compile, the tag Hello is used multiple time from ... and ...`. Give the
second wrapper an `alias`. The error message itself prints the full untruncated specifiers.

### #7129 — bun/npm lockfile switching — PASS for the reported failure; sticky-npm behaviour worth documenting

Round trip in `dsc/` (`logs/lock_*.log`):

| step | `reflex.lock/` after | frontend 200 | error |
|---|---|---|---|
| start (bun runs) | `bun.lock`, `package.json` | — | — |
| `REFLEX_USE_NPM=1 reflex run` | `package-lock.json`, `package.json` | 9 s | none |
| plain `reflex run` | `package-lock.json`, `package.json` | 5 s | **none** (no `lockfile had changes`) |
| plain run, install cache cleared | `package-lock.json`, `package.json` | 5 s | none |
| after `rm .web/package-lock.json reflex.lock/package-lock.json` | `bun.lock`, `package.json` | ok | none |

The specific `bun install --frozen-lockfile: lockfile had changes` failure from the previous
campaign's FINDING-021 **did not reproduce** — only the lockfile of the package manager that
actually ran is kept, as claimed.

Behaviour worth documenting (anomaly, both this and the previous run): **one
`REFLEX_USE_NPM=1` run converts the project to npm for good.** Subsequent runs *without* the
env var keep using npm, because the installer is chosen by which lockfile exists:

```
after a bun run : Using package installer at: ['.../reflex/bun/bin/bun', '/opt/node22/bin/npm']
after an npm run: Using package installer at: ['/opt/node22/bin/npm', '.../reflex/bun/bin/bun']
                  Running command: ['/opt/node22/bin/npm', 'install', '--legacy-peer-deps', ...]
```

The only way back to bun is deleting `package-lock.json` from both `.web/` and `reflex.lock/`
(verified — `logs/lock_F_backtobun.log`). This is self-consistent with the changelog, but there
is no documented `REFLEX_USE_NPM=0` escape hatch, so FINDING-021 should be re-graded from
"fails" to "sticky but functional, undocumented".

### #7202 — no crash when node is missing; react-router 8.4.0 — PASS

With every PATH entry containing `node`/`npm`/`npx`/`bun` removed
(`which node npm bun` → nothing) and a fresh `HOME`:

* `reflex init --name nonode --template blank` → exit 0, no `restartWithMergedOptions` anywhere
  in the log (`logs/7202_init_nonode.log`); reflex provisioned its own bun under
  `$HOME/.local/share/reflex/bun`.
* `reflex run` → frontend 200 after **7 s**, page renders, title `Nonode | Index`, zero console
  errors (`logs/7202_run_nonode.log`, `shots/7202_nonode.png`).

react-router versions in `.web/package.json` on 0.9.12a1 — all four at **8.4.0**:
`react-router 8.4.0`, `@react-router/node 8.4.0`, `@react-router/dev 8.4.0`,
`@react-router/fs-routes 8.4.0` (vite 8.2.2, react 19.2.8). 0.9.11.post1 for comparison:
`@react-router/dev 8.3.1`, `@react-router/fs-routes 8.3.1`.

### #7193 — Granian lifecycle logs as JSON — PASS

`reflex run --json --loglevel debug`, backend-only and full dev, parsed line by line:

* backend-only: 41 non-blank lines, **39 valid JSON**, 2 non-JSON.
* full dev incl. a hot reload: 167 lines, **163 valid JSON**, 4 non-JSON.

**Every non-JSON line was my own app's `logging.getLogger("dsc.app").warning(...)` output**, not
reflex's. The previous campaign's FINDING-016 (9 plain granian lines) is fixed: all granian
lifecycle messages now come through as records with `logger` `_granian` / `_granian.serve` —
`Starting granian (main PID: …)`, `Listening at: …`, `Spawning worker-1 with PID: …`,
`Started worker-1`, `Changes detected, reloading workers..`, `Stopping worker-1`,
`Stopped worker-1`, `Shutting down granian`, `Granian shutdown completed, see ya!`.
Even vite's stdout is wrapped (`logger: reflex.utils.processes`).
Record shape: `{timestamp, level, logger, message, location, pid}`.
Evidence: `logs/07089_new_backendonly.log`, `logs/full_dev_json.log`.

**Minor anomaly:** user code that logs through plain stdlib `logging` is *not* routed through
the reflex JSON pipeline, so it breaks "`reflex run --json` stdout is valid JSON lines" for any
app that uses `logging` directly. Low severity / arguably by design, but undocumented.

### #7152 — deprecation warnings via the shared logging pipeline — PASS

Deprecations surface as records with `logger: reflex.deprecation` and `level: warning`:
`@rx.memo` without annotations, and the implicit-Radix-Themes deprecation. Each fires **once per
process**; across a dev run there are three emitting processes (compile worker, serve worker,
post-reload worker), each logging once — no double-logging within a process.
`rx._x` experimental warning comes through as `logger: reflex.experimental`.
Evidence: `logs/full_dev_json.log` L30/L33, L90, L110/L113.

### #7075 — rxconfig-imported modules kept across config reload — PASS

`rxconfig.py` imports a sibling `settings.py` that logs a line on import and defines a
`SettingsMarker` class. Across a full dev run **plus** a source-edit hot reload:

* `SETTINGS_IMPORT` appears **exactly once** in the whole log (launcher pid 1472).
* `id(SettingsMarker)` is identical (`286011888`) in every worker, including the post-reload
  worker pid 2223 — so the class was not redefined.
* No duplicate-state-registration warning or error anywhere in the log.

Evidence: `logs/full_dev_json.log` (grep `SETTINGS_IMPORT|APP_MODULE_IMPORT`).
Caveat for whoever re-runs this: granian forks its workers here, so workers inherit the module
from the parent and identical `id()` values are weaker evidence than they look. The strong
signals are the single import line and the absence of duplicate-registration errors.

### #7049 — deferred imports / faster startup — PASS (claim holds)

Backend worker on 0.9.12a1, measured through the app's own `modules_report` var and
`/proc/self/status`:

* `reflex run --backend-only` → **/ping 200 in 0.85 s** (warm `.web`).
* worker RSS 55-59 MB; `len(sys.modules)` 692-739 depending on phase.
* Of the probed heavy modules — `sqlalchemy`, `alembic`, `starlette_admin`, `pandas`, `httpx`,
  `reflex.compiler` — **only `reflex.compiler` is imported**. No DB, admin or pandas import in a
  plain app's backend worker.

Evidence: `logs/07089_new_backendonly.log`, `shots/nocompile_new_events.json`
(`modules :: pid=1507 nmods=737 rss_kb=57396 present=reflex.compiler`).
I did **not** produce a like-for-like 0.9.11.post1 number for startup time / module count, so
the *relative* improvement claim is unverified — only the absolute state is (see `skipped`).

### hosting-cli 0.1.72 non-interactive semantics — PASS, with a `--json` inconsistency

```
reflex cloud --help                   -> exit 0, full command list
reflex deploy --help                  -> exit 0 (has --json and --loglevel)
reflex cloud apps list --json         -> exit 1, "Token is required for non-interactive mode."
reflex cloud whoami --json            -> exit 1, "Not logged in. Run `reflex login` ..."
```

Exit 1 + refusal in non-interactive mode is the documented 0.1.72 behaviour. **Anomaly:** with
`--json` passed, those two error messages are emitted as plain text, not JSON records — so a
script consuming `reflex cloud ... --json` cannot parse the failure path. Not baselined against
0.9.11 (the hosting CLI is the same 0.1.72 in both venvs, so this is almost certainly
pre-existing, not a regression). Evidence: `cli/`.

## Handover item from the `ent_map_dnd_flow_mantine` cluster

*"a module that raised at page-evaluation time logged the traceback followed by
`[ERROR] Unexpected exit from worker-1`, and the backend did NOT come back after the source was
fixed."*

**Did not reproduce on 0.9.12a1.** Deliberate sequence with a browser page held open
(`scripts/reload_err.py`, `shots/reloaderr_new_events.json`): introduce a `TypeError` from a
component constructor → save → introduce an `AttributeError` → save → fix the source → save.
The worker **recovered**: after the fix, `/ping` returned 200 again, the page reloaded to the new
heading (`dsc v3-fixed`) and events worked (`RECOVERED: true`,
`shots/reloaderr_new_after_fix.png`).

What *is* real, and is the same mechanism as the #6981 regression above: **while the app module
is broken, `/ping` does not fail — it hangs.** `ping_after_break` and `ping_after_break2` both
returned curl code `000` after the full 8 s timeout rather than a connection error. Under
0.9.11.post1 the port was released and the client got an immediate refusal. So a broken reload
is now *silent and slow* rather than *loud and fast*. Same root cause as the SIGTERM finding —
report them together.

I did not re-run the broken-reload sequence on 0.9.11.post1 (the port-probe test above covers
the same mechanism directly and is baselined).

## Not covered

* `#7166` build-sdk logging and `reflex-build-sdk==0.0.2` client renames — **skipped**, ran out
  of timebox; needs its own venv with `reflex-build-sdk==0.0.2`.
* prod-mode (`reflex run --env prod`, one port for both flags) signal handling — **skipped**.
* `reflex export --json` / `reflex init --json` line-by-line JSON validation — **skipped**
  (`reflex run --json` was validated in both dev and backend-only).
* A 0.9.11.post1 startup-time / `sys.modules` baseline for #7049.

## Cleanup performed

All servers and browsers started here were killed by pid/pgid. Verified with
`python3 $SB/bin/ports.py $(seq 3380 3399) $(seq 8380 8399)` → empty, and
`ps aux | grep chrome-linux/chrome` → 0. Processes on 3220/8220/3540/8540 belong to other
agents and were left alone. `.web/` and `node_modules/` are excluded from the copied artifacts.
