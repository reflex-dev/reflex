# examples_ui — non-DB reflex-examples, in-place upgrade 0.10.1 -> 0.11.0a1

## Status / resume here
- [x] staged: `$SB/apps/examples_ui` (= `$W`) = copy of `prerelease-testing/fixtures/upgrade` (`bin/stage.sh --no-fetch`)
  + apps copied from `$SB/downloads/reflex-examples` @ ebe19ff into `$W/up/apps/<app>` (github-stats + upload QA patches
  applied, rxconfig venv guard `QA_EXPECT_VENV`). Env: `. $SB/apps/examples_ui/env_eu.sh`.
  NOTE: a first staging attempt with a broken `$W` created `/apps/examples_ui` at the filesystem root (fixture copy only,
  no servers); the sandbox refused my `rm -rf` of it — leave it for a human to delete.
- [x] base venvs `$SB/envs/examples_ui-<app>` = `reflex==0.10.1` + requirements.txt, `-c $W/prev_constraints.txt`
  (freeze of `$SB/envs/prev`), no --prerelease, `--only-binary :all:`. Freezes in `$W/up/freeze/<app>-base.txt`.
- [x] DONE. All 9 apps (counter, github-stats, overkey, reflexle, upload, clock, quiz, snakegame, lorem-stream) base ->
  in-place -> prod -> cold; overkey fix + migration; split-origin prod (#7641) on upload; install matrix; blank init.
  Final report: `reports/examples_ui.md`. All servers stopped (ports 3420-3439/8420-8439 free).

## How to rerun
```bash
. $SB/apps/examples_ui/env_eu.sh            # SB, W, DEST, venv prefix examples_ui
cd $SB && bash <repo>/prerelease-testing/fixtures/upgrade/bin/stage.sh --no-fetch   # with W set as above
# copy apps: for a in github-stats overkey reflexle upload counter clock quiz; do cp -r $SB/downloads/reflex-examples/$a $W/up/apps/; done
# patch: (cd $W/up/apps && patch -p1 < $W/examples/patches/github-stats_fetchers.diff && patch -p1 < $W/examples/patches/upload-qa-extras.diff)
# harness fix: cp $W/up/scripts/harness_b.py $W/up/scripts/harness.py   (drive_upload.py needs Run.expected_bad; fixture drift)
# base venv per app:
uv --no-config venv --python 3.12 $SB/envs/examples_ui-<app>
uv --no-config pip install --python $SB/envs/examples_ui-<app>/bin/python --only-binary :all: -c $W/prev_constraints.txt -r $W/up/apps/<app>/requirements.txt 'reflex==0.10.1'
cd $W && bash eu/seq_eu.sh <app> base baseprod upgrade up prod cold      # this cluster's driver: eu/seq_eu.sh
```
`eu/seq_eu.sh` phases: base (0.10.1 dev, fresh .web/reflex.lock/profile) -> baseprod (0.10.1 `--env prod`, single port)
-> upgrade (`uv pip install --prerelease=allow 'reflex==0.11.0a1'`, **no -U**, same venv) -> up (dev, same dir/.web/
reflex.lock/browser profile) -> prod (single port 3420 + `REFLEX_API_URL=http://localhost:3420`) -> cold (`rm -rf .web`).
Ports: dev 3420/8420, prod 3420 (same origin so LocalStorage/cookies carry over), GraphQL stub 8438.
Drivers: fixture `up/scripts/drive_*.py` + new `eu/drive_overkey.py`. `eu/logdiff.sh a.log b.log` lists normalized
server-log lines new in b. `eu/pkgjson_cmp.py` = semantic package.json diff.

## Results per app (pass/fail/anomaly from the drivers; logs `$W/logs/<app>/`, run JSON + screenshots `$W/shots/<app>/`)

| app | 0.10.1 dev | 0.10.1 prod | 0.11.0a1 dev (in place) | 0.11.0a1 prod | 0.11.0a1 cold | verdict |
|---|---|---|---|---|---|---|
| counter | 8/0/0 | - | 8/0/0 | 8/0/0 | 8/0/0 | same |
| github-stats (stubbed GraphQL) | 14/0/2 | (log only) | 12/0/2 persist | 13/0/1 persist | 14/0/2 | same as a5 records; anomalies pre-existing |
| overkey unmodified | 27/1*/0 | 27/1*/0 | **does not start** | - | - | known stacked-decorator regression |
| overkey, outer `@rx.event` removed | - | - | 27/0/0 | 27/0/0 | 27/0/0 | works fully |
| overkey migrated to `rx.client_state` (named / unnamed) | - | - | 27/0/0 / 27/0/0 | - | - | works, 0 deprecations |
| reflexle (reflex-global-hotkey 1.2.3) | 19/0/0 | 18/0/1 | 19/0/0 | 18/0/1 | 19/0/0 | same (prod: favicon 404 console line) |
| upload | 21/0/0 | 21/0/0 | 21/0/0 | 21/0/0 | 21/0/0 | same |
| clock (rx.Cookie, bg tick) | 15/2/0 | 15/2/0 | 15/2/0 | 15/2/0 | 15/2/0 | same; the 2 fails are the driver's October (PDT/CEST) offsets, app shows correct PST/CET |
| snakegame (bg game loop, key watcher) | 13/0/0 | 13/0/0 | 13/0/0 | 13/0/0 | 13/0/0 | same |
| lorem-stream (bg streaming tasks) | 18/0/0 | 18/0/0 | 18/0/0 | 18/0/0 | 18/0/0 | same |
| quiz (code_block, redirect) | 12/0/1 | 13/0/0 | 12/0/1 | 13/0/0 | 12/0/1 | same (dev Checkbox uncontrolled->controlled warning, pre-existing) |

\* the 0.10.1 overkey "fail" was a driver assumption (expected the client to send `tick` events); on both versions a
background task's returned `OverkeyState.tick` is chained server-side, 0 client `tick` frames. The check became a note.

### Upgrade step (`uv pip install --prerelease=allow 'reflex==0.11.0a1'`, no -U), identical for every app
Moved: reflex, reflex-base, reflex-components-code, -core, -radix 0.10.1 -> 0.11.0a1. **Stayed:** reflex-components-lucide
1.1.1, reflex-hosting-cli 0.2.1, redis 7.4.1, reflex-global-hotkey 1.2.3, everything else. `uv pip check` clean.
With `-U --prerelease=allow` (dry run, `$SB/envs/examples_ui-ipuv`): additionally lucide 1.1.1 -> 1.1.2a1, hosting-cli
0.2.1 -> 0.2.2a1, **redis 7.4.1 -> 8.2.0b1** (a redis-py beta). Without the flag uv refuses (`no version of
reflex-base==0.11.0a1` + hint `--prerelease=allow`) — uv semantics, pre-existing.
pip (`$SB/envs/examples_ui-ippip`, 0.10.1): `pip install -U reflex` stays on 0.10.1 (alphas ignored, good);
`pip install reflex==0.11.0a1` (no --pre, no -U) works and moves the same 5 packages; `-U` and `-U --pre` with the pin
change nothing more (pip's only-if-needed strategy), so pip users keep lucide 1.1.1 / hosting-cli 0.2.1; `pip install
-U reflex` on the alpha venv stays on 0.11.0a1. `pip check` clean.

### First 0.11.0a1 run on the old `.web` / `reflex.lock`
- `reflex run` re-runs both `bun add` calls + `bun install --frozen-lockfile` (225 packages), starts in ~4 s.
  `reflex.lock/bun.lock` byte-identical; `.web/package.json` **and the committed `reflex.lock/package.json`** rewritten
  from indented to single-line JSON (semantically identical: `eu/pkgjson_cmp.py` -> "IDENTICAL (formatting only)").
- New `.web` files: `utils/client_state.js`, `utils/helpers/set.js`; `Errorboundary_errorboundary_<hash>.jsx` renamed
  (hash 71c9c4d9... -> fd51d99e...). Benign. Cold rebuild (`rm -rf .web`) == in-place (package.json + file list identical).
- New server-log messages for unchanged code: none for counter, github-stats, reflexle, upload, clock, quiz.
  overkey (after the fix): `DeprecationWarning: ClientStateVar.create has been deprecated in version 0.11.0. Use
  rx.client_state(default, name=...) instead. Naming a var makes it global; an unnamed var is owned by the outermost page
  or `@rx.memo` that uses it, so `global_ref` is no longer needed. It will be completely removed in 1.0.
  (overkey/overkey.py:80)` and twice `DeprecationWarning: ClientStateVar.set_value has been deprecated in version
  0.11.0. Use .set instead -- `cs.set` for the bare setter, `cs.set(value)` to bind a value. It will be completely
  removed in 1.0.` — once with `(overkey/overkey.py:286)` (the `set_value("")` call), once with
  **`(.../site-packages/reflex_components_core/el/elements/forms.py:857)`** for `on_change=user_input_state.set_value`
  (overkey.py:359; a bound method passed as the handler is invoked from inside the framework, so the location points into
  reflex_components_core instead of the user's line). Pre-existing on both: `@rx.memo ... without explicit annotations
  has been deprecated in version 0.9.3`, `Mutable default values are not recommended`, github-stats
  `RouterData.page has been deprecated in version 0.8.1`, prod `Page widget/[selected_user_param] is being redefined`.
- Every dev `reflex run` (both versions) prints `Info: Initializing the web directory.` and `Success: Initialized <app>.
  Install dependencies from requirements.txt ... before running uv run reflex run.` (pre-existing, odd during `run`).

### overkey on 0.11.0a1 unmodified (what a user sees) — `$W/logs/overkey/up-stacked-fail.server.log`
`reflex run` prints the ClientStateVar.create deprecation, `Warning: Mutable default values...`, then a traceback through
`state.py __init_subclass__ -> registry._register_event_handler -> format.get_event_handler_parts` ending in
`AttributeError: 'EventHandler' object has no attribute '__qualname__'. Did you mean: '__set_name__'?` and exits after
~7 s. Nothing names the decorator or `tick`; the only user frame is `overkey.py line 92, class OverkeyState(rx.State)`.
Minimal fix = delete the outer `@rx.event` (`eu/overkey-minimal-fix.diff`). Full migration (`eu/overkey-migrate-named.diff`,
`-unnamed.diff`): `rx.client_state("", name="user_input")` (or unnamed) + `.set` -> no deprecation lines, 27/27.
ClientStateVar on reload mid-game: identical on 0.10.1 / 0.11.0a1 dev+prod — the typed input resets to `""`, on_load
resets the timer (selects back), the pre-reload background tick does not resume the countdown, the next game works.
Restart (rotate-ccw) clears the typed input on both versions (TP-04 / examples#324 did not reproduce with this driver).

### TP-04 (examples#324) — `eu/probe_overkey_restart.py`
Restart clicked mid-game (timer running, 8 chars typed): input cleared and letters reset on 0.10.1 (`overkey-b010` copy of
the unmodified app, `$SB/envs/prev`) and on 0.11.0a1 (fixed app). Typing again starts a new timer. Not reproducible at
reflex-examples ebe19ff on either version (the `witness_is_reset` memo clears it).

### github-stats LocalStorage across the upgrade (`storage_probe.py`, profile written by 0.10.1)
First 0.11.0a1 load: users + stats restored, no changing app-storage writes (PASS). Both versions keep writing
`github_stats_state.user_stats_json` with the same value ~40 times/s while the page is open (8 s window: 338 writes on
0.10.1, 383 on 0.11.0a1; profile copies `$W/profiles/gh-fl-{b010,new}`) — **pre-existing anomaly**, not a regression.

### Split-origin prod (#7641) on a real app — `eu/split_prod.sh <key> <appdir> <venv>`
`reflex run --env prod --frontend-port 3420 --backend-port 8420` is refused on both versions ("In prod mode, frontend and
backend must run on the same port."), so no fixture/app here used two prod ports. The documented split is
`--backend-only --backend-port 8420` + `--frontend-only --frontend-port 3420`, `REFLEX_API_URL=http://localhost:8420`,
deploy_url unset:
- 0.10.1 (`$SB/envs/prev`, `up/apps/upload-b010`): upload driver 21/0/0; `/_event` polling and `/_upload` preflight
  answer `access-control-allow-origin: http://localhost:3420`.
- 0.11.0a1: page renders, client-only features work (file selection, drag & drop), but every backend interaction is dead:
  websocket rejected, uploads never land (6 FAIL + the driver times out waiting for "cancel"); `/_upload` preflight
  `405 Method Not Allowed`, no ACAO. Backend log: one line `http://localhost:3420 is not an accepted origin. (further
  occurrences of this error will be logged with level INFO)` — no `Warning:` prefix, no hint at deploy_url /
  cors_allowed_origins; nothing at startup. The `--loglevel debug` Config dump shows `cors_allowed_origins=('*',)` while
  the effective value is "none" (`reflex.app._cors_allowed_origins()` -> None; probe in NOTES above). Already filed by
  server_net (split deployment, high after verify_net); this is the same behaviour on the reflex-examples upload app.
  `REFLEX_CORS_ALLOWED_ORIGINS=...` / `REFLEX_DEPLOY_URL=...` env overrides are honoured (checked at Python level).

### Fresh-install matrix (PKG-09 / PKG-05) — `$W/inst/bin/n001.sh` + `dbcli.sh`, `INST_VERSION=0.11.0a1`
| install | rc | sqlalchemy / greenlet / aiosqlite / sqlmodel / alembic | lucide / hosting-cli / redis | pip check |
|---|---|---|---|---|
| uv 3.11 / 3.14 / 3.15 `reflex[db]==0.11.0a1 --prerelease=allow` | 0 | 2.1.8 / 3.5.6 / 0.22.1 / 0.0.48 / 1.20.1 | 1.1.2a1 / 0.2.2a1 / **8.2.0b1** | clean |
| pip 3.11 / 3.14 / 3.15 `reflex[db]==0.11.0a1` (no --pre) | 0 | same | 1.1.1 / 0.2.1 / 8.1.0 | clean |
| pip 3.12 `reflex==0.11.0a1` (no --pre) | 0 | not installed (expected) | 1.1.1 / 0.2.1 / 8.1.0 | clean |
`dbcli.sh` (uv311 uv315 pip311 pip314 pip315): `reflex db init / makemigrations / migrate / makemigrations(noop)` all rc 0,
1 version file, tables alembic_version + note. `reflex init --template blank` + dev run (uv311 pip314 uv315 pip315): init
rc 0, no npmmirror lines, 200, welcome page, colour mode toggle + survives reload; identical `.web/package.json` across
Python versions; dev answers `/nope` with 200 (SPA fallback, pre-existing). Python 3.15 is downloaded by uv on demand.
pip accepts the exact alpha pin without --pre and resolves the 0.11.0a1 siblings it pins (`reflex-base==`, core/code/
radix `>=0.11.0a1`); `pip install -U reflex` in a 0.10.1 venv stays on 0.10.1.

## Anomalies (benign or pre-existing)
1. `reflex.lock/package.json` (committed to VCS) is rewritten from indented to one-line JSON on the first 0.11 run —
   a no-op diff in every upgraded project's repo; bun.lock unchanged.
2. `ClientStateVar.set_value` deprecation for `on_change=cs.set_value` is attributed to
   `site-packages/reflex_components_core/el/elements/forms.py:857`: `reflex_base/utils/log.py`
   `_get_first_non_framework_frame` excludes `reflex` and `reflex_base` roots but not the `reflex_components_*` packages.
3. Three redis-py versions depending on install path: in-place without -U keeps 7.4.1, pip fresh 8.1.0, uv
   `--prerelease=allow` fresh or -U 8.2.0b1 (beta).
4. Debug Config dump shows `cors_allowed_origins=('*',)` in prod while the effective default is no CORS.
5. github-stats writes the same LocalStorage value ~40/s on both versions (above).
6. Pre-existing on both: github-stats widget `?appearance=dark` not applied + React `value` without `onChange` (3x);
   quiz dev `Checkbox is changing from uncontrolled to controlled` (6x); reflexle prod favicon 404 console line;
   `Initializing the web directory` + `Success: Initialized <app>...` printed by every dev `reflex run`.
7. Fixture drift: staged `up/scripts/harness.py` lacks `Run.expected_bad` that `drive_upload.py` uses (harness_b.py has
   it) — copied harness_b.py over harness.py. `clock_common.py` hardcodes October UTC offsets (2 clock fails on every
   version in November). The fixture `upgrade()` helper uses `-U`; this cluster's seq_eu.sh upgrades without -U.
8. Sandbox: `rsync` is not installed (use tar); GitHub blocked (GraphQL stub `up/scripts/github_stub.py`).
