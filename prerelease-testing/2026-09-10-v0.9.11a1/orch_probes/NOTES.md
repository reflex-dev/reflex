# orch_probes — orchestrator's own offline / CLI-only probes (2026-09-10)

Cheap checks the orchestrator ran directly, covering items whose cluster agents had not run yet.
All PyPI-only venvs (`$SB/envs/smoke` = reflex 0.9.11a1, `$SB/envs/base0910` = 0.9.10.post2),
every script run from `/tmp` with an `assert "/envs/smoke/" in reflex.__file__` guard.

## Rerun

```
cd /tmp && $SB/envs/smoke/bin/python <thisdir>/probe_offline.py            # logs/probe_smoke.json
cd /tmp && $SB/envs/smoke/bin/python <thisdir>/cloud_sweep.py $SB/envs/smoke/bin/reflex   # logs/cloud_sweep_0911.json
```

## Results

### reflex.testing / AppHarness (#6974/#7008) — FIXED since the 0.9.9a1 campaign
`import reflex.testing` succeeds in a bare install, and `AppHarness.create(...).__enter__()`
without the extra raises a directly actionable error:

```
ImportError: AppHarness backend support requires `uvicorn`. Install it with `pip install 'reflex[testing]'`.
```

That closes the previous campaign's FINDING-016 (which reported an undeclared dependency).

### `reflex_base.otel` is inert without reflex-otel (#6227) — as documented
After `import reflex` in the bare smoke venv: zero `opentelemetry*` modules in `sys.modules`
and `reflex_base.otel.enabled is False`.

### `_load_config()` deprecation (#6933) — works, with a wording nit
Calling it prints, through the logging pipeline (not the `warnings` module — `catch_warnings`
records nothing):

```
DeprecationWarning: _load_config() has been deprecated in version 0.9.9.post1.
Use _get_config() to load a config from disk, or get_config() to read the config
cached on the current RegistrationContext. It will be completely removed in 1.0.
```

The reflex-base 0.9.11a1 changelog files this deprecation under 0.9.11a1 while the message says
"deprecated in version 0.9.9.post1"; the two disagree about when it started. Cosmetic.

### `reserve_stdout` (#6917) — is a setter, not a context manager
`reflex_base.utils.log.reserve_stdout(reserved: bool = True)` sets a module global and returns
`None`, so `with reserve_stdout():` raises `TypeError: 'NoneType' object does not support the
context manager protocol`. That matches the changelog's "for as long as it is set", but the
name reads like a context manager and there is no scoped form, so a caller that raises between
`reserve_stdout(True)` and `reserve_stdout(False)` leaves stdout reserved for the process.
Observation for the API surface, not a defect.

### `frontend_path` validation (#7044) — rejects what the changelog promises, with gaps
Rejected with a clear `ConfigError` naming the offending segment: `../x`, `a\b`, `C:foo`,
`/ok/../x`, `/./x`. Still **accepted**: `//srv` and `/a//b` (empty segments), `/ .` (a segment
that is a space and a dot), `/a ` (trailing space), `/a%2e%2e`. The validator
(`packages/reflex-base/src/reflex_base/config.py:612`) skips empty segments and checks the rest
with `_is_plain_path_segment`. Trailing spaces and dots are exactly the class Win32 trims, which
is the mechanism the PR cites for the drive-letter/backslash cases, so the guard is narrower
than its rationale. Low severity, Windows-only impact.

### `rx.Model(table=True)` without sqlmodel — STILL the previous campaign's FINDING-014
```
TypeError: Thing.__init_subclass__() takes no keyword arguments
```
No mention of `reflex[db]` or sqlmodel. Unchanged from 0.9.9a1; pre-existing, low.

### `reflex cloud` sweep off a TTY (#6917) — clean
34 leaf commands enumerated from `--help` and run off-TTY with no token, each three ways
(plain, `--json`, `--json --loglevel debug`), 45 s timeout each:

- **0 hangs.** Every command returns; the pre-#6917 prompt-forever failure mode is gone.
- **stdout is never polluted**: for every command, `--json` stdout is either empty or exactly
  one parseable JSON document. Human text (including the debug log records) is on stderr.
- Auth-required commands exit 1 with `Token is required for non-interactive mode.` on stderr.
- Commands missing a required argument exit 2 with the usage line on stderr.

One consistency gap, **pre-existing** (identical on 0.9.10.post2): `reflex cloud regions --json`
and `reflex cloud vmtypes --json` print `[]` and exit **0** while stderr says
`Unable to get regions due to 403 Forbidden.` An agent that trusts the exit code reads an
auth failure as "no regions exist". `reflex cloud config --json` likewise exits 0 with
`{"generated": false, "path": null}` while stderr says PyYAML is missing (PyYAML is not a
dependency of reflex-hosting-cli). Compare `reflex cloud project selected --json`, which carries
an explicit `"error": null` field — the pattern the failing commands do not follow.

## hybrid_property typing promise vs pyright version (#6812) — bracketed to pyright 1.1.412

The `hybrid_property` cluster reported class-level access typing as `Any` on pyright 1.1.413,
contradicting the reflex-base 0.9.11a1 changelog ("type checkers now resolve class-level access to
the frontend var's type instead of the descriptor"). Re-run here with ONE file
(`pyright/hp_types.py`, copied next to this NOTES.md) across versions, each in its own venv:

| reflex | pyright | `State.full` | `State.doubled` | `State.positive` | explicit var fn | `State().full` |
|---|---|---|---|---|---|---|
| 0.9.10.post2 | 1.1.411 | `HybridProperty` | `HybridProperty` | `HybridProperty` | `HybridProperty` | `str` |
| **0.9.11a1** | **1.1.411** (repo pin) | **`StringVar[str]`** | **`NumberVar[int]`** | **`BooleanVar`** | **`StringVar[str]`** | `str` |
| 0.9.11a1 | 1.1.412 | `Any` | `Any` | `Any` | `Any` | `str` |
| 0.9.11a1 | 1.1.413 | `Any` | `Any` | `Any` | `Any` | `str` |
| 0.9.11a1 | 1.1.414 | `Any` | `Any` | `Any` | `Any` | `str` |

So the feature **does** work, and is a clear improvement over 0.9.10.post2, at the pyright version
this repo pins (1.1.411, raised from 1.1.408 in this same train by #6893). It degrades to `Any`
from **pyright 1.1.412 onward** — every version a downstream user would install today. Instance
access stays correct everywhere, and there are no errors either way, so the loss is silent.

Rerun:
```
uv venv envs/pyrightNNN --python 3.11
uv pip install --python envs/pyrightNNN/bin/python --prerelease=allow 'reflex==0.9.11a1' 'pyright==1.1.NNN'
PATH=/opt/node22/bin:$PATH envs/pyrightNNN/bin/pyright --pythonpath envs/pyrightNNN/bin/python --outputjson <thisdir>/hp_types.py
```

## `reflex run --json` stdout is still not strict JSON-lines (previous campaign's FINDING-013) — STILL OPEN

```
cd <app dir>
REFLEX_TELEMETRY_ENABLED=false <venv>/bin/reflex run --backend-only --json --loglevel debug --backend-port 8055 > out 2> err
# wait for /ping, then stop; parse every non-empty stdout line with json.loads
```

| version | stdout lines | non-JSON lines | stderr |
|---|---|---|---|
| 0.9.11a1 | 34 | **9** | 0 |
| 0.9.10.post2 | 41 | **9** | 0 |

The nine are granian's own lifecycle messages, which bypass the reflex logging pipeline:

```
[INFO] Starting granian (main PID: 5115)
[INFO] Listening at: http://0.0.0.0:8055
[INFO] Spawning worker-1 with PID: 5122
[INFO] Started worker-1
[INFO] Stopping worker-1
[ERROR] Unexpected exit from worker-1
[INFO] Shutting down granian
[INFO] Stopped worker-1
[INFO] Granian shutdown completed, see ya!
```

Unchanged from 0.9.10.post2, so pre-existing, not a regression of this train. Note the contrast
with `reflex cloud --json`, where #6917's `reserve_stdout` keeps stdout clean: the same treatment
has not reached `reflex run`. Evidence: `logs/json_backend_0911a1.out`, `logs/json_backend_0910.out`.

## `rx.plotly` still drops the `id` prop on react-plotly.js 4.1.0 (previous campaign's FINDING-020) — STILL OPEN

```
uv venv envs/probe_plotly --python 3.11
uv pip install --python envs/probe_plotly/bin/python --prerelease=allow \
  'reflex==0.9.11a1' 'reflex-components-plotly==0.9.6a1' plotly
cd /tmp && envs/probe_plotly/bin/python -c "
import reflex as rx, plotly.graph_objects as go
c = rx.plotly(data=go.Figure(data=[go.Scatter(x=[1,2], y=[3,4])]), id='the-plot')
print(c.render()['props'])"
```

Compiled props: `['id:"the-plot"', 'ref:ref_the_plot', 'useResizeHandler:true', ...]` — the wrapper
still emits a React `id` prop and never `divId`, which is the only identifier react-plotly.js's
`Plot` forwards to the container div. The plotly bump to react-plotly.js 4.1.0 in this train does
not change that, so the previous campaign's end-to-end result (chart renders,
`document.getElementById('the-plot')` is null) still stands. Pre-existing, low.

## `REFLEX_USE_NPM=1` on 0.9.11a1: works, but the choice sticks silently

Fresh blank app, three consecutive runs in the same directory (`logs/npm_run.trimmed.log`,
`bun_after_npm.trimmed.log`, `bun_after_rmlock.trimmed.log`):

| run | env | installer actually used | frontend | persisted lockfile |
|---|---|---|---|---|
| 1 | `REFLEX_USE_NPM=1` | npm (node 22.22.2) | 200, page clean in Chromium | `reflex.lock/package-lock.json` |
| 2 | *(no env var)* | **npm again** | 200 | `package-lock.json` |
| 3 | *(no env var)*, after `rm reflex.lock/package-lock.json .web/package-lock.json` | bun 1.4.0 | 200 | `bun.lock` |

- The npm path is healthy on this train: postcss-import 17 and the rest install under node 22, the
  dev server starts, and the driven page is clean (0 console errors, 0 failed requests).
- The previous campaign's FINDING-018 (a *failed* npm run persisting an inconsistent lock that breaks
  subsequent runs) did **not** reproduce: the npm → bun switch is clean once the npm lockfile is gone.
- What is surprising: reflex picks the installer from the persisted lockfile, so a single
  `REFLEX_USE_NPM=1` run converts the project to npm permanently. Run 2 used npm with no env var and
  nothing announcing it. A user who tries npm once silently keeps npm — and never gets the Bun 1.4
  lockfile behaviour this train is about. Deleting the npm lockfile is the undocumented remedy.

## `rx.AdminDash`: every `/admin` route returns HTTP 500 on both versions

The reflex 0.9.11a1 changelog says "AdminDash now works with starlette-admin 1.0, which renamed the
SQLAlchemy `Admin(engine=...)` argument to `session_provider`. Both starlette-admin 0.x and 1.x are
supported." The rename is indeed handled (reflex passes the engine positionally,
`reflex/app.py:1443`), but the dashboard itself does not serve.

App: `adminapp/` here — one `rx.Model(table=True)`, `rx.App(admin_dash=rx.AdminDash(models=[Widget]))`,
`reflex db init && reflex db makemigrations && reflex db migrate`, then `reflex run`.

| reflex | starlette-admin | `/ping` | `/admin/` | error |
|---|---|---|---|---|
| 0.9.11a1 | 1.0.1 | 200 | **500** | `NoMatchFound: No route exists for name "admin:list" and params "key"` |
| 0.9.11a1 | 1.0.0 | 200 | **500** | same shape |
| 0.9.11a1 | 0.17.1 | 200 | **500** | `NoMatchFound` |
| 0.9.10.post2 | 0.17.1 | 200 | **500** | `NoMatchFound: No route exists for name "admin:statics" and params "path"` |

Every sub-path fails too (`/admin/widget/list`, `/admin/login`, even `/admin/statics/...`), so this is
not a dashboard-index-only problem. **Pre-existing, not a regression of this train.**

Isolation (`admin_isolate.py`, starlette 1.6.0 + starlette-admin 0.17.1, no reflex): the identical
`Admin(engine)` with the same `ModelView`, mounted with `mount_to()` on a plain Starlette app —
and again on a sub-app mounted at `/` — returns **200** for `/admin/` and `/admin/widget/list`. So
neither starlette 1.6 nor an extra mount level explains it; the breakage is in how reflex sets the
admin app up (`reflex/app.py:1428-1453`, mounted onto `self._api`, with the request reaching it
through `reflex/app.py:715 context_middleware`).

Consequence for this release: the changelog's AdminDash line is not observable end to end. The
`engine` → `session_provider` change is necessary but not sufficient — `/admin` is 500 either way.
Logs: `logs/admin_run_new.tail.log` (1.0.1), `admin_run_100.tail.log`, `admin_run_old.tail.log`,
`admin_run_base.tail.log` (0.9.10.post2).
