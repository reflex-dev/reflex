# `reverify_prev` — re-verification of the 0.9.9a1 campaign's unfixed findings

Scope: re-run the **original failing repros** of the 2026-08-27 (`v0.9.9a1`) campaign's
findings that `0.9.9a2` did **not** fix, against

* **reflex 0.9.11a1** (this train) and
* **reflex 0.9.10.post2** (previous stable, baseline)

plus a quick sweep of the items `0.9.9a2` already fixed, to confirm they stayed fixed
(the vite item re-checked because vite moved 8.2.0 → **8.2.2** in this train).

All installs PyPI-only in isolated uv venvs; every probe asserts
`reflex.__file__` resolves inside a venv `site-packages`; no Python was ever run with
`/home/user/reflex` as cwd. Browser work in real headless Chromium via Playwright
(`/opt/pw-browsers/chromium`). Reserved ports used: frontend 5380–5386, backend 9780–9786.
Nothing of mine was left running (verified with `ps`).

## Results table

| # | Item (previous campaign) | Previous status | 0.9.10.post2 | 0.9.11a1 | Verdict |
|---|---|---|---|---|---|
| 1 | **FINDING-013** `reflex run --json --loglevel debug` (dev): granian's own lines are plain text on stdout | LOW, open | 8 non-JSON lines of 102 | 8 non-JSON lines of 98 | **still open** (pre-existing) |
| 2 | **FINDING-014** `rx.Model(table=True)` without sqlmodel → bare `TypeError`, no `reflex[db]` pointer | LOW, open | `TypeError: Item.__init_subclass__() takes no keyword arguments` | identical | **still open** (pre-existing) |
| 3 | **FINDING-016** `reflex.testing` / `AppHarness` needs undeclared uvicorn + psutil | LOW, open | `import reflex.testing` → `ModuleNotFoundError: uvicorn`; no `testing` extra | bare import OK; `reflex[testing]` extra ships psutil/selenium/uvicorn; dev **and** prod harness drive an app end to end (3/3 pytest) | **fixed** (#6974/#7008) |
| 4a | **FINDING-017a** `compile_app()` discards user-level `bundle_library()` | LOW, open | wiped; `window.__reflex` has no `lucide-react` | identical | **still open** (pre-existing) |
| 4b | **FINDING-017b** dynamic serializer never rewrites **subpath** imports of a bundled lib | LOW, open | bare `lucide-react/dist/esm/icons/apple.mjs`; dynamic block never renders | identical | **still open** (pre-existing) |
| 5 | **FINDING-018** failed `REFLEX_USE_NPM=1` run persists an inconsistent `reflex.lock` that breaks the next run | LOW, open | next bun run **succeeds** (HTTP 200) | next bun run **succeeds** (HTTP 200) | **cannot reproduce** (breakage gone; the persisted state is still inconsistent — see issue R-5) |
| 6 | **FINDING-020** `rx.plotly` drops the `id` prop (react-plotly.js wants `divId`) | LOW, open | `#the-plot` absent from the DOM, chart renders | identical, now on react-plotly.js **4.1.0** | **still open** (pre-existing) |
| 7 | **FINDING-024** `CachedVarOperation` masks `AttributeError` inside cached var computations | MEDIUM, open | `VarAttributeError: Attribute _cached_get_all_var_data not found.`, no `__cause__` | identical | **still open** (pre-existing) |
| 8 | **FINDING-003** background-task `on_load` cancelled on navigation | MEDIUM, behaviour change | cancelled | cancelled | **unchanged and now documented** in CHANGELOG (#6593) |

### Sweep of the items 0.9.9a2 fixed (confirm they stayed fixed)

| Item | 0.9.11a1 | 0.9.10.post2 |
|---|---|---|
| FINDING-002 / -006 PEP 695 alias setattr + uncalled alias-annotated handler | pass | pass |
| FINDING-004 `client_error` no-argument emit | pass — 0 `TypeError`/`Task exception`, 5 `malformed client_error payload` debug drops | (fixed since 0.9.9a2) |
| FINDING-007 upload sanitizer, all-dots filenames | pass — `..`, `./../.`, `..\`, `/..`, `...` all → `upload` | pass |
| FINDING-027 console warnings print literal `\[` | pass — `dict[str, typing.Any]`, no backslash | pass |
| FINDING-011 `reflex run` hang after fatal node-version error (`REFLEX_USE_NPM=1`) | pass — exit 1 in 8–17 s | pass — exit 1 in 10 s |
| FINDING-010 `library="react-router-dom"` | pass — actionable `ValueError` naming the migration | pass |
| FINDING-012 / -015 / -019 / -028 vite warnings (`jsx` key, `advancedChunks`, `configLoader`) | pass on **vite 8.2.2** — `reflex export` exit 0, 0 matches; generated `vite.config.js` uses `codeSplitting` and imports `./vite-plugin-safari-cachebust.js` | pass on vite 8.2.0 |
| FINDING-005 `REFLEX_ENABLE_FULL_LOGGING` worker records + `--json` purity | pass — 6 worker records in the log file, 0 leaked plain-text lines, `--json` stdout 16/16 JSON | (fixed since 0.9.9a2) |
| Deprecation shims (`bundled_libraries`, `DEFAULT_BUNDLED_LIBRARIES`, `DECORATED_PAGES`, `get_config(reload=True)`) | pass — all return a value + emit a deprecation notice | pass |

## Issues worth carrying forward (all pre-existing; **no regression found in this cluster**)

* **R-1 = FINDING-013** (campaign FINDING-016): `--json` stdout is not strictly parseable at
  `--loglevel debug`; granian's 4 startup + 4 shutdown lines are plain `[INFO] …` text.
  Note the contrast that pins the cause: a **backend-only** `--json` run is 16/16 pure, so it is
  granian's own logger (never given a `log_dictconfig`) that leaks, not the reflex pipeline.
* **R-2 = FINDING-014** (campaign FINDING-012): `class Item(rx.Model, table=True)` on a bare
  install dies with `TypeError: Item.__init_subclass__() takes no keyword arguments` — no
  `reflex[db]` pointer. The guided `ImportError` only exists on `__init__`.
* **R-3 = FINDING-024** (campaign FINDING-013): any `AttributeError` raised inside a cached var
  computation is converted to `VarAttributeError: Attribute _cached_get_all_var_data not found.`
  with `__cause__ = None`, so the real failure is invisible (this is what made the 0.9.9a1
  enterprise breakage undebuggable).
* **R-4 = FINDING-017** (campaign FINDING-022): `bundle_library()` at app-module scope is
  discarded, **and** the dynamic serializer emits the bare subpath specifier for a bundled lib.
  End-to-end on both versions the page silently loses the whole dynamic component and the server
  log shows two distinct frontend exceptions:
  `Failed to resolve module specifier "lucide-react/dist/esm/icons/apple.mjs"` (backend-context
  pass, lib *is* registered) and `Failed to fetch dynamically imported module: data:text/javascript…`
  whose import URL is the malformed
  `https://cdn.jsdelivr.net/npm/lucide-react@1.26.0/+esm/dist/esm/icons/apple.mjs`
  (CDN fallback pass — the subpath is appended *after* jsDelivr's terminal `+esm` marker).
  In this sandbox jsDelivr is blocked by the egress proxy, so the malformed URL could only be
  observed as `ERR_TUNNEL_CONNECTION_FAILED`; the composition itself is visible in the data-URI.
* **R-5 = FINDING-018 residue**: a `REFLEX_USE_NPM=1` run that dies on the node-version preflight
  still mutates persisted state — it writes `reflex.lock/package-lock.json` **next to** the stale
  `reflex.lock/bun.lock` and rewrites `.web/package.json` pins from exact (`"react": "19.2.8"`)
  to caret (`"react": "^19.2.8"`). It is no longer fatal (the next bun run succeeds), but the
  project also silently switches package manager forever: a later plain `reflex run` (no
  `REFLEX_USE_NPM`) runs `npm run dev` with nothing in the log saying so. Identical on both
  versions.
* **R-6 = FINDING-020** (campaign FINDING-017): `rx.plotly(id=…)` never reaches the DOM
  (`document.getElementById('the-plot')` is null while the chart renders and a control
  `rx.box(id='control-box')` gets its id). Unchanged by the react-plotly.js 4.0.0 → 4.1.0 bump.

## Adjacent observations (benign-but-surprising; both versions)

* **A-1 dev server does not exit promptly on SIGTERM/SIGINT when run non-interactively.**
  `reflex run` (dev), signalled while backgrounded: 0.9.11a1 SIGTERM → parent gone after **28 s**
  (children reaped, port closed); 0.9.10.post2 SIGTERM → still alive after **40 s** and the
  frontend still answers HTTP 200; SIGINT → both still alive after 40 s and still serving. So
  0.9.11a1 is better, but a plain `kill` still needs a follow-up `kill -9` in scripts/CI.
* **A-2 confusing shutdown message**: during that SIGTERM shutdown 0.9.11a1 prints
  `Starting frontend failed with exit code 143` + `error: script "dev" exited with code 143`,
  which reads like a startup failure rather than "the frontend was terminated as requested".
* **A-3** `reflex run` emits the default-plugin advisories twice per start
  (`SitemapPlugin is enabled by default …`) and the implicit-Radix deprecation once — noise only.
* **A-4** `reflex export --loglevel debug` logs vite's standard large-chunk advisory
  (`Use build.rolldownOptions.output.codeSplitting…`, `chunkSizeWarningLimit`) on both versions —
  ordinary vite output, not the removed `jsx`/`advancedChunks` warnings.

## How to rerun everything

```bash
SB=/tmp/claude-0/<session>/scratchpad          # any scratch root
DIR=$SB/apps/reverify_prev                     # copy this artifact dir here
```

Venvs (PyPI only; run every `uv pip install` from a neutral cwd, never `/home/user/reflex`):

```bash
uv venv $SB/envs/a1      --python 3.11 && uv pip install --python $SB/envs/a1/bin/python      --prerelease=allow 'reflex==0.9.11a1' plotly
uv venv $SB/envs/b0910   --python 3.11 && uv pip install --python $SB/envs/b0910/bin/python   'reflex==0.9.10.post2' plotly
uv venv $SB/envs/test_a1 --python 3.11 && uv pip install --python $SB/envs/test_a1/bin/python --prerelease=allow 'reflex[testing]==0.9.11a1' pytest playwright httpx
uv venv $SB/envs/test_b  --python 3.11 && uv pip install --python $SB/envs/test_b/bin/python  'reflex[testing]==0.9.10.post2' pytest playwright   # prints: does not have an extra named `testing`
uv venv $SB/envs/driver  --python 3.11 && uv pip install --python $SB/envs/driver/bin/python  playwright python-socketio aiohttp httpx
```

Exact versions used here: `evidence/venv_versions.txt`.

### 1–2, 4, 6, 7 + most of the sweep — one offline probe, no server

```bash
cd $DIR && $SB/envs/a1/bin/python    repros/probe_offline.py   # 0.9.11a1
cd $DIR && $SB/envs/b0910/bin/python repros/probe_offline.py   # baseline
```
Prints one block per item (`F014`, `F024`, `F020`, `F017a/b`, `S002/S006`, `S007`, `S027`,
`S010`, shims). Captured output: `logs/probe_offline_0911a1.log`, `logs/probe_offline_0910.log`.
(The `F020` block needs the `plotly` python package — it is skipped with a `ModuleNotFoundError`
in a venv without it.)

### 3 — FINDING-016, `reflex[testing]` + AppHarness end to end

```bash
cd $DIR/harness
$SB/envs/test_a1/bin/python -m pytest test_harness.py -x -q -s   # 0.9.11a1 -> 3 passed
$SB/envs/test_b/bin/python  -m pytest test_harness.py -x -q -s   # 0.9.10.post2 -> collection error
```
`conftest.py` pins AppHarness's otherwise-ephemeral ports (uvicorn `port=0`, frontend `PORT=0`)
into the reserved range 5384/5385/9784/9785. Logs: `logs/harness_a1_pytest.log` (dev URL
`http://localhost:5384/`, prod URL `http://127.0.0.1:5385/`, counter 0 → 1 in both, empty
console), `logs/harness_0910_pytest.log` (`reflex/testing.py:28: import uvicorn` →
`ModuleNotFoundError`). Screenshots `shots/harness_dev.png`, `shots/harness_prod.png`.

### 4, 6, 8 — live app (`apps/rvapp`), dev mode, Chromium

`apps/rvapp` has four pages: `/` , `/slowbg` (`on_load` = `@rx.event(background=True)` writing
five entries 1 s apart), `/other` (button that starts the *same* background task), `/charts`
(`rx.plotly(data=ChartState.fig, id="the-plot")` + control `rx.box(id="control-box")`), `/dyn`
(`bundle_library("lucide-react")` at module import + a computed `rx.Component` var containing
`rx.icon("apple")`). It also has `BgState.do_log` for the full-logging probe.

```bash
cp -r $DIR/apps/rvapp $SB/apps/rvapp   && cd $SB/apps/rvapp
REFLEX_TELEMETRY_ENABLED=false $SB/envs/a1/bin/reflex run --frontend-port 5380 --backend-port 9780 --loglevel info > $DIR/logs/rvapp_a1_dev.log 2>&1 &
# wait for http://localhost:5380/ == 200, then:
cd $DIR
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python repros/drive_charts_dyn.py http://localhost:5380 shots/a1
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python repros/drive_bg_onload.py  http://localhost:5380 shots/a1
```
Repeat with `$SB/envs/b0910/bin/reflex` on ports 5381/9781 (use a **separate copy** of the app so
the two versions do not share `.web`).

Observed on **both** versions:
* `charts_the_plot_by_id: False`, `charts_plotly_rendered: 1`, `charts_any_divid_attr: 0`,
  `control-box` present → R-6.
* `dyn_window_reflex_keys` = `['react','@emotion/react','$/utils/context','$/utils/state','@radix-ui/themes']`
  (no `lucide-react`), `dyn_icon_rendered: False`, `dyn_label_text: None`, one failed request to
  the malformed jsDelivr URL → R-4; the server log carries the two frontend exceptions
  (`logs/rvapp_a1_dev.trimmed.log`, `logs/rvapp_0910_dev.trimmed.log`).
* bg `on_load`: staying on `/slowbg` → all 5 entries; navigating away right after the first entry
  → **no further entries 6 s later**; the identical button-started task survives navigation
  (`shots/{a1,base0910}/A_control.png`, `B_after_nav.png`, `C_button.png`) → item 8.

### 1 — FINDING-013, strict JSON-lines

```bash
cd $SB/apps/rvapp
REFLEX_TELEMETRY_ENABLED=false $SB/envs/a1/bin/reflex run --json --loglevel debug \
  --frontend-port 5380 --backend-port 9780 > $DIR/logs/a1_json_debug.stdout 2>$DIR/logs/a1_json_debug.stderr &
# wait for 200, kill it, then:
cd $DIR && $SB/envs/a1/bin/python repros/check_jsonlines.py logs/a1_json_debug.stdout
#  -> total=98 json_ok=90 non_json=8   ([INFO] Starting granian / Listening at / Spawning worker-1 /
#     Started worker-1 / Shutting down granian / Stopping|Stopped worker-1 / Granian shutdown completed)
```
Baseline: same with `$SB/envs/b0910` on 5381/9781 → `total=102 json_ok=94 non_json=8`
(`logs/base0910_json_debug.stdout`).

### FINDING-005 / FINDING-004 sweep (backend-only, no browser)

```bash
cd $SB/apps/rvapp
REFLEX_TELEMETRY_ENABLED=false REFLEX_ENABLE_FULL_LOGGING=1 REFLEX_LOG_FILE=$DIR/logs/a1_full.log \
  $SB/envs/a1/bin/reflex run --backend-only --backend-port 9786 --loglevel info > $DIR/logs/a1_backend_full.stdout 2>&1 &
cd $DIR
$SB/envs/driver/bin/python repros/sweep_client_error.py http://localhost:9786
$SB/envs/driver/bin/python repros/sweep_dispatch.py     http://localhost:9786 \
    'reflex___state____state.rvapp___rvapp____bg_state.do_log'
grep -cE 'missing 1 required positional|Task exception was never retrieved' logs/a1_backend_full.stdout   # 0
grep -ci 'malformed client_error' logs/a1_full.log                                                        # 5
grep -c  'worker console.info from event handler\|worker hierarchy logger record' logs/a1_full.log         # 6
grep -cE '^\[[0-9]{4}-[0-9]{2}-[0-9]{2} ' logs/a1_backend_full.stdout                                     # 0 (no leaked file copies)
```
Add `--json` for the purity check → `logs/a1_backend_full_json.stdout` is 16/16 valid JSON and
`logs/a1_full_json.log` still holds the 6 worker records.

### 5 — FINDING-018, npm/bun lockfile switch

`fakenode/node` is a shim that answers `--version` with `v22.12.0` (below the 22.22.0 floor) and
execs the real node otherwise.

```bash
mkdir -p $SB/apps/npmapp2 && cd $SB/apps/npmapp2
REFLEX_TELEMETRY_ENABLED=false $SB/envs/a1/bin/reflex init --template blank
# run 1: normal (bun) run -> creates .web/bun.lock + reflex.lock/{bun.lock,package.json}; kill it
REFLEX_TELEMETRY_ENABLED=false $SB/envs/a1/bin/reflex run --frontend-port 5382 --backend-port 9782 &
# run 2: npm + old-node shim -> must fail fast
PATH=$DIR/fakenode:$PATH REFLEX_USE_NPM=1 REFLEX_TELEMETRY_ENABLED=false timeout 180 \
  $SB/envs/a1/bin/reflex run --frontend-port 5382 --backend-port 9782      # exit 1 after ~8 s
ls reflex.lock/     # bun.lock + package-lock.json + caret-rewritten package.json  (R-5)
# run 3: plain run again
REFLEX_TELEMETRY_ENABLED=false $SB/envs/a1/bin/reflex run --frontend-port 5382 --backend-port 9782 &
curl --noproxy '*' -o /dev/null -w '%{http_code}\n' http://localhost:5382/    # 200 -> FINDING-018 gone
ps -eo args | grep -E 'npm run dev|bun run dev'                               # bun run dev here
```
The npm-**first** variant (no successful bun run before the failed npm run) leaves the project on
npm permanently: `apps/npmapp` (0.9.11a1) and `apps/npmapp4` (0.9.10.post2) both show `npm run dev`
on the next plain run with nothing in the log (`evidence/npm_recovery_pm.txt`,
`logs/npm_oldnode_a1.log`, `logs/npm4_run1_npmfail.log`, `logs/npm4_run2_plain.log`).
Lockfile evidence and the exact pin diff: `evidence/lockfile_state.txt`,
`evidence/npm2_pkgjson_after_{bun,npm}.json`.

### 8 documentation check

```bash
git show origin/r/pre-2026.09.10-34457666442:CHANGELOG.md | grep -n '6593'
```
→ "Stale `on_load` work no longer blocks or outlives a page navigation: … **including `on_load`
handlers that are background tasks (`@rx.event(background=True)`), which 0.9.8 let run to
completion**. Background tasks started from other events are unaffected." The behaviour is
therefore intentional and documented in the changelog; nothing under `docs/` mentions it
(`grep -rn 'cancels the previous page' docs/` → no match), so the reference docs for
`on_load`/background tasks still do not warn about it.

### A-1 / A-2 shutdown probe

```bash
bash repros/shutdown_probe.sh $SB/envs/a1/bin/reflex    $SB/apps/rvapp     5380 9780 a1        $DIR/logs TERM
bash repros/shutdown_probe.sh $SB/envs/b0910/bin/reflex $SB/apps/rvapp0910 5381 9781 base0910  $DIR/logs TERM
# ... and again with INT
```
Captured: `logs/shutdown_a1.log`, `logs/shutdown_a1_int.log`, `logs/shutdown_base0910.log`,
`logs/shutdown_base0910_int.log`.

## Files

```
apps/rvapp/                  live app (4 pages) used for items 4, 6, 8 and the logging sweep
harness/{conftest,test_harness}.py   FINDING-016 pytest (dev + prod AppHarness, port-pinned)
repros/probe_offline.py      one-shot offline probe for items 1–2,4,6,7 + most of the sweep
repros/drive_charts_dyn.py   /charts + /dyn Playwright driver (id prop, bundled libs)
repros/drive_bg_onload.py    background-task on_load navigation driver (from the 0.9.9a1 campaign)
repros/check_jsonlines.py    strict JSON-lines validator (from the 0.9.9a1 campaign)
repros/sweep_client_error.py python-socketio no-arg client_error probe (from the a2 re-verify)
repros/sweep_dispatch.py     dispatches a worker-side event to force worker logging
repros/shutdown_probe.sh     SIGTERM/SIGINT shutdown timing probe
fakenode/node                node shim reporting v22.12.0
logs/, shots/, evidence/     captured output, screenshots, lockfile + version evidence
```

## VERIFICATION: AttributeError raised inside a cached var computation is still masked as 'Attribute _cached_get_all_var_data not found' (no __cause__)

**Verdict: CONFIRMED — genuine defect, pre-existing (NOT a regression), severity MEDIUM.**
Independently reproduced by a second agent from the written repro alone, and then
*strengthened*: the claimant only showed it via a hand-written `CachedVarOperation`
subclass (internal API). It also fires on a **100% public-API path** — an ordinary
`@rx.serializer` with a typo — and the misleading message is what `reflex export` /
`reflex run` print to the user, exit 1.

### Environment

* `$SB/envs/smoke` = reflex 0.9.11a1 / reflex-base 0.9.11a1 (Python 3.11)
* `$SB/envs/base0910` = reflex 0.9.10.post2 (baseline)
* cwd for every run: `$SB/apps/verify2_reverify_prev_0/` (never the checkout); each script
  asserts `"/envs/" in reflex.__file__`.

### Commands (rerunnable verbatim)

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
D=$SB/apps/verify2_reverify_prev_0

# 1) matrix probe (cases A/B/C/C2 + controls D/F), both versions
cd $D && $SB/envs/smoke/bin/python     verify_cachedvar_mask.py   # -> verify_0911a1.log
cd $D && $SB/envs/base0910/bin/python  verify_cachedvar_mask.py   # -> verify_0910post2.log

# 2) end-to-end: real app, real compile path, both versions
cd $D/e2e_app && REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/python    compile_probe.py
cd $D/e2e_app && REFLEX_TELEMETRY_ENABLED=false $SB/envs/base0910/bin/python compile_probe.py

# 3) end-to-end via the real CLI (0.9.11a1)
cd $D/e2e_app && REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex export --frontend-only --no-zip --loglevel info
```

### Results matrix (identical on 0.9.11a1 and 0.9.10.post2)

| case | what raises `AttributeError("… the_real_problem")` | observed exception | `__cause__` / `__context__` | real cause anywhere in traceback? |
|---|---|---|---|---|
| A | `CachedVarOperation._cached_get_all_var_data` (claimant's repro) | `VarAttributeError: Attribute _cached_get_all_var_data not found.` | None / None | **no** |
| B | `CachedVarOperation._cached_var_name` | `VarAttributeError: Attribute _cached_var_name not found.` | None / None | **no** |
| C | **public API**: user `@rx.serializer` raising `AttributeError`, reached lazily from `LiteralArrayVar._cached_var_name` via `str(rx.Var.create([Thing()]))` | `VarAttributeError: Attribute _cached_var_name not found.` | None / None | **no** |
| C2 | same serializer through `rx.text(..., custom_attrs=...).render()` | `VarAttributeError: Attribute _cached_var_name not found.` | None / None | **no** |
| D | control — same serializer reached **eagerly** (`str(rx.Var.create(Thing()))`) | `AttributeError: type object 'Reflex' has no attribute 'the_real_problem'` | — | **yes** |
| F | control — `ValueError` (not `AttributeError`) raised in the same cached property | `ValueError: … the_real_problem` | — | **yes** |

Controls D and F pin the mechanism precisely: only `AttributeError`, and only when raised
*inside a cached property of a `Var` subclass*, is destroyed.

### End-to-end (the part that makes this user-facing, not academic)

`verification/F024_e2e_badser_app/` is a 20-line app whose only bug is a one-character
serializer typo:

```python
@rx.serializer
def serialize_point(p: Point) -> str:
    return f"{p.x},{p.why}"      # Point has .y, not .why
```

`reflex export --frontend-only --no-zip` (and `app._compile()`) exits 1 with:

```
  File ".../reflex/compiler/plugins/memoize.py", line 189, in _should_memoize
    var_data = prop_var._get_all_var_data()
  File ".../reflex_base/vars/base.py", line 2128, in _get_all_var_data
    return self._cached_get_all_var_data
  File ".../reflex_base/vars/base.py", line 2120, in __getattr__
    return next_class.__getattr__(self, name)
  File ".../reflex_base/vars/base.py", line 1471, in __getattr__
    raise VarAttributeError(msg)
reflex_base.utils.exceptions.VarAttributeError: Attribute _cached_get_all_var_data not found.
```

`grep -c "serialize_point\|p.why" export_0911a1.log` -> **0**. The user's own module is not
named anywhere in the traceback, and the message points at a framework attribute that *does*
exist. Identical output on 0.9.10.post2 (`F024_e2e_compile_probe_0910post2.log`).

### Mechanism (file:line — wheel line numbers, identical in the checkout's
`packages/reflex-base/src/reflex_base/vars/base.py`)

1. `reflex_base/vars/base.py:1998` `class cached_property` — reflex's own descriptor;
   `cached_property_no_lock = cached_property` at :2079.
2. `:2075` `GLOBAL_CACHE[unique_id] = self._func(instance)` — the computation runs inside
   `cached_property.__get__`, so an `AttributeError` it raises leaves `__getattribute__`
   as an `AttributeError`.
3. CPython's attribute protocol (`slot_tp_getattr_hook`) treats that as "attribute missing",
   calls `PyErr_Clear()`, and falls through to `__getattr__`. The clear is why there is no
   `__cause__` **and** no `__context__`.
4. `CachedVarOperation.__getattr__` `:2104-2120` forwards to the next class in the MRO ->
   `Var.__getattr__` `:1456`, which at `:1470-1471` raises
   `VarAttributeError(f"Attribute {name} not found.")` for any `_`-prefixed name.

Scope: 23 `@cached_property_no_lock` decorations in the published `reflex_base` + `reflex`
(`vars/base.py`, `vars/sequence.py`, `vars/object.py`, `vars/function.py`, `vars/color.py`,
`components/component.py`, `reflex/istate/data.py`). The masking is specific to **`Var`
subclasses**, because only they define `__getattr__`; `Component` defines none, so an
`AttributeError` in *its* cached properties propagates intact (verified: no
`def __getattr__` in `reflex_base/components/component.py`). No CLI layer catches
`VarAttributeError` to re-surface a cause (`grep VarAttributeError` over `reflex/` +
`reflex_base/` outside `vars/` and `exceptions.py`: no hits).

### Refutations attempted and rejected

* **Environment quirk / proxy / ports / cwd shadowing** — no. Pure in-process Python, no
  network, no server; every script asserts it imported reflex from `$SB/envs/...`.
* **Internal-API misuse (subclassing `CachedVarOperation` is not public)** — rejected. Cases
  C, C2 and the end-to-end app use only `@rx.serializer`, `rx.Var.create`, `rx.box(custom_attrs=)`
  and `reflex export`.
* **Regression in 0.9.11a1** — rejected. 0.9.10.post2 is byte-for-byte the same behaviour in
  all six cases (`verify_F024_cachedvar_mask_0910post2.log`,
  `F024_e2e_compile_probe_0910post2.log`). Claimant's `regression=false` is correct.
* **Demo/example-app bug** — no; the app is a minimal purpose-built repro, the defect is in
  `reflex-base`.
* **Flaky** — no; deterministic, 2/2 versions x 2 runs.
* **Documented behaviour** — nothing documents it; the message actively misdirects (it names
  an attribute that exists).

### Severity / impact judgement (independent)

MEDIUM, agreeing with the claimant. It never breaks working code — the app was already
going to fail — but it converts *any* `AttributeError` in a var computation (user serializer,
user `ObjectVar` annotation mistake, a reflex or reflex-enterprise internal rename) into an
error that names neither the user's file nor the real attribute. That is exactly what made the
0.9.9a1 enterprise breakage undebuggable, so it is a force multiplier on every future
regression. Not a release blocker for 0.9.11a1 (pre-existing, no functional change), but worth
fixing: in `cached_property.__get__` (`vars/base.py:2075`) wrap the call and re-raise a
non-`AttributeError` chained from the original, e.g.

```python
try:
    GLOBAL_CACHE[unique_id] = self._func(instance)
except AttributeError as e:
    msg = f"Error computing cached property {self._attrname!r} of {type(instance).__name__}"
    raise VarValueError(msg) from e   # any non-AttributeError keeps __getattr__ out of it
```

Downstream: `downstream=false` (nothing downstream is broken *by* this), but note
reflex-enterprise is the most likely consumer to be hurt by the lost diagnostics.

### Evidence paths

* `verification/verify_F024_cachedvar_mask.py` — the 6-case matrix probe
* `verification/verify_F024_cachedvar_mask_0911a1.log`, `..._0910post2.log`
* `verification/F024_e2e_badser_app/` — minimal public-API app (`rxconfig.py`,
  `badser/badser.py`, `compile_probe.py`)
* `verification/F024_e2e_compile_probe_0911a1.log`, `..._0910post2.log`
* `verification/F024_e2e_reflex_export_0911a1.log` — real CLI, exit 1
* Claimant's originals: `logs/probe_offline_0911a1.log` (F024 block),
  `logs/probe_offline_0910.log`, `repros/probe_offline.py`

Processes started: none long-lived (one `reflex export` that exited on its own). Verified
`ps aux | grep -E 'reflex|vite|granian|bun|chrom'` shows only another agent's `mht_a1`
dev server on ports 5420/9820, untouched.

## VERIFICATION: Module-scope bundle_library() is discarded and subpath imports of a bundled library are never rewritten, so dynamic components containing rx.icon silently never render

Independent adversarial re-verification (second verifier, own venvs/ports/app, repro rebuilt
from the written description only). **Verdict: CONFIRMED — genuine framework defect, but the
claim is framed too narrowly and the load-bearing half is not the `bundle_library()` half.**

* `confirmed = true`, `severity = medium`, `regression = false` (0.9.10.post2 identical, run
  myself, dev *and* offline), `downstream = false` for release purposes (pre-existing; not a
  0.9.11a1 blocker) — with the caveat that the bug is in a mechanism reflex-enterprise builds
  on (`ImportVar.package_path`, see "blast radius" below).

### What is actually broken (narrower and broader than the claim)

The defect is in the **dynamic-component serializer's handling of `ImportVar.package_path`**,
and it needs **no `bundle_library()` call and no user mistake at all**: any computed
`rx.Component` var (dynamic component) that contains a component whose import carries a
subpath emits an import statement the browser cannot use, and the *whole* dynamic block is
then silently dropped — `rx.icon` is the everyday case.

Both branches of the rewrite are wrong, and one of the two is fully environment-independent:

| library bundled at serialization time? | emitted import | browser result |
|---|---|---|
| no | `import LucideApple from "https://cdn.jsdelivr.net/npm/lucide-react@1.26.0/+esm/dist/esm/icons/apple.mjs"` | jsDelivr's terminal `+esm` marker ends up mid-path; fetch of the dynamic module fails (`Failed to fetch dynamically imported module`) |
| yes | `import LucideApple from "lucide-react/dist/esm/icons/apple.mjs"` | `TypeError: Failed to resolve module specifier "lucide-react/dist/esm/icons/apple.mjs"` — **no network involved**, so this is not a sandbox artifact |

### Refutation attempts, and what survived

1. **"It is API misuse — module-scope `bundle_library()` is not the supported way to bundle a
   library."** Partly fair (the claim's part (a) is real: `compile_app()` calls
   `reset_bundled_libraries()` *after* the app module has been imported, so the user's call is
   wiped and `window.__reflex` never gets the lib — no warning). But it does **not** save the
   feature: I re-ran the same app declaring `lucide-react` through the *supported* compiler
   plugin hook `get_frontend_dependencies()` (`rxconfig.py`, `REPRO_PLUGIN=1`), in **prod**,
   where compile and serving are the same process. `window.__reflex` then really does hold
   `lucide-react` (`typeof window.__reflex['lucide-react'] === 'object'`, exports
   `AArrowDown, …, Apple`), and the dynamic block **still never renders**, now with the
   purely client-side resolve error and **zero CDN traffic**. So the defect is independent of
   `bundle_library()` and of this sandbox's blocked jsDelivr egress.
2. **"Blocked jsDelivr egress in this sandbox is what breaks it."** Refuted for the bundled
   case (above: no network at all). Honest limitation for the *unbundled* case: jsDelivr is
   403-blocked by the egress proxy here (`curl https://cdn.jsdelivr.net/... ` → CONNECT 403),
   so I could only observe `ERR_TUNNEL_CONNECTION_FAILED`; that the URL itself is malformed is
   established from the source (`get_cdn_url()` appends `/+esm`, then `compile_imports()`
   concatenates the subpath after it) and from reflex's own convention that `+esm` is the last
   path segment.
3. **"Dynamic components are simply broken/unused here."** Refuted by a control on the same
   page set: `/ctl` renders a dynamic block built only from `rx.el` elements (no third-party
   import), it renders and live-updates on click, clean console, in dev **and** prod.
   `/mix` is the *same* block plus exactly one `rx.icon("apple")` → the icon, the box and the
   label are all absent, before and after the click. One added icon deletes the whole block.
4. **"The subpath import is just unsupported everywhere."** Refuted: on `/dyn` the *static*
   `rx.icon("banana")` (`#static-icon`) renders fine in the same page — the normal
   bun/vite compile path resolves the deep import; only the dynamic-component serializer
   cannot.
5. **"Dev-only."** Refuted: prod (`reflex run --env prod`, single port) fails the same way.
6. **"Regression in 0.9.11a1."** Refuted, agreeing with the claimant: byte-identical emitted
   imports on 0.9.10.post2 (offline probe) and the same end-to-end failure with the same
   browser error on 0.9.10.post2 in dev. `reflex-components-lucide` is 1.0.4 in both envs; the
   deep per-icon import landed in #6628, before 0.9.10.
7. **Flakiness.** Every run reproduced first try; 6 runs total (3 versions/modes × pages).

### Mechanism (release branch `origin/r/pre-2026.09.10-34457666442`, line numbers verified against the installed wheel)

* `packages/reflex-base/src/reflex_base/components/dynamic.py:146` — the CDN/window decision
  is made on the **library key only** (`format_library_name(lib)`), which knows nothing about
  `ImportVar.package_path`.
* `.../dynamic.py:148` + `:69` — unbundled case: `imports[get_cdn_url(lib)] = names` produces
  `https://cdn.jsdelivr.net/npm/<lib>/+esm`, and then
  `reflex/compiler/utils.py:156` (`formatted_lib = format.format_library_name(lib) + (path if
  path != "/" else "")`) concatenates the `package_path` **after** `+esm`
  (`format_library_name` returns an `https://` string unchanged), yielding
  `…/lucide-react@1.26.0/+esm/dist/esm/icons/apple.mjs`.
* `.../dynamic.py:170` — bundled case: the window-rewrite loop tests
  `if f'from "{lib}"' in line`, i.e. it requires the *closing quote* right after the library
  name, so `from "lucide-react/dist/esm/icons/apple.mjs"` never matches and the bare
  specifier is shipped verbatim.
* `reflex/compiler/compiler.py:1212` — `reset_bundled_libraries()` inside `compile_app()`
  (after app-module import) is the claim's part (a); `:1217-1219` then re-bundles only
  plugin `get_frontend_dependencies()`.
* Extra facet found while verifying (same root cause, not in the claim): in **dev** the
  serving granian worker never runs the full-compile path, so its registry holds only the four
  defaults — no plugin libraries either. The same computed var is therefore serialized two
  different ways in one run; decoded from the log with `decode_modules.py`:
  module #1 (worker) `import {Flex…} from "https://cdn.jsdelivr.net/npm/@radix-ui/themes@3.3.0/+esm"`,
  module #2 (compile process) `const {Flex: RadixThemesFlex,…} = window.__reflex['@radix-ui/themes']`.
  So in dev a dynamic component silently pulls a **second copy of Radix Themes from jsDelivr**
  at runtime (broken Theme context, extra network dependency) even with no user error.
* Blast radius beyond icons (code inspection): `reflex_components_plotly/plotly.py:359`
  (`package_path="/factory"`) and, downstream, `reflex_enterprise/components/highcharts/base.py`
  (`package_path` `"/"`, `"/Stock"`, `"/Maps"`, `"/Gantt"`). A synthetic component with
  `ImportVar(..., package_path="/sub/mod.mjs")` reproduces both bad forms (`probe_offline.py`
  case F), so the defect is general to `package_path`, not lucide-specific.
* A fix is available in-place: `window.__reflex['lucide-react'].Apple` exists (checked in the
  browser), so a bundled subpath import can be rewritten to a barrel destructure; the CDN form
  needs `+esm` moved to the end (`…/lucide-react@1.26.0/dist/esm/icons/apple.mjs/+esm`).

### Exact commands (my own working dir, ports 6084-6087 / 10484-10487)

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
V=/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/reverify_prev/verification/F022_dynamic_subpath_imports
W=$SB/apps/verify2_reverify_prev_1                 # neutral cwd, never /home/user/reflex

# 1. offline, no server: what the serializer emits (asserts reflex.__file__ is in a venv)
cd $W && $SB/envs/smoke/bin/python probe_offline.py     # -> logs/probe_offline_0911a1.log
cd $W && $SB/envs/base0910/bin/python probe_offline.py  # -> logs/probe_offline_base0910.log
cd $W && $SB/envs/smoke/bin/python probe_subpath_blast.py

# 2. end to end, dev, 0.9.11a1, nothing bundled by the app
cp -r $V/app $W/dynmin && cd $W/dynmin
REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex run \
  --frontend-port 6084 --backend-port 10484 --loglevel info > $W/logs/dynmin_a1_nobundle.log 2>&1 &
cd $W && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python \
  /home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py \
  http://localhost:6084/mix --actions actions_mix.json --report logs/a1_nobundle_mix.json
#   -> [mix-icon, mix-box, mix-label] = [False, False, None] before and after the click,
#      one failed request: .../lucide-react@1.26.0/+esm/dist/esm/icons/apple.mjs
#   control: same driver on /ctl with actions_ctl.json -> [True, 'ctl-label: clicked'], "clean"

# 3. same, with bundle_library() at module import  (dev, 6085/10485)
REPRO_BUNDLE=1 ... reflex run --frontend-port 6085 --backend-port 10485
#   -> server log: TypeError: Failed to resolve module specifier
#      "lucide-react/dist/esm/icons/apple.mjs"   (no network involved)

# 4. baseline 0.9.10.post2, same app, separate copy so .web is not shared (6086/10486)
REPRO_BUNDLE=1 $SB/envs/base0910/bin/reflex run --frontend-port 6086 --backend-port 10486
#   -> identical: block absent, identical resolve error + identical malformed CDN URL

# 5. prod, and the SUPPORTED plugin route (6087 for both ports)
REPRO_BUNDLE=1 $SB/envs/smoke/bin/reflex run --env prod --frontend-port 6087 --backend-port 6087
REPRO_PLUGIN=1 $SB/envs/smoke/bin/reflex run --env prod --frontend-port 6087 --backend-port 6087
#   plugin run: window.__reflex keys include 'lucide-react', /dyn -> static-icon True,
#   dyn-icon False, dyn-label False; /mix block absent; only the resolve error, no CDN request

# 6. decode the modules the server log echoes back
cd $W && $SB/envs/driver/bin/python decode_modules.py logs/dynmin_a1_nobundle.log
```

### Evidence paths

* `verification/F022_dynamic_subpath_imports/app/` — minimal app (3 pages, 3 env-selected
  variants incl. the plugin route in `rxconfig.py`)
* `verification/F022_dynamic_subpath_imports/probe_offline.py` (cases A–F),
  `probe_subpath_blast.py`, `decode_modules.py`
* `.../logs/probe_offline_0911a1.log`, `.../logs/probe_offline_base0910.log` — emitted imports,
  both versions
* `.../logs/dynmin_a1_nobundle.log`, `dynmin_a1_bundle.log`, `dynmin_0910_bundle.log`,
  `dynmin_a1_prod_bundle.log`, `dynmin_a1_prod_plugin.log` — server logs with the forwarded
  frontend exceptions
* `.../logs/a1_nobundle_{dyn,ctl,mix}.json`, `a1_bundle_mix.json`, `b0910_bundle_mix.json`,
  `a1_prod_mix.json`, `a1_prod_plugin_{mix,dyn}.json` — driver reports (console, failed
  requests, per-action evals) and the `actions_*.json` used
* `.../shots/a1_nobundle_{ctl,mix,dyn_initial,dyn_after_click}.png`,
  `a1_prod_{ctl,bundle_mix,plugin_mix,plugin_dyn}.png`, `b0910_bundle_mix.png`

### Assessment

Keep it open as a real defect worth fixing, at **medium** severity: total, silent loss of a
dynamic component (no browser-visible error — only "Failed to load resource" — while the
backend log carries the real exception), triggered by `rx.icon`, which is about the most
common component there is; affects dev and prod; no user workaround, since the supported
plugin route fails too. It is **not** a 0.9.11a1 release blocker: pre-existing and unchanged
since at least 0.9.10.post2. The claimant's severity/regression/downstream judgments all hold;
only the title should be re-pointed at `ImportVar.package_path` handling in
`load_dynamic_serializer().make_component`, since the `bundle_library()` framing suggests a
workaround that does not exist.

Processes: dev/prod servers on 6084-6087 and 10484-10486 plus their bun/vite children, all
killed; verified `ps aux | grep -E 'reflex|vite|granian|bun|chrom'` shows nothing of mine and
all 8 reserved ports refuse connections. Another agent's `mht_a1` prod server on 5430 was left
untouched.
