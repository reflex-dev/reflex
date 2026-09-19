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

## VERIFICATION

Independent adversarial verifier, run 2026-09-19 from the written material only (this NOTES.md
+ `scripts/` + `dsc/`), in a fresh working dir
`$SB/apps/verify_dev_server_cli/` with its own copies of `dsc/` and `dsc_prev/`.
Ports used: frontend 3882-3895, backend 8882-8895 (reserved range 3880-3899 / 8880-8899).
All processes killed; `python3 $SB/bin/ports.py $(seq 3880 3899) $(seq 8880 8899)` exits 0 (nothing bound).

Venvs are the prebuilt shared ones, unchanged:

```
$ uv pip freeze --python $SB/envs/shared/bin/python | grep -i reflex
reflex==0.9.12a1  reflex-base==0.9.12a1  reflex-components-code==0.9.6a1
reflex-components-core==0.9.10a1  reflex-components-dataeditor==0.9.3a1
reflex-components-gridjs==0.9.2a1  reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.4a1  reflex-components-moment==0.9.4
reflex-components-plotly==0.9.7a1  reflex-components-radix==0.9.10a1
reflex-components-react-player==0.9.2  reflex-components-recharts==0.9.4a1
reflex-components-sonner==0.9.4a1  reflex-hosting-cli==0.1.72

$ uv pip freeze --python $SB/envs/prev/bin/python | grep -i reflex
reflex==0.9.11.post1  reflex-base==0.9.11.post1  reflex-components-core==0.9.9  (etc.)
```

Both venvs carry **granian==2.8.3**, so every new-vs-old difference below is reflex's own code,
not a granian upgrade.

Setup:

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/apps/verify_dev_server_cli ; D=/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/dev_server_cli
mkdir -p $W/logs $W/scripts ; cp -r $D/dsc $W/dsc ; cp -r $D/dsc_prev $W/dsc_prev ; cp $D/scripts/* $W/scripts/
export REFLEX_TELEMETRY_ENABLED=false PORTS_PY=$SB/bin/ports.py
```

New scripts written by the verifier live in `verification/scripts/`; new evidence in
`verification/logs/`.

---

### Issue 1 — backend port accepts-but-never-answers after the worker is gone — **CONFIRMED, REGRESSION**

```bash
python3 $W/scripts/sigterm_port_probe.py $SB/envs/shared $W/dsc      3882 8882 new  $W/logs
python3 $W/scripts/sigterm_port_probe.py $SB/envs/prev   $W/dsc_prev 3883 8883 prev $W/logs
```

Reproduced exactly as written, on my own ports, first try:

| | before | +8 s | +18 s | after SIGKILL to group |
|---|---|---|---|---|
| 0.9.12a1 | `200` / 0.00 s | `TIMEOUT_NO_REPLY_6s` | `TIMEOUT_NO_REPLY_6s` | `CONNECTION_REFUSED` |
| 0.9.11.post1 | `200` / 0.00 s | `CONNECTION_REFUSED` | `CONNECTION_REFUSED` | `CONNECTION_REFUSED` |

`verification/logs/portprobe_new.json`, `verification/logs/portprobe_prev.json`.

**The repro as written was incomplete in one way that matters, and I completed it.** It leads with
the SIGTERM case, which only occurs together with issue 2 (SIGTERM being ignored) and so looks
like a corner case. The NOTES' own parenthetical — the same hang via a broken hot reload — is
the real-world form, and it was only evidenced indirectly (`shots/reloaderr_new_events.json`,
a curl `000`, from a run whose purpose was something else). I wrote a dedicated probe,
`verification/scripts/break_reload_probe.py`, that involves **no signal at all**: start the dev
server, confirm `/ping` 200, append `raise RuntimeError(...)` to `dsc/dsc.py` (an ordinary
"developer saved a file with an error"), then open a raw socket to the backend port.

```bash
python3 $W/scripts/break_reload_probe.py $SB/envs/shared $W/dsc      3888 8888 new  $W/logs
python3 $W/scripts/break_reload_probe.py $SB/envs/prev   $W/dsc_prev 3889 8889 prev $W/logs
```

| | before break | +10 s | +24 s | after the file is fixed |
|---|---|---|---|---|
| 0.9.12a1 | `200` | `TIMEOUT_NO_REPLY_6s` | `TIMEOUT_NO_REPLY_6s` | `200` / 0.02 s |
| 0.9.11.post1 | `200` | `CONNECTION_REFUSED` | `CONNECTION_REFUSED` | `200` / 0.02 s |

`verification/logs/breakreload_new.json`, `verification/logs/breakreload_prev.json`,
`verification/logs/breakreload_summary.txt`. Both versions recover fully once the error is
fixed, so this is a stall, not a wedge.

Refutation attempts, all failed:
* Not an environment/proxy artifact — the probe is a raw `socket.create_connection` to
  127.0.0.1, no curl, no proxy, no bun involved.
* Not ports/flakiness — four independent runs (two mechanisms x two versions) on four different
  port pairs, consistent every time.
* Not a granian upgrade — granian is 2.8.3 in both venvs.
* Not app misuse — the same app source produces `CONNECTION_REFUSED` on 0.9.11.post1.
* Partly intended: the #7114 changelog line explicitly wants requests to "wait for the new worker
  instead of being refused". The defect is the missing bound — nothing ever gives up.

Root cause confirmed in the release source: `reflex/utils/exec.py:726-741`,
`ParentBoundGranian._init_shared_socket`, which builds the listening socket in the supervisor.
0.9.11.post1 has no such subclass (`$SB/envs/prev/.../reflex/utils/exec.py:678` constructs a plain
`Granian(...)`), so there the worker owned the socket and its death released the port.
Corroborated independently by `verification/logs/sigres_V_N_proc.json` vs `sigres_V_P_proc.json`:
after the stuck SIGTERM, 0.9.12a1 still lists `8884  pids=26295  .../bin/python` as bound by the
supervisor, while 0.9.11.post1 lists only the frontend port.

**Severity: medium** (explorer said high). Dev mode only — `run_granian_backend_prod`
(`reflex/utils/exec.py:857`) uses plain `Granian`, so no deployed app is affected — and it
self-heals the moment the app imports again. But it is unbounded: a `/ping` health check against
a dev backend with a broken module blocks until the *client's* timeout, forever. Worth a bounded
wait (return 503 after N seconds with no live worker) but not a release blocker.

### Issue 2 — dev `reflex run` ignores SIGTERM sent to the pid alone — **CONFIRMED, NOT a regression**

```bash
python3 $W/scripts/signal_test.py $SB/envs/shared $W/dsc      V_N_proc TERM proc $W/logs 3884 8884
python3 $W/scripts/signal_test.py $SB/envs/prev   $W/dsc_prev V_P_proc TERM proc $W/logs 3886 8886
```

| | exit | after | survivors | ports still bound |
|---|---|---|---|---|
| 0.9.12a1 | `TIMEOUT_30s` | 30.11 s | `reflex`, `bun`, `node` | 3884 (node), **8884 (reflex)** |
| 0.9.11.post1 | `TIMEOUT_30s` | 30.08 s | `reflex`, `bun`, `node` | 3886 (node) only |

`verification/logs/sigres_V_N_proc.json`, `verification/logs/sigres_V_P_proc.json`. Identical on
both versions, so pre-existing and not introduced by this release — the explorer's call is right.
The one new detail my baseline adds is the `ports_after` column, which is the cleanest single
piece of evidence for issue 1: same stuck process, backend port bound only on 0.9.12a1.

**Severity: medium**, unchanged. It is a real defect (`docker stop` / `kill <pid>` never stops a
dev server, and the #7140 changelog line advertises "clean SIGTERM shutdown" for the docker
examples), but it ships in every recent release and it is not a reason to hold 0.9.12a1.

### Issue 3 — `[ERROR] Unexpected exit from worker-1` on a clean shutdown — **CONFIRMED, NOT a regression** (explorer had not baselined this; I did)

```bash
python3 $W/scripts/signal_test.py $SB/envs/shared $W/dsc      V_N_group TERM group $W/logs 3885 8885
python3 $W/scripts/signal_test.py $SB/envs/prev   $W/dsc_prev V_P_group TERM group $W/logs 3887 8887
```

0.9.12a1 (`verification/logs/sigres_V_N_group.json`): `exit_code: 0` in 0.15 s, no survivors,
log tail

```
App running at: http://localhost:3885/
Backend running at: http://0.0.0.0:8885
[ERROR] Unexpected exit from worker-1
Info: Reflex app stopped.
```

0.9.11.post1 (`verification/logs/sigres_V_P_group.json`) — the baseline the explorer skipped —
**logs the same ERROR line**, so the line itself is not new:

```
"exit_code": 1, "log_has_143": ["Starting frontend failed with exit code 143",
                                "error: script \"dev\" exited with code 143"],
"log_has_error": ["[ERROR] Unexpected exit from worker-1"]
```

Two consequences. First, regression status is settled: **no**. Second, this run independently
**confirms the #6981 fix** — 0.9.11.post1 exits 1 with the "exit code 143" lines, 0.9.12a1 exits 0
with none (`verification/logs/sig_V_P_group.log` vs `sig_V_N_group.log`).

The message is not reflex's: it is granian's own, `granian/server/common.py:61`
(`logger.error(f'Unexpected exit from worker-{self.idx + 1}')`), byte-identical in both venvs'
granian 2.8.3. A fix in reflex would mean filtering/downgrading that record in
`_granian_log_dictconfig()` (`reflex/utils/exec.py:689`) or fixing the shutdown ordering upstream.

**Severity: low**, cosmetic. Still a genuine defect worth a ticket: on 0.9.12a1 the shutdown
really is clean, so an ERROR line on every Ctrl-C is now purely false. It was masked on
0.9.11.post1 where the shutdown genuinely failed.

### Issue 4 — "one `REFLEX_USE_NPM=1` run permanently switches a project to npm with no documented way back" — **REFUTED** (the stickiness is real and intended; the "no way back" claim is wrong)

```bash
# verification/scripts/lock_probe.sh: runs `reflex run --loglevel debug`, records the chosen
# installer and what reflex.lock/ holds afterwards, then kills the process group.
$W/scripts/lock_probe.sh $SB/envs/shared $W/dsc L0_baseline_bun 3890 8890 $W/logs
$W/scripts/lock_probe.sh $SB/envs/shared $W/dsc L1_npm1         3891 8891 $W/logs 1
$W/scripts/lock_probe.sh $SB/envs/shared $W/dsc L2_plain        3892 8892 $W/logs
$W/scripts/lock_probe.sh $SB/envs/shared $W/dsc L3_npm0         3893 8893 $W/logs 0
$W/scripts/lock_probe.sh $SB/envs/shared $W/dsc L4_plain_again  3894 8894 $W/logs
```

| step | `REFLEX_USE_NPM` | installer chosen | `reflex.lock/` after |
|---|---|---|---|
| L0 | unset | **bun** first | `bun.lock` |
| L1 | `1` | **npm** first | `package-lock.json` |
| L2 | unset | **npm** first | `package-lock.json` |
| L3 | **`0`** | **bun** first (`bun install v1.4.0` ran) | **`bun.lock`** |
| L4 | unset | **bun** first | `bun.lock` |

`verification/logs/lockswitch_summary.txt`, `verification/logs/lockv_L*.trimmed.log`.

The first half of the claim holds: L2 shows a plain run still choosing npm after one
`REFLEX_USE_NPM=1` run. But the headline — *"no documented way back"*, *"no `REFLEX_USE_NPM=0` /
`--package-manager` escape hatch documented"*, recovery only by deleting `package-lock.json` from
two places — **is false**. `REFLEX_USE_NPM=0` is an explicit escape hatch and it works in one run:

`reflex/utils/js_runtimes.py:115-132`

```python
def prefer_npm_over_bun() -> bool:
    """...
      2. ``REFLEX_USE_NPM`` set — honor the explicit value.
      3. Persisted lockfile state — implicit npm if only a npm lock is present in ``reflex.lock/``.
    """
    if constants.IS_WINDOWS and windows_check_onedrive_in_path():
        return True
    explicit = environment.REFLEX_USE_NPM.getenv()
    if explicit is not None:
        return explicit
    return _persisted_lockfile_implies_npm()
```

`getenv()` returns `None` only when the variable is unset, so `REFLEX_USE_NPM=0` takes precedence
over the lockfile heuristic (step 2 beats step 3). L3 proves it end to end: bun was selected,
`bun install v1.4.0` ran, and `reflex.lock/` went back to `bun.lock` — no file deletion. L4 then
confirms the project stays on bun afterwards.

The behaviour the explorer calls undocumented is also deliberate and documented in the code it
comes from, `_persisted_lockfile_implies_npm` (`reflex/utils/js_runtimes.py:99-112`): *"A project
is treated as npm-managed when `reflex.lock/` carries an npm lockfile but no bun lockfile, so
committing only `package-lock.json` is enough to opt in without setting `REFLEX_USE_NPM=1`."*
That is a feature (check in a `package-lock.json`, the whole team gets npm), not a trap.

A final full run with everything unset (`verification/logs/lockv_L5_final.trimmed.log`) served the
frontend 200 in 3 s and `/ping` 200, so the npm→bun round trip leaves a fully working project.

What survives as a real, much smaller point: **nothing tells the user their project was
converted**, and `REFLEX_USE_NPM=0` is not mentioned in the changelog or user docs. That is a
docs/console-message nit, not a code defect. The explorer's re-grading of the previous campaign's
FINDING-021 from "fails" to "sticky but functional" is confirmed; its recovery advice (delete two
lockfiles) should be replaced with "run once with `REFLEX_USE_NPM=0`".

**Severity: not-a-defect.**

### Verifier notes on the material

* `scripts/sigterm_port_probe.py` and `scripts/signal_test.py` are self-contained and ran
  unmodified against fresh app copies — good repro quality.
* One gap worth fixing for a fix agent: the high-severity issue is written as "after a SIGTERM
  that fails to stop `reflex run`", which buries it behind issue 2. It should lead with the
  broken-hot-reload form, which needs no signal and is what a developer hits daily. See
  `verification/scripts/break_reload_probe.py`.
* Caveat on my own `lock_probe.sh`: its readiness loop greps for `frozen-lockfile`, which also
  matches bun's own `'--frozen-lockfile'` argument in the debug log, so bun runs report
  `frontend200=ERROR(2s)` spuriously. The installer choice and the resulting `reflex.lock/`
  contents (what the test is about) are unaffected; L1, L2 and L5 reached `App running at`.

### Cleanup

All verifier processes killed by pid/pgid. `python3 $SB/bin/ports.py $(seq 3880 3899) $(seq 8880 8899)`
returns nothing (exit 0); `ps -eo pid,pgid,comm | grep -E 'reflex|bun|node|granian'` shows no
process belonging to this verifier.
