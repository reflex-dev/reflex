# Cluster: config_assets_cli — CLI startup, frontend reinstall avoidance, version-check cache, rxconfig loading, telemetry context, frontend_path, shared assets

Second pass over this cluster. The first pass is preserved as `NOTES.first-pass.md` with its
scripts (`race_assets.py`, `race_assets2.py`) and app (`sharedasset/`); it covered the `#7039`
stale-link half and a top-level CLI timing table. Everything below is new work; the first pass's
conclusions are folded in and independently re-verified here.

All installs are PyPI-only in isolated uv venvs. Every python/CLI invocation below runs from an
app dir under `$SB/apps/config_assets_cli/`, never from the checkout; every repro script starts
with `assert "/envs/" in reflex.__file__`.

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
$SB/envs/smoke        reflex 0.9.11a1                     (reflex-base 0.9.11a1)
$SB/envs/base0910     reflex 0.9.10.post2                 (baseline)
$SB/envs/cac_db_a1    reflex[db]==0.9.11a1                (made here)
$SB/envs/cac_db_0910  reflex[db]==0.9.10.post2            (made here)
$SB/envs/cac_nohost   reflex==0.9.11a1, hosting CLI removed
$SB/envs/cac_nohost_0910  reflex==0.9.10.post2, hosting CLI removed
$SB/envs/cac_comp / cac_comp_0910   uv venv --seed (has pip) + build/twine, for `reflex component`
$SB/envs/cac_plotly   reflex 0.9.11a1 + reflex-components-plotly 0.9.6a1 + plotly
```

Ports used: frontend 5300/5301/5302, backend 9700/9701/9702, dead-proxy port 9719. All inside the
assigned ranges; nothing left running (verified with `ps`).

---

## Results table

| # | Check | Result |
| --- | --- | --- |
| 1a | CLI startup timings, plain install, 6 commands | pass — ~2.1x faster on 0.9.11a1 |
| 1b | CLI startup timings with `reflex[db]` installed | pass — **5.3x** faster (0.89 s → 0.17 s) |
| 1c | `import reflex` pulls in no sqlalchemy/sqlmodel/plugins/compiler modules | pass (both versions) |
| 1d | `reflex_base.utils.types` no longer imports sqlalchemy at import time | pass — 123 sqlalchemy modules on 0.9.10.post2, 0 on 0.9.11a1 |
| 1e | `rx.plugins.*` still resolve after lazy loading | pass — all 19 names resolve |
| 1f | `reflex component init` + `component build` through the lazy proxy | pass with defects (ISSUE-3, ISSUE-6) |
| 1g | `reflex deploy` / `cloud apps list` with reflex-hosting-cli uninstalled | pass — names the package, exit 1 |
| 1h | lazy proxy: nested help, bad flag, unknown subcommand, shell completion | pass |
| 2a | run app → stop → change ONLY backend config → rerun: no reinstall | **FAIL** — reinstall happens (ISSUE-1) |
| 2b | same, once the install cache is not spuriously invalidated | pass — cache hit, no `bun add` |
| 2c | add a component with a new npm dep (`rx.plotly`) → must reinstall | pass — `react-plotly.js`, `plotly.js` added |
| 2d | add a plugin (`TailwindV4Plugin`) → must reinstall what it needs | pass — tailwindcss + @tailwindcss/{postcss,typography} |
| 2e | 0.9.10.post2 baseline for 2a/2b | fails too (config JSON was in the fingerprint) |
| 3a | version-check cache location + knob | pass — `<app>/.web/reflex.json`, `REFLEX_CHECK_LATEST_VERSION` (**not** platformdirs) |
| 3b | second CLI run makes no PyPI request | pass — `reflex run` #1 hits pypi.org once, #2..n zero |
| 3c | dead proxy + fresh success timestamp → no request at all | pass — 0.000 s, no keys touched |
| 3d | failed check records the 1-hour throttle | pass — only `last_version_check_attempt_datetime` written |
| 3e | throttle actually suppresses the next check | pass |
| 3f | per-package keys (`reflex-hosting-cli`) | pass |
| 3g | 0.9.10.post2 baseline | requests PyPI on **every** invocation (~0.24 s each) |
| 4a | `_load_config()` emits a deprecation naming the replacement | pass (both versions; console, not `warnings`) |
| 4b | 16 threads × `get_config()`/`reload_config()`/mixed, rxconfig imports a sibling | pass — 0 errors, both versions |
| 4c | 8 loader threads vs 8 threads plainly importing the sibling, 40 rounds | pass — 0 errors, both versions |
| 4d | #6933 changelog attribution | anomaly — already shipped in 0.9.9.post1/0.9.10.post1 (ISSUE-5) |
| 5 | #6960 telemetry worker no longer re-imports rxconfig off-thread | pass — reproduced independently |
| 6a | `frontend_path` `'../x'`, `'a\b'`, `'C:foo'` rejected with a clear message | pass (0.9.10.post2 accepted all) |
| 6b | `frontend_path='//x'` / `'/a//b'` (empty segment) | anomaly — still accepted (ISSUE-4) |
| 6c | `frontend_path=/myapp` + `REFLEX_SSR=false` + `reflex export` | pass — 0.9.10.post2 raises `FileNotFoundError`, 0.9.11a1 succeeds |
| 6d | same with SSR on | pass on both |
| 6e | prod `reflex run` under `/myapp`, driven in a browser | covered by the `frontend_path_ssr` cluster; not duplicated |
| 7a | stale `assets/external/<link>` pointing at the wrong file is repointed | pass — 0.9.10.post2 keeps the wrong file |
| 7b | dangling symlink / symlink loop / plain file at the link path | pass — all replaced (0.9.10.post2 keeps a plain file) |
| 7c | directory at the link path | anomaly — traceback on both versions, different message |
| 7d | 4 concurrent `reflex compile` in one app dir, 5 trials | **FAIL** — 4/20 aborted (ISSUE-2) |
| 7e | same, with the install cache alive | pass — 24/24 clean, links always correct |
| 7f | 4 concurrent `reflex export --frontend-only --no-zip`, 4 trials | **FAIL** — 3/16 aborted (ISSUE-2) |
| 7g | 0.9.10.post2 baseline for 7d/7f | worse — 4/20 and 8/16 aborted |
| 7h | shared assets served and used in a real browser | pass — clean console, 200s |

---

## ISSUE-1 (medium, pre-existing, not a regression) — the frontend-package install cache is invalidated on every run, so `bun add` re-runs on every `reflex run` / `compile` / `export`

The 0.9.11a1 changelog says #7050 will "avoid frontend package reinstalls after backend-only
config changes". As a user would test it, it does not:

```
cd $SB/apps/config_assets_cli/cliapp
REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex run --frontend-port 5300 --backend-port 9700 --loglevel debug   # run 1
#   -> "Debug: Installing frontend packages"        (expected, first run)
# stop it, edit ONLY backend knobs in rxconfig.py (backend_host / cors_allowed_origins / telemetry_enabled)
REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex run --frontend-port 5300 --backend-port 9700 --loglevel debug   # run 2
#   -> "Debug: Installing frontend packages"        AGAIN
```

Evidence: `logs/run1_a1.log` line 177, `logs/run2_a1_backendcfg.log` line 108. It is not the
config change: three consecutive `reflex compile` runs with **no** change at all reinstall too
(`logs/compile_1.log`, `logs/compile_2.log`, `logs/compile_3.log`, each with
`Using cached value for _install_frontend_packages` count 0).

Root cause, verified: `reflex/utils/js_runtimes.py::_sync_root_lockfiles_for_frontend_install()`
deletes `.web/reflex.install_frontend_packages.cached` whenever
`frontend_skeleton.sync_root_lockfiles_to_web()` reports a change, and
`sync_root_package_json_to_web()` always reports one — it compares `.web/package.json` against
`_compile_package_json()`, which renders **compact** JSON, while `bun add` rewrites
`.web/package.json` **pretty-printed** (2-space indent). Same bytes, different formatting:

```
cd $SB/apps/config_assets_cli/cliapp
$SB/envs/smoke/bin/python - <<'PY'
from pathlib import Path
from reflex.utils import frontend_skeleton as fs
print("identical:", Path(".web/package.json").read_text() == fs._compile_package_json())   # -> False
PY
```

So each run: sync rewrites the file compact and drops the cache → `bun add` runs → bun leaves the
file pretty → next run drops the cache again. Proof of causation — normalise the file and the very
next compile hits the cache and skips the install entirely:

```
cd $SB/apps/config_assets_cli/cliapp
$SB/envs/smoke/bin/python $SB/apps/config_assets_cli/scripts/normalize_pkgjson.py
REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex compile --loglevel debug | grep "Using cached value for _install_frontend_packages"
```
(`logs/compile_normalized.log`: cache hit 1, "Installing frontend packages" 0.)

With the cache alive, the #7050 improvement is real and observable: a backend-only config change
keeps the cache hit on 0.9.11a1 (`logs/compile_a1_backendonly.log`), because the fingerprint no
longer contains `config.json()` — 0.9.10.post2's fingerprint did
(`.web/reflex.install_frontend_packages.cached` on `cliapp_base` embeds the whole config JSON).

Cost here is small (~25 ms of warm-cache `bun add` per invocation) but it is a real package-manager
run on every CLI invocation — on a cold machine, in CI, or behind a slow registry that is a network
round trip per `reflex run`, and it is what makes ISSUE-2 happen.

Regression: **no** — 0.9.10.post2 behaves the same (`logs/compile_base_1..3.log`,
`logs/compile_base_control*.log`; on that version the cache never hit in any configuration I could
construct). Downstream: no, this is `reflex` itself.

## ISSUE-2 (medium, pre-existing, not a regression) — compiling/exporting one app dir from several processes still aborts

#7039's changelog says: "Compiling an app from several processes against one working directory —
pytest-xdist workers, parallel builds, or containers sharing a bind mount — no longer aborts with
FileNotFoundError or FileExistsError while linking a `rx.asset(shared=True)` file". The asset link
step is indeed fixed (see 7a/7e), but the overall scenario still aborts, one step later.

```
cd $SB/apps/config_assets_cli
bash scripts/concurrent_cli.sh $SB/envs/smoke/bin/reflex $PWD/sharedapp $PWD/logs/conc TAG 4 5 compile
bash scripts/concurrent_cli.sh $SB/envs/smoke/bin/reflex $PWD/sharedapp $PWD/logs/conc TAG2 4 4 export --frontend-only --no-zip
```

| version | 4×`reflex compile`, 5 trials | 4×`reflex export --frontend-only --no-zip`, 4 trials |
| --- | --- | --- |
| 0.9.11a1 | 4/20 aborted | 3/16 aborted |
| 0.9.10.post2 | 4/20 aborted | 8/16 aborted |
| 0.9.11a1, install cache alive | **0/24 aborted** | — |

Two distinct causes, neither of them the shared asset:

* `bun add`/`bun install` from four processes into one `.web/node_modules`:
  `error: Failed to link semver: EEXIST` (etc.), reported by reflex as
  `Installing frontend development dependencies failed with exit code 1`.
  Logs: `logs/conc/concurrent_compile_a1_t3_w1.log`, `..._t3_w3.log`.
  **This only happens because of ISSUE-1** — with the install cache alive, no worker runs bun and
  24/24 concurrent compiles are clean (`logs/conc/CLEAN_concurrent_compile_a1_cached_t1_w1.log`).
* Four `react-router build` runs writing one `.web/build`:
  `Error: Prerender: Request failed for /: … Received a 500 status code from entry.server.tsx`
  (`logs/conc/concurrent_export_a1_natural_t1_w3.log`), and on 0.9.10.post2 additionally
  `FileNotFoundError: '.web/app/routes'` from `purge_web_pages_dir` racing itself
  (`logs/conc/concurrent_export_0910_t1_w1.log`).

In every trial on 0.9.11a1 the two `assets/external/sharedapp/widget/shared.{js,css}` symlinks were
present and pointed at the right files afterwards — the asset half of the claim holds.

Regression: **no** (0.9.10.post2 is worse). Downstream: no.

## ISSUE-3 (low, pre-existing) — `reflex component init` dies with a bare "No module named pip" in a uv venv

`reflex/custom_components/custom_components.py::_pip_install_on_demand` runs
`sys.executable -m pip install -e .`. uv-created venvs have no `pip`, which is the documented way
to work in this repo, so the documented custom-component flow ends at:

```
cd <empty dir>/reflex_test_widget
$SB/envs/smoke/bin/reflex component init        # exit 1
# ─────── Installing reflex-test-widget in editable mode. ───────
# …/envs/smoke/bin/python: No module named pip
```

Everything before that point succeeded, so the user is left with a half-initialised project and no
hint that `uv pip install -e .` would finish the job (the `reflex init` output two lines earlier
does mention `uv pip install`). Evidence: `logs/component_init_a1.log`,
`logs/component_init_0910.log`. Regression: **no** — identical on 0.9.10.post2. Downstream: no.

## ISSUE-4 (low, not a regression) — the new `frontend_path` validation still accepts empty segments

#7044 added `_is_plain_path_segment`, but the loop skips empty segments
(`for segment in self.frontend_path.split("/"): if segment and not …`). An empty segment is not a
plain directory name either, and it makes the two derived values disagree:

```
cd /tmp && $SB/envs/smoke/bin/python -c "
import reflex as rx
c = rx.Config(app_name='t', frontend_path='/a//b')
print(c.prepend_frontend_path('/'), '|', c.frontend_path.strip('/'))"
#  /a//b/ | a/b        <- react-router/vite basename vs the build output directory
```

The build output is relocated into `.web/build/client/a/b`, while the client is told its basename
is `/a//b/`. `'//x'` is accepted too (its basename normalises to `/x/`, the build dir is `x`).
Evidence: `logs/frontend_path_validation.log`. Regression: **no** (0.9.10.post2 accepted every
form, including the three the fix now rejects). Downstream: no.

## ISSUE-5 (low, documentation) — reflex-base's 0.9.11a1 changelog re-lists #6933, which shipped in 0.9.9.post1

`packages/reflex-base/CHANGELOG.md` on `origin/r/pre-2026.09.10-34457666442` lists the same two
#6933 entries (the `_load_config()` deprecation and the multi-threaded `rxconfig.py` fix) under
**v0.9.9.post1, v0.9.10.post1 and v0.9.11a1**:

```
git -C /home/user/reflex show origin/r/pre-2026.09.10-34457666442:packages/reflex-base/CHANGELOG.md | grep -n 6933
```

The code confirms it: `reflex_base/config.py` is byte-identical between 0.9.10.post2 and 0.9.11a1
apart from `reload_config()`'s placement, the runtime warning says "deprecated in version
0.9.9.post1", and reflex-base 0.9.9.post1 is on PyPI. Someone upgrading 0.9.10.post2 → 0.9.11 will
read a deprecation and a bug fix as new when they already have both. Only reflex-base is affected;
the root `CHANGELOG.md` has no duplicated PR refs. Regression: n/a. Downstream: no.

---

## ISSUE-6 (low, pre-existing) — `reflex component build` prints five tracebacks and then reports success

```
mkdir -p /tmp/x/reflex_lazy_widget && cd /tmp/x/reflex_lazy_widget
$SB/envs/cac_comp/bin/reflex component init     # needs a venv with pip, see ISSUE-3
$SB/envs/cac_comp/bin/reflex component build    # exit 0, dist/*.whl and *.tar.gz produced
```

stdout contains five `Failed to import …` blocks with full tracebacks ending in
`ModuleNotFoundError: No module named 'custom_components'` and
`ModuleNotFoundError: No module named 'lazy_widget_demo'`, raised by
`reflex_base/utils/pyi_generator.py::_scan_files`, followed by
`Info: Custom component built successfully!`. The generator walks every top-level directory of the
project and imports `<dir>.<module>`, but neither `custom_components/` nor the generated demo app
directory is an importable package from the project root (setuptools maps
`where = ["custom_components"]`, so the installed top-level package is `reflex_lazy_widget`). The
build is fine; the output tells a first-time component author their build broke.

Evidence: `logs/component_build_full.log`, `logs/component_build_full_0910.log` (5 tracebacks on
each version). Regression: **no**. Downstream: no.

---

## Anomalies (recorded, not raised as defects)

* **A2 — click help for `reflex component init` renders the raw Google docstring**, "Args:" and
  "Raises:" included, as one paragraph. Both versions.
* **A3 — a directory at `assets/external/<pkg>/<mod>/<asset>` aborts the compile on both versions**,
  with different errors: 0.9.11a1 `IsADirectoryError` from `_link_shared_asset`'s `tmp.replace()`
  (`logs/shared_edge_directory.log`), 0.9.10.post2 `FileExistsError` later while copying into
  `.web/public` (`logs/shared_edge_directory_base.log`). No leftover `.<uuid>.tmp` files either way.
* **A4 — `console.deprecate()` output is not a Python `DeprecationWarning`.**
  `warnings.catch_warnings(record=True)` around `_load_config()` captures nothing; the notice is
  printed by the reflex logger instead. Tooling that runs with `-W error::DeprecationWarning` will
  not see reflex deprecations. Both versions. `logs/load_config_deprecation.log`.
* **A5 — the version-check cache is per app, in `<app>/.web/reflex.json`, not a user-level
  platformdirs cache.** A developer with ten projects still makes ten PyPI requests a day, and any
  invocation in a directory without `.web/reflex.json` checks unconditionally
  (`get_or_set_last_reflex_version_check_datetime` returns early before recording an attempt).
* **A6 — `reflex export` with `frontend_path=/myapp` and SSR on writes both
  `build/client/myapp/index.html` and a duplicate `build/client/myapp/myapp.html`** (plus
  `myapp.html.gz`) — the prerenderer emits the prefixed route as a file and the tree is then moved
  under the prefix. Identical on 0.9.10.post2, harmless.
* **A7 — the `SitemapPlugin is enabled by default` warning is printed twice per command** at
  default loglevel (once per config load), and 80 times in a 16-thread `reload_config()` loop.
* **A8 — each `get_config()` from a fresh thread loads `rxconfig.py` again** (16 threads → 16
  imports of rxconfig and of its sibling module) because `RegistrationContext.ensure_context()` is
  per-thread. Behaviour is correct and identical on both versions; it just means an rxconfig with
  import side effects runs them once per thread. `logs/threads_get_config.log`.
* **A9 — my own misconfiguration, recorded so nobody re-reports it**: serving the app on 5301 while
  `cors_allowed_origins` listed only 5300 gives `WebSocket … 403` and
  "Cannot connect to server: websocket error" in the browser. Correct CORS enforcement, not a bug.

---

## Verified claims (no defect)

### #7050 — CLI startup

`scripts/cli_timing.sh`, best of five, cold shell, `cwd=/tmp` (no reflex project):

| command | 0.9.10.post2 | 0.9.11a1 | 0.9.10.post2 + `[db]` | 0.9.11a1 + `[db]` |
| --- | --- | --- | --- | --- |
| `reflex --version` | 0.383 s | 0.171 s | 0.891 s | **0.170 s** |
| `reflex --help` | 0.378 s | 0.174 s | 0.890 s | **0.165 s** |
| `reflex run --help` | 0.361 s | 0.170 s | 0.892 s | **0.170 s** |
| `reflex component --help` | 0.352 s | 0.175 s | 0.897 s | **0.179 s** |
| `reflex cloud --help` | 0.355 s | 0.197 s | 0.925 s | **0.193 s** |
| `reflex deploy --help` | 0.366 s | 0.182 s | 0.941 s | **0.183 s** |
| `reflex export --help` | 0.371 s | 0.177 s | — | — |
| `reflex db --help` | 0.380 s | 0.178 s | — | — |

`logs/cli_timing.txt`, `logs/cli_timing_db.txt`. The `[db]` column is the reflex-base half of the
claim: on 0.9.10.post2 `reflex_base/utils/types.py` imported `sqlalchemy.ext.hybrid` at module
import time, so every CLI invocation paid for 123 sqlalchemy modules; 0.9.11a1 imports them inside
the function that needs them.

```
cd /tmp && $SB/envs/cac_db_0910/bin/python $SB/apps/config_assets_cli/scripts/laziness_db.py
cd /tmp && $SB/envs/cac_db_a1/bin/python  $SB/apps/config_assets_cli/scripts/laziness_db.py
#   after import reflex_base.utils.types: 0.9.10.post2 -> 367 modules, 123 sqlalchemy
#                                          0.9.11a1     -> 180 modules,   0 sqlalchemy
```

`import reflex` alone loads nothing matching `sqlalchemy|sqlmodel|reflex_base.plugins|
reflex_base.compiler` on either version (57 modules), and all 19 `rx.plugins.*` names still
resolve (`scripts/laziness.py`).

Missing hosting CLI, verbatim (`$SB/envs/cac_nohost`, `uv pip uninstall reflex-hosting-cli`):

```
$ reflex deploy                 # exit 1
`reflex deploy` requires the reflex-hosting-cli package, which is not installed.
Install it with: pip install reflex-hosting-cli
$ reflex cloud apps list        # exit 1
`reflex cloud` requires the reflex-hosting-cli package, which is not installed.
Install it with: pip install reflex-hosting-cli
```

`reflex login` and `reflex logout` behave the same, `reflex --help` shows
`cloud  Requires the reflex-hosting-cli package.` without importing it, and
`reflex deploy --help` / `reflex cloud --help` render the stand-in help instead of a usage error.
Identical text on 0.9.10.post2 (`logs/nohost_all.log`, `logs/nohost_all_0910.log`).
The suggestion is `pip install …` even though the rest of the CLI suggests `uv pip install …`.

### #7050 — version-check cache

Knob `REFLEX_CHECK_LATEST_VERSION` (default true); state in `<app>/.web/reflex.json` under
`last_version_check_datetime` (24 h) and `last_version_check_attempt_datetime` (1 h), suffixed per
package for anything but reflex itself.

CLI-level, from `--loglevel debug` logs of the same app dir:

```
grep -c 'pypi.org' logs/run1_a1.log              # 2   (request + response, first ever run)
grep -c 'pypi.org' logs/run2_a1_backendcfg.log   # 0
grep -c 'pypi.org' logs/run4_a1_plotly.log       # 0
```

Fine-grained, `scripts/version_cache_probe.py` (run from `cliapp/`; the local egress proxy is
bypassed for pypi.org by `NO_PROXY`, so the offline cases clear it explicitly):

```
cd $SB/apps/config_assets_cli/cliapp
env NO_PROXY= no_proxy= HTTPS_PROXY=http://127.0.0.1:9719 https_proxy=http://127.0.0.1:9719 \
    $SB/envs/smoke/bin/python ../scripts/version_cache_probe.py D1 --clear
$SB/envs/smoke/bin/python ../scripts/version_cache_probe.py D2
```

| scenario | elapsed | success key | attempt key |
| --- | --- | --- | --- |
| D1 cleared, dead proxy | 0.206 s | not written | **written** (1 h throttle) |
| D2 working proxy right after | 0.000 s | — | unchanged → **no request** |
| D3 attempt key removed, working proxy | 0.252 s | written | written |
| D4 dead proxy, success key fresh | 0.000 s | unchanged | unchanged → **no request** |

0.9.10.post2 for comparison (`cliapp_base/`): 0.248 s / 0.242 s / 0.189 s on three consecutive
calls — it requests PyPI unconditionally every time, and burns the timeout even when the network is
gone; its `last_version_check_datetime` only ever suppressed the *warning*, and never expired.

### #6933 — `_load_config()` deprecation and multi-threaded config loading

```
cd $SB/apps/config_assets_cli/cfgapp
$SB/envs/smoke/bin/python ../scripts/load_config_deprecation.py
$SB/envs/smoke/bin/python ../scripts/threads_get_config.py 16 get_config     # also reload_config, mixed
$SB/envs/smoke/bin/python ../scripts/threads_config_vs_import.py 8 8 40
```

`cfgapp/rxconfig.py` imports the project-local `sibling_settings.py` and both append to
`config_imports.log` / `sibling_imports.log`, so re-imports are visible without instrumenting
reflex. The deprecation reads:

```
DeprecationWarning: _load_config() has been deprecated in version 0.9.9.post1. Use _get_config()
to load a config from disk, or get_config() to read the config cached on the current
RegistrationContext. It will be completely removed in 1.0.
```

16 threads × 5 calls: 0 errors in all three modes on both versions. The harsher shape — 8 threads
calling `reload_config()` (which evicts rxconfig and its project-local deps from `sys.modules` and
removes the `sys.path` entry) while 8 threads plainly `import sibling_settings` — is also clean,
320/320 loads and 320/320 imports on both versions. `sys.path` length never drifts (5 → 5).
See ISSUE-5: this landed in 0.9.9.post1, so there is nothing here that 0.9.10.post2 lacks.

### #6960 — telemetry no longer re-imports rxconfig off-thread

```
cd $SB/apps/config_assets_cli/cfgapp && rm -f config_imports.log && rm -rf .web
env NO_PROXY= no_proxy= HTTPS_PROXY=http://127.0.0.1:9719 https_proxy=http://127.0.0.1:9719 \
  REFLEX_TELEMETRY_ENABLED=true timeout 60 $SB/envs/<env>/bin/reflex run --backend-only --backend-port 9702
cat config_imports.log
```

0.9.10.post2 (`logs/telemetry_base0910.log`, the app's `config_imports.log`):
```
rxconfig import thread=MainThread        pid=19120 syspath_len=6
rxconfig import thread=MainThread        pid=19120 syspath_len=6
rxconfig import thread=reflex-telemetry_0 pid=19120 syspath_len=6   <-- off-thread re-import
rxconfig import thread=MainThread        pid=19128 syspath_len=9
```
0.9.11a1: the `reflex-telemetry_0` line is gone; every import is on a main thread. `sys.path`
length is unchanged in both. Telemetry itself never leaves the box (dead proxy). This independently
reproduces the `telemetry_ctx` cluster's result.

### #7044 — frontend_path

```
cd /tmp && $SB/envs/smoke/bin/python $SB/apps/config_assets_cli/scripts/frontend_path_validation.py
```
`'../x'`, `'a\b'`, `'C:foo'` (and `'..'`, `'/a/../b'`, `'/.'`, `'/C:/x'`, `'/\\server\share'`,
`'/a/./b'`) all raise, verbatim for the three the changelog names:

```
ConfigError: frontend_path '/../x' contains '..', which is not a plain directory name (no '.', '..', backslashes, or drive letters).
ConfigError: frontend_path '/a\\b' contains 'a\\b', which is not a plain directory name (no '.', '..', backslashes, or drive letters).
ConfigError: frontend_path '/C:foo' contains 'C:foo', which is not a plain directory name (no '.', '..', backslashes, or drive letters).
```
`/myapp`, `/a/b`, `/`, `''`, `/my-app`, `/my.app`, `/v1.2`, `/a b` are all still accepted.
0.9.10.post2 accepted every one of the invalid forms.

Build side (`fpapp2/`, `frontend_path="/myapp"`):

| | 0.9.10.post2 | 0.9.11a1 |
| --- | --- | --- |
| `REFLEX_SSR=false reflex export --frontend-only --no-zip` | **fails**: `FileNotFoundError: '.web/build/client/myapp/index.html.gz'` | succeeds |
| `reflex export --frontend-only --no-zip` (SSR on) | succeeds | succeeds |

`logs/fp_export_0910_nossr.log`, `logs/fp_export_a1_nossr.log`, `logs/fp_export_a1_ssr.log`.
Serving the prod build under `/myapp` in a browser is covered by the `frontend_path_ssr` cluster
and was not duplicated here.

### #7039 — shared assets

`sharedapp/sharedapp/widget.py` publishes two shared assets
(`rx.asset("shared.css", shared=True)`, `rx.asset("shared.js", shared=True)`) and the page uses
both; `decoy.js` is the wrong target.

```
cd $SB/apps/config_assets_cli/sharedapp
$SB/envs/smoke/bin/reflex compile
ln -sf $PWD/sharedapp/decoy.js assets/external/sharedapp/widget/shared.js
$SB/envs/smoke/bin/reflex compile
readlink assets/external/sharedapp/widget/shared.js
```

| state of `assets/external/sharedapp/widget/shared.js` before the compile | 0.9.10.post2 after | 0.9.11a1 after |
| --- | --- | --- |
| symlink → `decoy.js` | still `decoy.js` (serves the wrong file) | **repointed to `shared.js`** |
| dangling symlink | repointed | repointed |
| symlink loop | (not run) | repointed |
| plain regular file | left as-is | **replaced with the link** |
| directory | `FileExistsError` later in `.web/public` | `IsADirectoryError` in `_link_shared_asset` (A3) |

Browser: `reflex run --frontend-port 5302 --backend-port 9702`, driven with the shared
`drive_app.py`. `/external/sharedapp/widget/shared.{js,css}?v=<hash>` return 200 with the right
bytes, the page renders, the state round-trips, and the console/network capture is empty
(`logs/sharedapp.json`, `shots/sharedapp.png`).

---

## Rerun cheatsheet

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
export REFLEX_TELEMETRY_ENABLED=false

# 1. CLI timings + laziness
bash scripts/cli_timing.sh
cd /tmp && $SB/envs/smoke/bin/python <artifacts>/scripts/laziness.py
cd /tmp && $SB/envs/cac_db_0910/bin/python <artifacts>/scripts/laziness_db.py

# 2. frontend reinstall (cliapp/)
$SB/envs/smoke/bin/reflex run --frontend-port 5300 --backend-port 9700 --loglevel debug   # then edit
                                                                                          # backend-only knobs, rerun
$SB/envs/smoke/bin/python ../scripts/normalize_pkgjson.py     # makes the install cache survive
$SB/envs/smoke/bin/python ../scripts/probe_sync.py            # which sync reports a change

# 3. version cache (cliapp/)
$SB/envs/smoke/bin/python ../scripts/version_cache_probe.py L1 --clear

# 4. config threads (cfgapp/)
$SB/envs/smoke/bin/python ../scripts/threads_get_config.py 16 mixed
$SB/envs/smoke/bin/python ../scripts/threads_config_vs_import.py 8 8 40

# 6. frontend_path
cd /tmp && $SB/envs/smoke/bin/python <artifacts>/scripts/frontend_path_validation.py
cd fpapp2 && REFLEX_SSR=false $SB/envs/smoke/bin/reflex export --frontend-only --no-zip

# 7. shared assets (sharedapp/)
bash scripts/concurrent_cli.sh $SB/envs/smoke/bin/reflex $PWD/sharedapp $PWD/logs/conc TAG 4 5 compile
```

Apps are shipped without `.web/`, `node_modules/`, `reflex.lock/`, `assets/external/` or
`__pycache__`; the first command in each app dir re-creates them.

---

## VERIFICATION: Frontend-package install cache is invalidated on every run (bun pretty-prints .web/package.json, reflex renders it compact), so bun add re-runs on every reflex run/compile/export and the #7050 reinstall-avoidance is invisible

Independent adversarial verification (second agent, own working dir
`$SB/apps/verify2_config_assets_cli_0/`, own app built from scratch — the claimant's
`cliapp/` was **not** used, only their NOTES/scripts were read).

**VERDICT: CONFIRMED — genuine framework defect. Severity: low (downgraded from the
claimed medium). Regression: NO (0.9.10.post2 is worse). Downstream: no (`reflex` itself).**

### What was reproduced

A fresh minimal app (`verification/issue1_install_cache/vapp/`: `rx.Config(app_name="vapp",
telemetry_enabled=False)`, one page, **no plugins** — so this is not specific to the
claimant's Tailwind/Sitemap app), reflex 0.9.11a1 from `$SB/envs/smoke`:

| step | reinstall | `Using cached value for _install_frontend_packages` | bun invocations |
| --- | --- | --- | --- |
| `reflex compile` #1 (first ever) | yes | 0 | 4 |
| `reflex compile` #2, nothing changed | yes | 0 | 3 |
| `reflex compile` #3, nothing changed | yes | 0 | 3 |
| `reflex run` #1 | yes | 0 | 5 |
| `reflex run` #2, after a **backend-only** rxconfig change | yes | 0 | 5 |
| `reflex export --frontend-only --no-zip`, natural state | yes | 0 | 5 |

Every non-cached invocation runs three real package-manager commands:
`bun install --legacy-peer-deps --frozen-lockfile`, `bun add --legacy-peer-deps -d <7 dev deps>`,
`bun add --legacy-peer-deps <12 framework deps>`
(`verification/issue1_install_cache/logs/v_compile_2.log` lines 21-64).

### Mechanism — confirmed at source level and by experiment

`.web/package.json` on disk and what reflex renders are **JSON-equal but not byte-equal**:

```
cd <app> && $SB/envs/smoke/bin/python verification/issue1_install_cache/scripts/probe_pkgjson.py
#   text identical      : False
#   JSON-equal          : True
#   disk    len/lines   : 774 32     <- bun, 2-space indent
#   rendered len/lines  : 664 1      <- json.dumps(), compact
```

Chain, all in the installed 0.9.11a1 wheel (identical on
`origin/r/pre-2026.09.10-34457666442`):

* `reflex_base/compiler/templates.py:597` — `package_json_template()` returns
  `json.dumps({...})` with no `indent`, i.e. one compact line.
* `reflex/utils/frontend_skeleton.py:370` —
  `sync_root_package_json_to_web()` compares `output_path.read_text() == rendered`
  (a **byte** comparison), so the formatting difference alone makes it return `True`
  ("meaningfully changed").
* `reflex/utils/js_runtimes.py:399-401` — `_sync_root_lockfiles_for_frontend_install()`
  deletes `.web/reflex.install_frontend_packages.cached` whenever that returns `True`.
* `reflex/utils/js_runtimes.py:612-615` — `_install_frontend_packages` is a
  `@cached_procedure` keyed on that file, so it re-runs; bun then rewrites
  `.web/package.json` pretty-printed and the loop repeats forever.

The docstrings make the intent explicit ("True if `.web`'s copy was **meaningfully**
changed", "Initial creation does not count as a meaningful change since no install cache
could exist yet"), so a formatting-only diff invalidating the cache is a defect, not
documented behaviour.

**bun is the pretty-printer** (proved, not assumed): with `.web/package.json` rewritten
compact and the cache file deleted by hand, one `reflex compile` turned it back into
31 lines (`logs/v_compile_6_after_cache_rm.log`).

### Causation proof (own runs, own app)

```
cd $SB/apps/verify2_config_assets_cli_0/vapp
$SB/envs/smoke/bin/python ../scripts/normalize_pkgjson.py      # formatting only, no content change
REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex compile --loglevel debug
```
-> `reinstall=0 cache_hit=1 bun_invocations=0`, twice in a row
(`logs/v_compile_4_normalized.log`, `logs/v_compile_5_normalized.log`), and it survives a
**backend-only** rxconfig change (`backend_host`, `cors_allowed_origins`, `backend_port`):
`logs/v_compile_7_normalized_backendcfg.log` -> `cache_hit=1, bun_invocations=0`.
`reflex export` behaves the same (`logs/v_export_1_cached.log`).

So #7050's payload change **does** work — the promise in the changelog is real, it is just
never reachable because a second, older invalidation path fires first on every run.

### Self-contained minimal repro (runs from an empty directory)

```
bash /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/config_assets_cli/\
verification/issue1_install_cache/scripts/repro_install_cache.sh \
    $SB/envs/smoke/bin/reflex /tmp/repro_a1
```
0.9.11a1 output: phase 1 = 3x `cache_hit=0`; phase 2 (normalise formatting) = `cache_hit=1,
bun_invocations=0`; phase 3 (backend-only config change) = `cache_hit=1, bun_invocations=0`.

### Baseline 0.9.10.post2 — run myself, and it is WORSE

```
bash .../scripts/repro_install_cache.sh $SB/envs/base0910/bin/reflex /tmp/repro_base
```
phases 1, 2 **and** 3 all report `cache_hit=0`. Two independent reasons on 0.9.10.post2:

1. the identical `sync_root_package_json_to_web()` byte comparison
   (`$SB/envs/base0910/.../reflex/utils/frontend_skeleton.py:370` — same code), **and**
2. its cache payload embedded `config.json()`
   (`.../reflex/utils/js_runtimes.py:599`), whose `_non_default_attributes` is a **set**
   serialised in iteration order, so the fingerprint changes between processes:
   ```
   cd <app0910> && for i in 1 2 3; do $SB/envs/base0910/bin/python -c "
   import json; from reflex_base.config import get_config
   print(json.loads(get_config().json())['_non_default_attributes'])"; done
   #  ['backend_host', 'app_name', 'telemetry_enabled', 'cors_allowed_origins']
   #  ['backend_host', 'telemetry_enabled', 'app_name', 'cors_allowed_origins']
   #  ['cors_allowed_origins', 'backend_host', 'telemetry_enabled', 'app_name']
   ```
   i.e. on 0.9.10.post2 the install cache could **never** hit for any app with >1
   non-default config attribute, regardless of package.json.

Logs: `logs/vbase_compile_1..3.log` (natural), `logs/vbase_compile_4_normalized.log` and
`logs/vbase_compile_6_normalized2.log` (still miss after normalising).
So 0.9.11a1 is strictly better than 0.9.10.post2 — **not a regression**, confirmed
empirically and at source level.

### Where I disagree with the claimant: impact / severity

The claim's severity rests on "on a cold machine, in CI, or behind a slow registry that is
a network round trip per `reflex run`". I measured that and it does **not** hold as long as
`.web/node_modules` exists:

* Wall-clock `reflex compile`, best of 3, same app: **0.664-0.714 s cached** vs
  **0.716-0.726 s uncached** -> the redundant installs cost ~**50 ms**
  (`[timing] Install Frontend Packages: 0.05s`; bun itself reports 9-11 ms per command).
* Pointed `.web/bunfig.toml` at a dead registry (`http://127.0.0.1:10403/`) and dropped the
  cache: `reflex compile` still **succeeded in 0.82 s**
  (`logs/v_compile_deadregistry.log`).
* Same, additionally with an empty `BUN_INSTALL_CACHE_DIR`: still **succeeded, 0.79 s**
  (`logs/v_compile_deadreg_coldcache.log`).

So the repeated `bun install --frozen-lockfile` / `bun add` are resolved entirely from
`.web/node_modules` + `bun.lock` and make **no network request**. The real cost is ~50 ms
of local work per CLI invocation, not a registry round trip. Downgraded to **low**.

What genuinely remains, and is worth fixing before/soon after release:

1. The shipped changelog line "avoid frontend package reinstalls after backend-only config
   changes" is **not observable by any user** in a normal app — the feature is dead on
   arrival even though the code behind it is correct.
2. It is the trigger for the concurrent-compile aborts recorded as ISSUE-2 in this cluster
   (with the cache alive, 24/24 concurrent compiles were clean).
3. Every CLI invocation shells out to a package manager three times against a shared
   `.web/node_modules`, which is exactly the kind of avoidable write that breaks under
   parallelism and on read-only/containerised builds.

Suggested direction (not applied — verifiers do not fix): compare parsed JSON rather than
bytes in `sync_root_package_json_to_web()` (e.g. `json.loads(existing) == json.loads(rendered)`,
falling back to a byte compare on parse failure), or render with the same 2-space indent bun
uses. Either makes the byte-vs-format churn disappear; both are ~2 lines in
`reflex/utils/frontend_skeleton.py`.

### Refutations I ruled out

* **Environment quirk** — no: reproduced in a brand-new app in my own directory with my own
  ports (frontend 6001, backend 10400), with the default registry, with a dead registry, and
  with a cold bun cache dir. Nothing proxy- or `NO_PROXY`-dependent; bun ships with reflex
  (1.4.0), so every user gets the same pretty-printer.
* **cwd shadowing** — no: every python invocation ran from the app dir with
  `assert "/envs/" in reflex.__file__`; the installed wheel at
  `$SB/envs/smoke/lib/python3.11/site-packages/reflex` was the one read and run.
  (Worth noting for others: `python -c "import reflex"` **with cwd=/home/user/reflex**
  silently resolves to the checkout.)
* **Demo/example-app bug** — no: minimal app, no plugins, no third-party components.
* **Documented behaviour / API misuse** — no: the function's own docstring says only
  "meaningful" changes should invalidate.
* **Flaky** — no: 6/6 natural runs missed the cache, 5/5 normalised runs hit it, on two
  different apps and two reflex versions.
* **Regression** — no: 0.9.10.post2 misses in strictly more situations.

### Files

* Repro + probes: `verification/issue1_install_cache/scripts/`
  (`repro_install_cache.sh`, `probe_pkgjson.py`, `normalize_pkgjson.py`, `probe_sync2.py`,
  `run_once.sh`)
* Minimal app: `verification/issue1_install_cache/vapp/`
* Logs: `verification/issue1_install_cache/logs/`
* No processes left running (`ps aux | grep -E 'reflex|vite|granian|bun|chrom'` clean,
  no listeners on ports 6000-6003 / 10400-10403).

---

## VERIFICATION: Compiling or exporting one working directory from several processes still aborts (bun node_modules EEXIST, react-router prerender race), so #7039's parallel-build claim only holds for the asset-link step

Independent adversarial verifier (second pass, own working dir
`$SB/apps/verify2_config_assets_cli_1/`, own app copies, own scripts).

**Verdict: NOT CONFIRMED as filed — the observations reproduce exactly, the finding does not.**
Every number in the claim reproduces. But the three refutations below take it out of
"pre-release finding" territory: the changelog sentence is already scoped to the asset-link
step, the aborts have nothing to do with `rx.asset(shared=True)` (an app with no shared asset
at all aborts at the same rate), and the one reflex-owned crash in the set is byte-identical
between 0.9.10.post2 and 0.9.11a1 — so even the claim's own "0.9.10.post2 is worse" is a
sampling artifact, not a code difference.

### What I ran (all commands verbatim)

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
D=$SB/apps/verify2_config_assets_cli_1          # app copies + logs live here
# sharedapp copied from this cluster's sharedapp/, warmed once per version:
cd $D/sharedapp      && REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex compile
cd $D/sharedapp_base && REFLEX_TELEMETRY_ENABLED=false $SB/envs/base0910/bin/reflex compile

bash $D/conc.sh       $SB/envs/smoke/bin/reflex    $D/sharedapp    $D/logs/conc v2_compile_a1    4 5 compile
bash $D/conc.sh       $SB/envs/smoke/bin/reflex    $D/sharedapp    $D/logs/conc v2_export_a1     4 4 export --frontend-only --no-zip
bash $D/conc.sh       $SB/envs/base0910/bin/reflex $D/sharedapp_base $D/logs/conc v2_compile_0910 4 5 compile
bash $D/conc.sh       $SB/envs/base0910/bin/reflex $D/sharedapp_base $D/logs/conc v2_export_0910  4 4 export --frontend-only --no-zip
# control: identical app/components, rx.asset(shared=True) replaced by two static /assets paths
bash $D/conc_plain.sh $SB/envs/smoke/bin/reflex    $D/noassetapp   $D/logs/conc v2_noasset_dev_a1  4 5 compile
bash $D/conc_plain.sh $SB/envs/smoke/bin/reflex    $D/sharedapp    $D/logs/conc v2_shared_norm_a1  4 3 compile
bash $D/conc_plain.sh $SB/envs/smoke/bin/reflex    $D/noassetapp   $D/logs/conc v2_noasset_dev2_a1 4 3 compile
# prod-mode compile only (purge_web_pages_dir path, no react-router build)
bash $D/conc_prod.sh  $SB/envs/smoke/bin/reflex    $D/sharedapp    $D/logs/conc v2_prodcompile_a1  4 8 compile
# minimal repro of the one reflex-owned crash, run from any app dir that has a .web/
cd $D/noassetapp     && REFLEX_ENV_MODE=prod REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/python    $D/purge_race.py 4 40
cd $D/sharedapp_base && REFLEX_ENV_MODE=prod REFLEX_TELEMETRY_ENABLED=false $SB/envs/base0910/bin/python $D/purge_race.py 4 40
```

### Results

| run | 0.9.11a1 | 0.9.10.post2 |
| --- | --- | --- |
| 4x `reflex compile`, 5 trials, sharedapp | 4/20 aborted (bun EEXIST) | 1/20 aborted (bun EEXIST) |
| 4x `reflex export --frontend-only --no-zip`, 4 trials | 4/16 aborted (all prerender 500) | 4/16 aborted (2x `FileNotFoundError: '.web/app/routes'`, 1x prerender 500, 1x bun EEXIST) |
| 4x `reflex compile`, 5+3 trials, **no `rx.asset` at all** | 0/20 then 4/12 aborted (bun EEXIST) | not run |
| 4x prod-mode `reflex compile`, 8 trials | 1/32 aborted (bun EEXIST) | not run |
| `purge_race.py 4 40` | **3/4 workers raise `FileNotFoundError`** | 3/4 workers raise `FileNotFoundError` |

In every trial on both versions the two `assets/external/sharedapp/widget/shared.{js,css}`
symlinks existed and pointed at the right files afterwards — the asset half of #7039 holds,
as the claim says.

### Refutation 1 — the changelog is already scoped to the asset-link step

```
git -C /home/user/reflex show origin/r/pre-2026.09.10-34457666442:CHANGELOG.md | sed -n 16p
```

> Compiling an app from several processes against one working directory — pytest-xdist
> workers, parallel builds, or containers sharing a bind mount — no longer aborts with
> `FileNotFoundError` or `FileExistsError` **while linking a `rx.asset(shared=True)` file
> into `assets/external/`**. (#7039)

The qualifier is in the same sentence, and PR #7039 is titled "fix(assets): link shared assets
atomically instead of check-then-act". Its own "Notes for review" even lists the neighbouring
races as deliberately out of scope ("`remove_stale_external_asset_symlinks()` is itself
check-then-act ... Left for a follow-up to keep this diff local"). So "#7039's parallel-build
claim only holds for the asset-link step" restates what the release note says rather than
contradicting it. At most the opening clause reads broadly until the qualifier lands — a
wording nit, not a defect.

### Refutation 2 — the aborts are unrelated to shared assets (control app)

`verification/issue2_parallel_cli/noassetapp/` is the same app, same components, same page,
with `CSS_PATH = rx.asset("shared.css", shared=True)` replaced by `CSS_PATH = "/shared.css"`
(files moved to `assets/`). Four concurrent `reflex compile` runs in it abort with exactly the
same error:

```
Installing frontend packages failed with exit code 1
error: Failed to link @babel/parser: EEXIST
error: Failed to link autoprefixer: EEXIST
...
```
(`verification/issue2_parallel_cli/logs/v2_noasset_dev2_a1_t3_w2.log`, 4/12 workers)

So the scenario is "N processes run `bun install`/`bun add` into one `.web/node_modules` and
`react-router build` into one `.web/build`". No package manager or bundler serializes that;
reflex takes no cross-process lock either (`grep -rn "filelock\|fcntl\|flock"` over the
installed `reflex`/`reflex_base` returns nothing). Whether an app uses `rx.asset(shared=True)`
makes no difference, so this is not evidence about #7039 in either direction.

Side note on the trigger: every `reflex compile` does run bun three times even with
`.web/reflex.install_frontend_packages.cached` present (`reflex compile --loglevel debug`
shows `bun install` + two `bun add`), which is ISSUE-1 above. Fix ISSUE-1 and this whole
failure mode stops being reachable for `compile` — which matches the claim's own
"cache alive -> 24/24 clean" observation. The actionable root cause is ISSUE-1, not this.

### Refutation 3 — the one reflex-owned crash is identical in both versions

The claim reports `FileNotFoundError: '.web/app/routes'` from `purge_web_pages_dir` as a
0.9.10.post2-only symptom ("baseline is worse"). It is not version-specific. The code is
byte-identical between the two wheels:

- `reflex/compiler/compiler.py:794-803` `purge_web_pages_dir()` (called at
  `compiler.py:1435` on a1, `:1422` on 0.9.10.post2, prod mode only)
- `reflex/compiler/utils.py:979-996` `empty_dir()` — `path.iterdir()` at `:994` then `path_ops.rm(element)` at `:996`
- `reflex/utils/path_ops.py:32-43` `rm()` — `shutil.rmtree(...)` at `:41` / `path.unlink()` at `:43`

`iterdir()` -> `rm()` is check-then-act: another process removing the same entry in between
makes `shutil.rmtree` (and its `chmod_rm` onerror handler) raise. Minimal repro
`verification/issue2_parallel_cli/scripts/purge_race.py` (4 processes, 40 iterations, no bun,
no bundler) raises on **both** versions, 3/4 workers each:

```
# 0.9.11a1 - verification/issue2_parallel_cli/logs/purge_race_a1.log
  File ".../reflex/compiler/compiler.py", line 801, in purge_web_pages_dir
  File ".../reflex/compiler/utils.py", line 996, in empty_dir
  File ".../reflex/utils/path_ops.py", line 43, in rm
FileNotFoundError: [Errno 2] No such file or directory: '.web/app/_document.js'
# 0.9.10.post2 - verification/issue2_parallel_cli/logs/purge_race_0910.log
FileNotFoundError: [Errno 2] No such file or directory: '.web/app/routes'
```

That it only showed up in the 0.9.10.post2 export sample (mine and the claimant's) is timing,
not a fix. My a1 export sample happened to lose the same race in react-router instead.

### What is left, and what I would do with it

A real but pre-existing robustness gap, entirely outside this release: concurrent CLI
invocations against one working directory can abort, in three independent places, none of
them the shared asset —

1. `bun install`/`bun add` into one `.web/node_modules` (bun's error, reflex has no lock);
   only reachable this often because of ISSUE-1;
2. `react-router build` into one `.web/build` (react-router's error);
3. `purge_web_pages_dir()` -> `empty_dir()` -> `path_ops.rm()` check-then-act — reflex's own
   code, cheap to harden (`shutil.rmtree(..., ignore_errors=...)` / `unlink(missing_ok=True)`),
   and the same bug class #7039's author explicitly deferred.

Only (3) is reflex's to fix and it is a **low**-severity follow-up issue, not a 0.9.11 blocker
and not a regression. Nothing here should change the #7039 changelog entry beyond, optionally,
moving the "while linking a `rx.asset(shared=True)` file" qualifier earlier in the sentence.

Evidence (new, this verification):
`verification/issue2_parallel_cli/scripts/{conc.sh,conc_plain.sh,conc_prod.sh,purge_race.py}`,
`verification/issue2_parallel_cli/noassetapp/` (control app with no shared asset),
`verification/issue2_parallel_cli/logs/{v2_compile_a1_t2_w4,v2_compile_a1_t4_w4,v2_export_a1_t3_w1,v2_compile_0910_t3_w2,v2_export_0910_t1_w1,v2_export_0910_t1_w3,v2_noasset_dev2_a1_t3_w2,purge_race_a1,purge_race_0910}.log`.
No processes left running (all runs foreground; `ps aux | grep -E 'reflex|vite|granian|bun|chrom'`
shows only another cluster's dev server).
