# examples_ui — non-DB reflex-examples, in-place upgrade 0.10.1 -> 0.11.0a1

## Status / resume here
- [x] staged: `$SB/apps/examples_ui` (= `$W`) = copy of `prerelease-testing/fixtures/upgrade` (`bin/stage.sh --no-fetch`)
  + apps copied from `$SB/downloads/reflex-examples` @ ebe19ff into `$W/up/apps/<app>` (github-stats + upload QA patches
  applied, rxconfig venv guard `QA_EXPECT_VENV`). Env: `. $SB/apps/examples_ui/env_eu.sh`.
  NOTE: a first staging attempt with a broken `$W` created `/apps/examples_ui` at the filesystem root (fixture copy only,
  no servers); the sandbox refused my `rm -rf` of it — leave it for a human to delete.
- [x] base venvs `$SB/envs/examples_ui-<app>` = `reflex==0.10.1` + requirements.txt, `-c $W/prev_constraints.txt`
  (freeze of `$SB/envs/prev`), no --prerelease, `--only-binary :all:`. Freezes in `$W/up/freeze/<app>-base.txt`.
- [x] counter, github-stats, overkey (stacked fail + minimal fix) — done
- [ ] reflexle, upload, clock, quiz — running (`$W/logs/seq-<app>.txt`)
- [x] fresh-install matrix n001 (uv/pip x 3.11/3.14/3.15 + plain pip 3.12) + dbcli; pip/uv in-place paths
- [ ] fresh `reflex init --template blank` + run per python; overkey fully-migrated API check; copy artifacts

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
