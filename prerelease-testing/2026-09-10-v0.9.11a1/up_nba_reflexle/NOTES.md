# Cluster `up_nba_reflexle` — upgrade testing 0.9.10.post2 -> 0.9.11a1

reflex-examples apps **nba** (pandas 3.0.1 + plotly 6.6.0 + statsmodels/scipy -> `rx.plotly`,
react-plotly.js 4.0.0 -> **4.1.0** in this train; `rx.data_table`/gridjs), **reflexle** (Wordle
clone driven by the third-party **reflex-global-hotkey 1.2.3**, keyboard-only) and **snakegame**
(hand-written custom `GlobalKeyWatcher` component + a singleton background-task game loop).
Date: 2026-09-11. Agent: `up_nba_reflexle`.

## Verdict

**No regressions in any of the three apps.** Every user flow behaves identically on reflex
0.9.10.post2 (previous stable) and on the full 0.9.11a1 alpha train — in-place upgrade, cold
`.web` rebuild, and `--env prod`. 65 checks per version-pass, all passing except two recorded
anomalies that reproduce identically on 0.9.10.post2 and are app-level, not framework-level.

| app | 0.9.10.post2 dev | 0.9.11a1 in-place dev | 0.9.11a1 cold dev | 0.9.11a1 prod | 0.9.10.post2 prod |
|---|---|---|---|---|---|
| nba (21 checks) | 21 P | 21 P | 21 P | 21 P | n/a |
| reflexle (23 checks) | 21 P + 2 A | 21 P + 2 A | 21 P + 2 A | 21 P + 2 A | 21 P + 2 A |
| snakegame (22 checks) | 22 P | 22 P | 22 P | 22 P | n/a |

P = pass, A = anomaly (both anomalies are pre-existing and explained below).

The in-place migration is clean on all three apps: reflex's bundled Bun moves 1.3.11 -> **1.4.0**,
`.web/utils/context.js` -> `context.jsx` plus a new `context-registry.js` (#7071), the app-root
`reflex.lock/bun.lock` stays at `lockfileVersion 1`, and the frontend pins bump exactly as
expected (per-app `artifacts/<app>/package.json.diff`):

```
react-router / @react-router/{node,dev,fs-routes}  8.3.0 -> 8.3.1
isbot        5.2.1 -> 5.2.2      sonner   2.0.7 -> 2.0.8
postcss      8.5.23 -> 8.5.26    postcss-import 16.1.1 -> 17.0.0
vite         8.2.0 -> 8.2.2
react-plotly.js 4.0.0 -> 4.1.0   (nba only; plotly.js itself stays 3.7.0)
```

A cold run (`rm -rf .web`) converges to a **byte-identical** `.web/package.json` for all three
apps. No new custom-component import/prop warnings from `reflex-global-hotkey` under the new
frontend pins, in dev or prod, in the browser console or the server log.

### react-plotly.js 4.1.0 is behaviour-neutral for this app

The nba scatter/histogram render byte-for-byte the same on both versions: the driver fingerprints
each plot (trace count, point count, titles, legend entries, axis ticks, `svg.main-svg` innerHTML
length) and 0.9.10.post2 and 0.9.11a1 agree exactly — e.g. default filters give
`traces=6, points=445, svglen=106417` on the scatter and `traces=1, points=22, svglen=12863` on
the histogram on every run (`artifacts/nba/*/results.json`). `use_resize_handler=True` still
re-lays-out on a viewport change (638px -> 704px), and the empty-dataframe path still degrades to
a bare `go.Figure()` (0 traces, no crash) and recovers.

## Ports / envs / one-time setup

- Reserved range used: nba FP/BP **5540/9940**, reflexle **5541/9941**, snakegame **5542/9942**;
  prod (same port for both) reflexle **5545**, nba **5546**, snakegame **5547**. One dev server
  at a time.
- Per-app venvs (Python 3.11): `$SB/envs/up_nba_{nba,reflexle,snakegame}`. Driver venv
  `$SB/envs/driver` (Playwright; chromium at `/opt/pw-browsers/chromium`).
- `REFLEX_DIR=$SB/reflex_dirs/<app>` per app (set by `serve.sh`) isolates reflex's own bun
  install, so the 0.9.10.post2 baseline picks up the system bun 1.3.11 from PATH and the
  0.9.11a1 run performs the real bun 1.4.0 install/migration itself.
- **nba env workaround (not a finding):** upstream `nba/views/table.py` does
  `pd.read_csv("https://media.geeksforgeeks.org/wp-content/uploads/nba.csv")` at *import* time;
  this container's egress proxy answers `CONNECT tunnel failed, response 403` for that host, so
  the app cannot start at all here. The identical dataset (same 9 columns, 457 rows) is vendored
  to `nba/data/nba.csv` (copied from `/home/user/reflex/docs/app/data/nba.csv`) and the two lines
  are patched to read the local path. Everything downstream (pandas filtering, plotly figures,
  gridjs table) is untouched. Both versions run the same patched source.
- reflexle's Google-Fonts `<link>` (`fonts.googleapis.com`) fails with `ERR_CONNECTION_RESET` in
  the browser: Chromium has no proxy configured in this container. Environmental, identical on
  both versions, filtered out of the driver's "bad responses" check.

## Rerun instructions

```sh
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
WD=$SB/apps/up_nba_reflexle          # nba/ reflexle/ snakegame/ drive_*.py serve.sh stop.sh
DRIVER=$SB/envs/driver/bin/python

# 0. app sources: copy from /home/user/reflex-dev/reflex-examples/{nba,reflexle,snakegame}
#    then apply the nba CSV workaround (see above) -- or just use the copies in this directory.

# --- baseline 0.9.10.post2 (per app; nba shown) --------------------------------------
uv venv $SB/envs/up_nba_nba --python 3.11
cd $WD/nba && uv pip install --python $SB/envs/up_nba_nba/bin/python \
  'reflex==0.9.10.post2' -r requirements.txt          # NO --prerelease on the baseline
cd $WD && ./serve.sh $WD/nba $SB/envs/up_nba_nba 5540 9940 logs/nba_0910_dev.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_nba.py http://localhost:5540 artifacts/nba/0910 0910 $WD/nba
cp $WD/nba/.web/package.json artifacts/nba/pre_upgrade_state/package.json
./stop.sh $WD/nba 5540 9940

# --- in-place upgrade to the FULL alpha train (same venv, same .web/, same reflex.lock/) ---
cd $WD/nba && uv pip install --python $SB/envs/up_nba_nba/bin/python --prerelease=allow \
  'reflex==0.9.11a1' 'reflex-base==0.9.11a1' 'reflex-components-radix==0.9.9a1' \
  'reflex-components-code==0.9.5a1' 'reflex-components-moment==0.9.4a1' \
  'reflex-components-plotly==0.9.6a1' 'reflex-components-recharts==0.9.3a1' \
  'reflex-components-sonner==0.9.3a1' 'reflex-hosting-cli==0.1.72a1' -r requirements.txt
cd $WD && ./serve.sh $WD/nba $SB/envs/up_nba_nba 5540 9940 logs/nba_0911_inplace_dev.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_nba.py http://localhost:5540 artifacts/nba/0911_inplace 0911_inplace $WD/nba
diff -u artifacts/nba/pre_upgrade_state/package.json $WD/nba/.web/package.json
./stop.sh $WD/nba 5540 9940

# --- cold run --------------------------------------------------------------------------
rm -rf $WD/nba/.web
cd $WD && ./serve.sh $WD/nba $SB/envs/up_nba_nba 5540 9940 logs/nba_0911_cold_dev.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_nba.py http://localhost:5540 artifacts/nba/0911_cold 0911_cold $WD/nba
./stop.sh $WD/nba 5540 9940

# --- prod (SAME port for frontend and backend) ------------------------------------------
cd $WD && ./serve.sh $WD/nba $SB/envs/up_nba_nba 5546 5546 logs/nba_0911_prod.log --env prod
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_nba.py http://localhost:5546 artifacts/nba/0911_prod 0911_prod $WD/nba
./stop.sh $WD/nba 5546
```

reflexle / snakegame are identical with `drive_reflexle.py` / `drive_snakegame.py`, ports
5541/9941 and 5542/9942 (prod 5545 / 5547).

To reproduce the **0.9.10.post2 prod** control for reflexle, pin the stable component packages
too (a bare `reflex==0.9.10.post2` install leaves the alpha sub-packages in place):

```sh
cd $WD/reflexle && uv pip install --python $SB/envs/up_nba_reflexle/bin/python \
  'reflex==0.9.10.post2' 'reflex-base==0.9.10.post2' 'reflex-components-radix==0.9.8' \
  'reflex-components-code==0.9.4' 'reflex-components-moment==0.9.3' \
  'reflex-components-plotly==0.9.5' 'reflex-components-recharts==0.9.2' \
  'reflex-components-sonner==0.9.2' 'reflex-hosting-cli==0.1.71' -r requirements.txt
rm -rf $WD/reflexle/.web
cd $WD && ./serve.sh $WD/reflexle $SB/envs/up_nba_reflexle 5545 5545 logs/reflexle_0910_prod.log --env prod
```

### Driver signatures

- `drive_nba.py        <frontend_url> <artifacts_dir> <label> [<app_dir>]` — 21 checks
- `drive_reflexle.py   <frontend_url> <artifacts_dir> <label> [<app_dir>]` — 23 checks, real key presses
- `drive_snakegame.py  <frontend_url> <artifacts_dir> <label> [<app_dir>]` — 22 checks, real key presses
- `probe_reflexle_lost.py <frontend_url> <out_dir>` — isolated probe: plays six guaranteed-losing
  guesses and dumps every websocket frame (`ws_frames.json`) plus screenshots
- `repro_reflexle_enum_delta.py` / `repro_dataclass_backend_var_delta.py` — in-process probes of
  the delta produced for an enum-valued computed var and for a cached var that depends only on a
  mutable-dataclass backend var (run from the app dir with that app's venv python; both showed the
  framework behaving correctly, see "Investigated and cleared" below)

`serve.sh <app_dir> <venv_dir> <FP> <BP> <log> [extra reflex-run args]` starts the app with the
per-app `REFLEX_DIR`, waits for HTTP 200, writes the pgid to `<app>/logs/server.pid`.
`stop.sh <app_dir> <ports...>` kills the process group and verifies the ports are free.
Do NOT export `NO_PROXY` into the server environment (it breaks bun installs through the proxy);
only curl/Playwright bypass the proxy.

## What each driver covers

### nba — `rx.plotly` x2, `rx.data_table`, `rx.select`, range `rx.slider`
page load / navbar; 457-row gridjs table (render, search "Curry", sort by header, pagination);
both plotly figures render with the right titles; the `px.scatter(trendline="lowess")` produces
5 position traces + the statsmodels "Overall Trendline"; position select -> figure recompute
(6 traces -> 2); college select -> recompute; age slider (keyboard) and salary slider (mouse
drag — its 0..25 000 000 range with step 1 makes ArrowRight useless) both fire
`on_value_commit` and update the badges; filters that yield an empty dataframe render bare
`go.Figure()`s (0 traces) and recover; color-mode toggle; viewport resize against
`use_resize_handler=True`; hard reload re-hydrates; `.web/package.json` recorded.

### reflexle — third-party `reflex-global-hotkey`, `@rx.memo`, `rx.toast`, background event
real `page.keyboard.press()` for every letter; Backspace; Ctrl+Backspace; the "word too short"
sonner toast; the invalid-word shake cleared 0.3 s later by the `@rx.event(background=True)`
handler; a valid guess colouring the row and the on-screen keyboard; duplicate-guess rejection;
on-screen keyboard buttons including ⌫ and ↵ (each a `@rx.memo` component with a per-button
event arg); high-contrast toggle recolouring already-revealed cells; color mode; state surviving
a reload; a deterministic **LOST** end state (six words that are in `valid_guess` but never in
`possible_solution`) revealing "Word is …"; keys ignored after game over; play-again resetting the
board and `rx.set_focus("guesses")` landing on the hidden button; hotkeys still working after the
reset (the `useEffect` listener re-attaches); a second browser context getting its own game.

### snakegame — custom `GlobalKeyWatcher` component + singleton background loop
361-cell grid and the RATE/SCORE/MAGIC stat boxes; RUN starts the background loop and the
`rx.switch(checked=State.running)` follows the backend; the loop pushes deltas ~2/s; PAUSE
freezes it; **Escape** toggles run/pause through the custom key map (`flip_switch(~State.running)`);
the switch itself drives the loop; 10x ArrowUp + 5x ArrowLeft deterministically walks the head
from (10,15) onto the food at (5,5) (SCORE 0->1, MAGIC 1->2, RATE 10->12); vim keys h/j/k/l;
the mouse arrow buttons; three `,` presses (relative-left turns) fold the head into the body for a
deterministic **Game Over** with the dead cell recoloured red; the loop stops on death; RUN after
death resets the game; state survives a reload and keys still work afterwards; a second context
runs its own independent game.

## Anomalies (both pre-existing on 0.9.10.post2 — regression = NO)

### A1. reflexle: `Ctrl+Backspace` is indistinguishable from `Backspace`

`Reflexle.received_letter` has an `elif letter == "Ctrl+Backspace":` branch that clears the whole
row, but `reflex_base.event.key_event` forwards only `e.key` (modifiers arrive separately in
`KeyInputInfo`), so the browser's Ctrl+Backspace is delivered as `"Backspace"` and deletes a single
letter. Dead branch in the example, identical on both reflex versions, in dev and prod.
Evidence: `artifacts/reflexle/*/results.json` -> `ctrl_backspace_deletes_one_letter`.
If anything is worth doing here it is upstream in reflex-examples (use the `KeyInputInfo.ctrl_key`
the event already carries).

### A2. reflexle: the "Invalid word." / "You already guessed this word." toasts never appear

`ReflexleGame.guess()` *builds* `rx.toast(...)` and returns it, but `Reflexle.received_letter`
throws that return value away:

```python
event = self._word.guess(current_guess)
if event is not None:          # <- the EventSpec is only used as a boolean
    self.is_wrong_guess = True
    return type(self).set_is_wrong_guess_false
```

so the user only gets the red shake. The third toast path (`"Word must be 5 characters long."`,
returned directly from the handler) *does* fire, which proves sonner itself works — so this is an
upstream example bug, not a framework one. Identical on both versions.
Evidence: `invalid_word_toast_dropped_by_app` / `duplicate_guess_rejected` in every
`artifacts/reflexle/*/results.json`.

### A3. reflexle in prod: `GET /favicon.ico` -> 404 in the browser console

reflexle ships no `assets/favicon.ico` (unlike nba and snakegame), but the compiled HTML always
carries `<link rel="icon" href="/favicon.ico">`. In **dev** this is invisible because the
react-router dev server answers *every* unknown path with `200 text/html` (checked:
`/does-not-exist.ico` -> `200 text/html`); in **prod** it is a real 404 and shows up as a console
error on every page load. Reproduced identically on 0.9.10.post2 prod (`curl -I
http://localhost:5545/favicon.ico` -> 404 on both), so regression = no. Worth knowing because the
dev server masks *all* missing-asset 404s until you build for production.
Evidence: `artifacts/reflexle/0911_prod/console.json`, `artifacts/reflexle/0910_prod/console.json`.

### A4. `@rx.memo` deprecation warnings on every compile (reflexle)

Both versions print, twice per compile:

```
DeprecationWarning: `@rx.memo` on `character_box` without explicit annotations has been
deprecated in version 0.9.3. ... It will be completely removed in 1.0.
```

Pre-existing (0.9.3), unchanged by this train, and the app still compiles and behaves correctly —
but it is the only warning a user of this example sees, and the example in reflex-examples has not
been updated. Evidence: `logs/reflexle_0910_dev.log`, `logs/reflexle_0911_inplace_dev.log`.

### A5. snakegame: the board is uniformly empty until the first tick

`State.cells` starts as 361 `GRID_EMPTY`s and is only painted inside the loop, so a freshly loaded
page shows no snake and no food until you press RUN. App design, identical on both versions;
recorded because it looks like a rendering failure at first glance.

## Investigated and cleared (no defect)

- **"The LOST banner never appears"** — my first driver run reported this, and it looked like a
  cached-computed-var delta bug. It is a *driver* bug: the banner has
  `text_transform="uppercase"`, Playwright's `inner_text()` returns the transformed text
  ("WORD IS MARSH"), and the assertion was case-sensitive. `probe_reflexle_lost.py` captured the
  websocket frames and the framework is correct: after the sixth guess the delta carries
  `"game_status_rx_state_":2` and `"correct_word_rx_state_":"marsh"`, and the compiled condition
  (`.web/app_components/reflexle/reflexle.jsx`,
  `game_status_rx_state_?.valueOf?.() === 2?.valueOf?.()`) matches, so the banner renders.
  Enum-valued computed vars serialize to their `.value` over the socket, on both versions.
  Evidence: `artifacts/reflexle/lost_probe_0910/ws_frames.json` + `lost_probe.png`.
- **Cached vars that depend only on a mutable-dataclass backend var** — `repro_dataclass_backend_var_delta.py`
  and `repro_reflexle_enum_delta.py` confirm that mutating `self._word.guesses` in place marks
  `game_status` / `correct_word` / `guesses_count` dirty and puts them in the delta on every event
  (0.9.10.post2 and 0.9.11a1 alike).
- **statsmodels/scipy heavy pins** — `pandas==3.0.1 plotly==6.6.0 statsmodels==0.14.6 scipy==1.17.1`
  install and import cleanly next to both reflex versions; the lowess trendline renders.
- **Third-party `reflex-global-hotkey` 1.2.3 under the new frontend pins** — it imports
  `reflex.Fragment`, `reflex.Var`, `reflex.event.{EventHandler,EventType,key_event,KeyInputInfo}`
  and `reflex.utils.imports`; all still resolve on 0.9.11a1 with no deprecation warning, and its
  `add_hooks` `useEffect` keeps working across resets, reloads and the prod bundle.
- **prod multi-worker delta loss (campaign FINDING-003)** — not hit here: granian spawned a single
  worker in all three prod runs, so backend-initiated deltas (snakegame's loop) were delivered 100%.

## Files

```
NOTES.md                       this file
nba/ reflexle/ snakegame/      app sources as run (nba carries the vendored data/nba.csv)
serve.sh stop.sh               server lifecycle helpers
drive_common.py                shared Playwright plumbing (console/network/screenshot capture)
drive_nba.py drive_reflexle.py drive_snakegame.py
probe_reflexle_lost.py         websocket-level probe of the LOST end state
repro_reflexle_enum_delta.py   in-process delta probe (enum computed var)
repro_dataclass_backend_var_delta.py
artifacts/<app>/<run>/         screenshots, results.json, console.json, bad_responses.json,
                               page_errors.json, npm_versions.json per run
artifacts/<app>/package.json.diff          pre- vs post-upgrade .web/package.json
artifacts/<app>/{pre_upgrade,post_inplace,post_cold}_state/package.json
logs/<app>_<run>.log           reflex server logs (--loglevel debug)
logs/<app>_<run>_driver.log    driver stdout (per-check pass/fail lines)
```
