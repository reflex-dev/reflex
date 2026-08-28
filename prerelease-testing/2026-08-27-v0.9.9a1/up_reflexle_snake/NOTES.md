# up_reflexle_snake — upgrade testing reflexle + snakegame (0.9.8 -> 0.9.9a1)

Cluster: `up_reflexle_snake` — UPGRADE testing of two reflex-examples apps:

- **reflexle** — wordle clone; third-party `reflex-global-hotkey` (1.2.3) keyboard input,
  `@rx.memo` components, background task (shake auto-clear), enum state vars, sonner toasts.
- **snakegame** — arrow-key gameplay; singleton background-task game loop (2 ticks/s state
  churn), custom `rx.Fragment` subclass with `add_hooks` keydown wiring, 361-cell
  `rx.foreach` grid, event-throughput stress.

**Verdict: NO REGRESSIONS.** Both apps behave identically on 0.9.8 and 0.9.9a1
(in-place upgrade AND cold fresh-.web install). All Playwright checks pass on all six
runs (reflexle 17 checks x 3 runs, snakegame 19 checks x 3 runs). The in-place
migration (lockfile restore, react-router 7->8 bump, react-router-dom prune, vite bump)
completed cleanly with no new warnings, no console errors, no failed requests.

## Procedure (exact rerun instructions)

Working dir used: `$SB/apps/up_reflexle_snake` where
`SB=/tmp/claude-0/-home-user-reflex/20b6ffc8-8244-5bac-b158-8501871b3811/scratchpad`.
Apps copied from `/home/user/reflex-dev/reflex-examples/{reflexle,snakegame}`.
Ports: reflexle 3180/8180, snakegame 3181/8181. One server at a time.

Per app (`<app>` = reflexle | snakegame):

```sh
# 1. venv on stable 0.9.8 (resolves like a real user's today)
uv venv <app>/venv --python 3.11
uv pip install --python <app>/venv/bin/python -r <app>/requirements.txt 'reflex==0.9.8'

# 2. baseline run + browser verification
cd <app> && REFLEX_TELEMETRY_ENABLED=false ./venv/bin/reflex run \
  --frontend-port <FP> --backend-port <BP> --loglevel debug > ../logs/<app>_098_run1.log 2>&1 &
# poll http://localhost:<FP>/ until 200, then:
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drive_<app>.py http://localhost:<FP> shots/<app>_098 098

# 3. IN-PLACE upgrade (same venv, same app dir, .web/ + reflex.lock/ preserved)
cp <app>/.web/package.json artifacts/<app>/package.json.098   # before snapshot
kill <server pids>
uv pip install --python <app>/venv/bin/python --prerelease=allow -U 'reflex==0.9.9a1'
# re-run server (first run = migration run), diff package.json, re-run driver with tag 099a1

# 4. cold path
kill <server pids>; rm -rf <app>/.web
# re-run server (tag 099a1_cold), re-run driver
```

Driver scripts: `drive_reflexle.py`, `drive_snakegame.py` (this dir). Each writes
screenshots, `<tag>_results.json` (per-check pass/fail) and `<tag>_console.json`
(full console/pageerror/failed-request capture) into its shots dir.

## What the drivers verify

**drive_reflexle.py** (17 checks): grid renders 6x5 blank; real keydown via Playwright
keyboard reaches backend through reflex-global-hotkey; typing "crane" echoes into tiles;
Enter colors the row (green/yellow/gray incl. 0.3s-per-tile transition delays); on-screen
keyboard buttons recolor; short-guess toast ("Word must be 5 characters long."); invalid
5-letter word auto-clears via `@rx.event(background=True)` task; Backspace editing;
on-screen key + backspace click path; high-contrast toggle swaps to `#F5793A`/`#85C0F9`;
color-mode toggle flips `light`/`dark` class; play-again resets grid; a post-reset guess
still colors; console/network clean.

**drive_snakegame.py** (19 checks): 361-cell grid + RATE=10/SCORE=0/MAGIC=1 stats; RUN
starts singleton background loop (switch reflects `running`); tick throughput (8 board
updates observed in 4s at 2 ticks/s — full event stream flowing); Escape pause/resume
(`flip_switch(~State.running)` key_map wiring); deterministic food chase: ArrowUp until
head reaches food row (poll head via board diff), ArrowLeft onto food at (5,5) —
SCORE=1/MAGIC=2/RATE=12; four quickly-queued "." (relative-right) turns loop the snake
into itself -> "Game Over 🐍", red GRID_DEAD cell, switch off; RUN after death resets and
restarts; pausing via the switch itself; console/network clean.

Cell classification is done by probing computed colors of `--gray-5/--grass-9/--blue-9/
--red-9` CSS vars at runtime, so it is theme-robust.

## Migration observations (first 0.9.9a1 run, in-place, both apps)

From `logs/<app>_099a1_run1.log`:

1. `Restoring lockfiles.` — `reflex.lock/bun.lock` + `reflex.lock/package.json`
   (created by the 0.9.8 runs; the reflex.lock/ mechanism already exists in 0.9.8)
   copied into `.web/`.
2. `bun remove --legacy-peer-deps react-router-dom` — "Removing unused frontend
   packages" prunes react-router-dom from package.json. Clean, no errors.
3. Dev+runtime deps reinstalled: `@react-router/{node,dev,fs-routes}` and
   `react-router` 7.18.2 -> **8.3.0**, `vite` 8.0.16 -> **8.2.0**. Other pins unchanged.
4. `postcss` override kept at 8.5.23 (`overrides` block unchanged).
5. Lockfiles saved back to `reflex.lock/`.
6. Node 22.22.2 / bun 1.3.11 detected and used, no re-download.

package.json before/after + diffs: `artifacts/<app>/package.json.{098,099a1}` and
`artifacts/<app>/package.json.diff`. Both apps have the identical dep diff.

Cold run (rm -rf .web): frontend back up in ~10s; `Install Frontend Packages: 0.18s`
(reflex.lock restore + warm bun cache); no npmmirror "Failed to connect" lines occurred
in these runs; no new warnings; all checks pass.

## Benign quirks (present on BOTH versions — not regressions)

- Server log: `Warning: reflex_base.plugins.sitemap.SitemapPlugin plugin is enabled by
  default, but not explicitly added to the config...` (both apps, both versions).
- Server log (reflexle): `DeprecationWarning: @rx.memo on character_box/keyboard_button
  without explicit annotations has been deprecated in version 0.9.3...` (both versions).
- Server log (0.9.8 only, expected): `Your version (0.9.8) of reflex is out of date.
  Upgrade to 0.9.8.post1`.
- Browser console (reflexle): one `Failed to load resource: net::ERR_CONNECTION_RESET`
  for `fonts.googleapis.com` — the test sandbox blocks Google Fonts from the browser;
  environment artifact, identical on both versions.
- App-logic quirk in reflexle (both versions, arguably an example bug, not a framework
  issue): `received_letter` discards the `rx.toast("Invalid word.")` /
  `rx.toast("You already guessed this word.")` EventSpec returned by
  `ReflexleGame.guess()` (it returns the shake background task instead), so those toasts
  never appear. Only the "Word must be 5 characters long." toast is reachable.
- snakegame pause semantics (both versions): the game loop checks `self.running` before
  its `asyncio.sleep`, so one in-flight tick lands up to 0.5s after pausing. The drivers
  account for this.

## Artifact map (this directory)

```
NOTES.md                      this file
drive_reflexle.py             Playwright driver, reflexle
drive_snakegame.py            Playwright driver, snakegame
reflexle/, snakegame/         app sources as tested (venv/.web excluded)
artifacts/<app>/package.json.098 / .099a1 / .diff
artifacts/reflexle/reflex.lock.after_upgrade/   lockfile dir snapshot post-migration
logs/<app>_{098_run1,099a1_run1,099a1_cold}.log full --loglevel debug server logs
shots/<app>_{098,099a1,099a1_cold}/             screenshots + results/console JSON
```
