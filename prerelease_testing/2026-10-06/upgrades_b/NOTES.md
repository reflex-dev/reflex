# Cluster `upgrades_b`: in-place upgrade regression, reflex-examples set B (0.9.12 → 0.10.0a1)

Date 2026-10-06. Host: 4-CPU Linux container shared with other agents. Python 3.12.3, Node 22.22.0, bun 1.4.2,
uv 0.11.32, Playwright 1.63 with Chromium at `/opt/pw-browsers/chromium`. Every framework install came from
PyPI into isolated venvs under `$SB/envs/`. Nothing was installed from or run inside `/home/user/reflex`;
release source was only read with `git show origin/r/pre-2026.10.05-37378928999:…`. Apps were copied from
`$SB/downloads/reflex-examples` (commit `ebe19ff`).

`SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`, `W=$SB/apps/upgrades_b`.

## Verdict

**No regression was found in any of the 7 apps.** twitter, upload, lorem-stream, local-component, nba, quiz
and snakegame each went through the same sequence:

1. Drive the app in Chromium on 0.9.12 in its own venv.
2. Upgrade **in place**: same venv and same app dir, keeping `.web/`, `reflex.lock/`, `.states/`,
   `reflex.db` and `uploaded_files/`.
3. Re-drive with identical drivers.
4. Re-drive again after `rm -rf .web` (cold).

Every check that passed on 0.9.12 passed on 0.10.0a1 in place and cold. Console-signature sets and failed
requests were identical, and no app produced page errors.

Prod coverage (`--env prod`, one port):
- twitter (with Redis), upload, local-component and lorem-stream (with Redis, 9 granian workers) were run on
  both versions.
- nba was run in prod on the alpha only.
- `reflex export` for twitter and local-component gave identical zip file lists on both versions.

Highlights:
- **twitter, login across the upgrade.** With Redis (the setup where sessions outlive a process), 0.10.0a1
  restored sessions pickled by 0.9.12 **without re-login**. The pickled `State.user` is a SQLModel `User` row
  object. This held both for fresh contexts seeded with the old tab token and for a 0.9.12 prod tab that
  stayed open across stop → upgrade → start. That tab kept working on the old bundle, then switched to the new
  bundle on manual reload and stayed logged in.
  With the default disk state manager (dev), users are logged out after the upgrade. That is **not a
  regression**: `reflex run` deletes `.states/*` on every start (`reset_disk_state_manager()`, unconditional,
  identical code in both versions). I confirmed it empirically with a 0.9.12→0.9.12 restart.
  Users, tweets, follows and the alembic head all survive. `reflex db migrate` and `makemigrations` after the
  upgrade are no-ops.
- **upload.** react-dropzone moved 15.0.0→17.0.0, an ESM-only release that dropped prop-types and now needs
  React ≥18. The following all behave identically on both versions, in dev and prod:
  - selection display, re-select, `rx.clear_selected_files`, drag & drop
  - hostile filenames (`../`, `..\..\`, absolute, nested, unicode/spaces/parens): sanitized into the upload
    dir, nothing escapes
  - 12 MB sha256 roundtrip
  - progress bar, cancel (no partial file), upload after cancel, served bytes through the rendered links
  - multi-client behaviour: concurrent throttled uploads, a client disconnecting mid-upload, a third client's
    events
- **nba, #7226.** The plotly change is a visible improvement, not a regression. A plain-string `layout`
  title (literal or state-driven) renders on 0.10.0a1 (normalized to `{text: …}`) and was silently dropped on
  0.9.12, because plotly.js 3.7.0 ignores string titles. The px figure titles render identically on both.
  Filters (select and range slider) recompute identical point and trace counts on both versions.
- **local-component (local `.jsx` via `rx.asset(shared=True)`).**
  - Compiles to a byte-identical import on both versions:
    `import {Hello} from "$/public//external/local_component/hello/hello.jsx?v=0ebba69a"`.
  - Passes all 15 checks in dev, in-place, cold, and prod on both versions.
  - Editing the `.jsx` while `reflex run` is live hot-swaps it on both versions with no full reload, keeping
    state.

Issues: one low-severity UX gap on the alpha's intentional `reflex component` CLI removal (I-1). The rest are
anomalies or context, listed below.

## Rerun instructions

Ports (reserved range 3180-3199 / 8180-8199):

| app | ports |
|---|---|
| twitter dev | 3180/8180 |
| twitter-redis prod | 3181 (single port) |
| upload dev | 3182/8182 |
| upload prod | 3183 |
| upload-012 (0.9.12 copy) | dev 3184/8184, prod 3185 |
| lorem dev | 3186/8186 |
| local-component dev | 3187/8187 |
| local-component prod | 3188 |
| lc-012 prod | 3189 |
| nba dev | 3190/8190 |
| nba prod | 3191 |
| quiz | 3192/8192 |
| snake | 3193/8193 |
| lorem-redis prod | 3194 (0.9.12), 3195 (alpha) |
| local-component hot-edit | 3196/8196 (0.9.12), 3197/8197 (alpha) |
| twitter-exp012 restart control | 3198/8198 |
| redis | 8189 |

Helpers in `bin/` are copied from upgrades_a, with `ports.sh` re-ranged:
- `run_app.sh <appdir> <venv> <fp> <bp> <log> [reflex run args]` starts `reflex run --loglevel debug` under
  setsid, records `run/<app>.pid`, and polls `/` and `/ping` until both answer 200.
- `stop_app.sh <appdir> <ports…>` sends SIGTERM to the main pid and reports the exit time or orphans, then
  hard-kills.
- `ports.sh` lists listeners in the range.

```bash
export SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad W=$SB/apps/upgrades_b
cd $SB/downloads/reflex-examples && tar --exclude=.web --exclude=node_modules --exclude=.states --exclude=__pycache__ \
  --exclude='*.db' -cf - twitter upload lorem-stream local-component nba quiz snakegame | tar -C $W -xf -
# QA patches (patches/*.diff; default behaviour = upstream unless the env var is set):
#   upload: QA_UPLOAD_EXTRAS=1 renders a Clear button (rx.clear_selected_files) + Ping counter (event latency probe)
#   nba:    CSV stub (always on: media.geeksforgeeks.org answers CONNECT 403 through the proxy; nba_local.csv copied from
#           prerelease-testing/2026-09-18-v0.9.12a1/up_examples_c/apps/nba) + QA_NBA_EXTRAS=1 renders 2 extra plots
#           with plain-string layout titles (literal and state-driven) for #7226
# per-app venv, baseline resolved like a stable user (NO prerelease flag)
cd $SB && uv --no-config venv --python 3.12 $SB/envs/upgrades_b-<app>
cd $SB && uv --no-config pip install --python $SB/envs/upgrades_b-<app>/bin/python -r $W/<app>/requirements.txt 'reflex==0.9.12'
# twitter needs a DB first (the app ships no alembic dir):
cd $W/twitter && $SB/envs/upgrades_b-twitter/bin/reflex db init && .../reflex db makemigrations --message init && .../reflex db migrate
# baseline run + drive (example twitter; DRV = NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python)
$W/bin/run_app.sh $W/twitter $SB/envs/upgrades_b-twitter 3180 8180 $W/logs/twitter-base.server.log
$DRV $W/scripts/drive_twitter.py http://localhost:3180/ $W/shots/twitter tw-base base $W/run/tw_tokens.json
$W/bin/stop_app.sh $W/twitter 3180 8180
# in-place upgrade (same venv + same app dir), then re-run + re-drive, then cold
cd $SB && uv --no-config pip install --python $SB/envs/upgrades_b-<app>/bin/python --prerelease=allow -U 'reflex==0.10.0a1'
QA_EXPECT_SESSION=0 $DRV $W/scripts/drive_twitter.py http://localhost:3180/ $W/shots/twitter tw-up up $W/run/tw_tokens.json
rm -rf $W/<app>/.web   # cold run, same commands
# prod: REFLEX_API_URL=http://localhost:<P> $W/bin/run_app.sh <app> <venv> <P> <P> <log> --env prod
```

Drivers (`scripts/`, run with `$SB/envs/driver/bin/python` and `NO_PROXY` on the driver only). Each asserts
it runs from the driver venv and writes `<outdir>/<tag>.json`. That file holds the checks, the full console,
page errors, failed and ≥400 requests and `/_event` websocket frames. Screenshots go next to it. `harness.py`
is upgrades_a's harness plus an `expected_bad` hook for requests a flow aborts on purpose (the upload cancel).

| script | invocation |
|---|---|
| `drive_twitter.py` | `<url> <outdir> <tag> base\|up <tokfile>`. Env vars: `QA_USER_SUFFIX` (usernames alice<sfx>/bob<sfx>); `QA_EXPECT_SESSION=1\|0` (the up mode expects the seeded old tokens to still be logged in (Redis) or to land on /login (disk)) |
| `stale_tab_twitter.py` | `<url> <outdir> <tag> <ctldir>`. Keeps ONE logged-in tab open; operator touches `<ctldir>/down` and `<ctldir>/up`. Env vars: `QA_STALE_USER`, `QA_STALE_FOLLOW`, `QA_EXPECT_SESSION` |
| `drive_upload.py` | `<url> <outdir> <tag> <upload_dir> <fixtures_dir>` (server with `QA_UPLOAD_EXTRAS=1`) |
| `probe_upload_multiclient.py` | `<url> <outdir> <tag> <upload_dir> <fixtures_dir>` (server with `QA_UPLOAD_EXTRAS=1`) |
| `drive_lorem.py` | `<url> <outdir> <tag>` |
| `drive_local_component.py` | `<url> <outdir> <tag>` |
| `probe_lc_hot_edit.py` | `<url> <outdir> <tag> <app_dir>`. Edits and then restores `local_component/hello.jsx` |
| `drive_nba.py` | `<url> <outdir> <tag>` (server with `QA_NBA_EXTRAS=1`) |
| `drive_quiz.py` | `<url> <outdir> <tag>` |
| `drive_snakegame.py` | `<url> <outdir> <tag>` |
| `compare_runs.py` | `<json>…`: check-status and console-signature diff between runs |

### Scenario commands not covered by the generic recipe

**twitter + Redis + prod** (venv `upgrades_b-twredis`, app copy `twitter-redis` = `twitter` with
`reflex.db`/alembic, without `.web`/`.states`):

```bash
cd $W && tar --exclude=.web --exclude=.states --exclude=__pycache__ --exclude=reflex.lock -cf - twitter | tar -C $W -xf - --transform 's#^twitter#twitter-redis#'
cd $SB && uv --no-config venv --python 3.12 $SB/envs/upgrades_b-twredis && uv --no-config pip install --python $SB/envs/upgrades_b-twredis/bin/python -r $W/twitter/requirements.txt 'reflex==0.9.12'
redis-server --port 8189 --save '' --appendonly no &
R="REFLEX_REDIS_URL=redis://localhost:8189 REFLEX_API_URL=http://localhost:3181"
env $R $W/bin/run_app.sh $W/twitter-redis $SB/envs/upgrades_b-twredis 3181 3181 $W/logs/twredis-base-prod.server.log --env prod
QA_USER_SUFFIX=r $DRV $W/scripts/drive_twitter.py http://localhost:3181/ $W/shots/twredis twr-base-prod base $W/run/twr_tokens.json
# control: plain 0.9.12 restart, sessions must survive
$W/bin/stop_app.sh $W/twitter-redis 3181; env $R $W/bin/run_app.sh ... twredis-base-prod-restart.server.log --env prod
QA_EXPECT_SESSION=1 QA_USER_SUFFIX=r $DRV $W/scripts/drive_twitter.py http://localhost:3181/ $W/shots/twredis twr-base-restart up $W/run/twr_tokens.json
# stale tab across the upgrade
QA_EXPECT_SESSION=1 QA_STALE_USER=daver QA_STALE_FOLLOW=alicer $DRV $W/scripts/stale_tab_twitter.py http://localhost:3181/ $W/shots/twredis twr-stale-prod $W/run/stale_twr &
$W/bin/stop_app.sh $W/twitter-redis 3181; touch $W/run/stale_twr/down
cd $SB && uv --no-config pip install --python $SB/envs/upgrades_b-twredis/bin/python --prerelease=allow -U 'reflex==0.10.0a1'
env $R $W/bin/run_app.sh $W/twitter-redis $SB/envs/upgrades_b-twredis 3181 3181 $W/logs/twredis-up-prod.server.log --env prod; touch $W/run/stale_twr/up
QA_EXPECT_SESSION=1 QA_USER_SUFFIX=r $DRV $W/scripts/drive_twitter.py http://localhost:3181/ $W/shots/twredis twr-up-prod up $W/run/twr_tokens.json
QA_USER_SUFFIX=r2 $DRV $W/scripts/drive_twitter.py http://localhost:3181/ $W/shots/twredis twr-up-prod-base base $W/run/twr2_tokens.json
cd $W/twitter-redis && $SB/envs/upgrades_b-twredis/bin/reflex export --loglevel debug      # alpha export
# 0.9.12 export of an identical copy, with the shared stable venv:
(copy -> twitter-exp012) && cd $W/twitter-exp012 && $SB/envs/stable/bin/reflex export --loglevel debug
```

**Other runs.**
- *0.9.12 baselines with the final drivers, or where the app venv was already upgraded.* These used the
  shared read-only `$SB/envs/stable` (0.9.12 + `reflex[db]`) on plain copies: `upload-012`, `lc-012` (prod and
  export) and `twitter-exp012` (the dev restart control).
- *lorem-stream prod+Redis baseline.* New venv `upgrades_b-lorem012` (0.9.12 + `lorem_text`) on the copy
  `lorem-redis`.
- *lorem-stream prod+Redis on the alpha.* Used the upgraded `upgrades_b-lorem-stream` venv.

## Resolution / upgrade mechanics

**Baseline freezes** (`freeze/<app>-base.txt`) are all identical in the reflex packages:

| package | version |
|---|---|
| reflex, reflex-base | 0.9.12 |
| reflex-components-code | 0.9.6 |
| reflex-components-core | 0.9.10.post1 |
| reflex-components-gridjs | 0.9.2.post1 |
| reflex-components-markdown | 0.9.4.post1 |
| reflex-components-moment | 0.9.4 |
| reflex-components-plotly | 0.9.7 |
| reflex-components-radix | 0.9.10.post1 |
| reflex-components-recharts | 0.9.4.post1 |
| reflex-components-sonner | 0.9.4 |
| reflex-components-dataeditor | 0.9.3.post1 |
| reflex-components-lucide | 1.0.4 |
| reflex-components-react-player | 0.9.2 |
| reflex-hosting-cli | 0.1.72 |
| wrapt | 2.3.0 |

Extra packages per app:
- twitter: sqlmodel 0.0.47, pydantic 2.13.5, alembic 1.20.0, sqlalchemy 2.0.54.
- lorem: lorem-text 3.0.
- nba: pandas 3.0.1, plotly 6.6.0, scipy 1.17.1, statsmodels 0.14.6, numpy 2.5.3. The pinned versions
  installed on 3.12 without relaxing.

**`uv pip install --prerelease=allow -U 'reflex==0.10.0a1'`** gives the same 13-line diff for every venv
(`freeze/*-base-to-up.diff`):
- reflex and reflex-base move to 0.10.0a1, and reflex-build-sdk 0.0.5 is added.
- The code, core, gridjs, markdown, moment, plotly, radix and recharts components move to 0.10.0a1.
- hosting-cli moves to 0.1.73a1 and wrapt to 2.5.0.
- sonner, dataeditor, lucide and react-player are unchanged.
- sqlmodel stays 0.0.47 for twitter, and `uv pip check` reports the result as compatible. This is upgrades_a
  I-1, which is under verification elsewhere and was not re-investigated here.

**`.web/package.json` diff after the upgrade** is identical for all apps (`pkg/*-base-to-up.package.diff`):
- react and react-dom 19.2.8→19.3.0
- react-error-boundary 6.1.2→6.1.6
- socket.io-client 4.8.3→4.8.4
- autoprefixer 10.5.4→10.6.1
- postcss 8.5.26→8.5.29
- vite 8.2.2→8.3.2
- upload only: **react-dropzone 15.0.0→17.0.0**

Cold runs converged to a byte-identical package.json for all 7 apps. `reflex.lock/` was synced to `.web/`
(sha256 recorded in `pkg/twitter-*.reflex.lock.ls`).

**First post-upgrade run** (`logs/twitter-up.server.log`):
1. "Restoring lockfiles".
2. `bun install --frozen-lockfile` (226 packages).
3. Two `bun add` steps move to the new pins, then "Saved lockfile".

There was no "lockfile had changes" message and no npmmirror fallback. Startup took 4–10 s on every
post-upgrade run, with no cliff.

**Shutdown with SIGTERM and no TTY:**
- 0.9.12 dev: the main pid never exits within 15 s and the react-router node process orphans the frontend
  port, on every run.
- 0.10.0a1: "Reflex app stopped." in 2–3 s with all ports free (#7328).
- 0.9.12 prod exits in about 2 s.

## Per-app results (`shots/<app>/<tag>.json`; pass/fail/anomaly)

| app | 0.9.12 | in-place 0.10.0a1 | cold | prod 0.9.12 | prod 0.10.0a1 |
|---|---|---|---|---|---|
| twitter (full flow `base`) | 21/0/0 `tw-base` | 14/0/0 `tw-up` (restore flow) | 14/0/0 `tw-cold`; full flow 21/0/0 `tw-cold-base` | Redis: 19/0/2 `twr-base-prod` | Redis: 19/0/2 `twr-up-prod-base` |
| twitter session across restart/upgrade | disk: 10/0/2 `tw-stale-restart-0912` (logged out, expected); Redis 0.9.12→0.9.12: 12/1*/2 `twr-base-restart` | disk: logged out (same as 0.9.12, `logs/tw-stale.driver.log`) | – | – | Redis 0.9.12→alpha: tokens 12/0/2 `twr-up-prod`, stale tab 8/0/3 `twr-stale-prod` |
| upload | 21/0/0 `up-base`, `up-base-final012` | 21/0/0 `up-up` | 21/0/0 `up-cold` | 21/0/0 `up-prod-0912` | 21/0/0 `up-prod-alpha` |
| upload multi-client | 9/0/0 `mc-0912` | 9/0/0 `mc-alpha` | – | – | – |
| lorem-stream | 18/0/0 `lo-base` | 18/0/0 `lo-up` | 18/0/0 `lo-cold` | Redis, 9 workers: 18/0/0 `lo-redis-prod-0912` | 18/0/0 `lo-redis-prod-alpha` |
| local-component | 15/0/0 `lc-base` | 15/0/0 `lc-up` | 15/0/0 `lc-cold` | 15/0/0 `lc-prod-0912` | 15/0/0 `lc-prod-alpha` |
| local-component hot edit of `.jsx` | 5/0/0 `lc-hotedit-0912` | 5/0/0 `lc-hotedit-alpha` | – | – | – |
| nba | 11/0/3 `nba-base` (3 = #7226 string titles not rendered) | 14/0/0 `nba-up` | 14/0/0 `nba-cold` | – | 14/0/0 `nba-prod-alpha` |
| quiz | 12/0/1 `qz-base` | 12/0/1 `qz-up` | 12/0/1 `qz-cold` | – | – |
| snakegame | 13/0/0 `sn-base` | 13/0/0 `sn-up` | 13/0/0 `sn-cold` | – | – |

Notes on the table:
- `twr-base-restart` 1 fail: the driver then checked bob's *restored* "Following" list, which shows `[]`.
  This is the app's stale cached computed var (see below). The check was turned into an observation
  afterwards, and the alpha shows the same `[]` (`twr-up-prod` notes).
- The twitter prod anomalies are `bg.svg` 404s: the app references `url(bg.svg)`, which is missing from
  `assets/`. Identical on 0.9.12. Dev hides it behind vite's SPA fallback.
- The quiz anomaly is the pre-existing Radix "Checkbox is changing from uncontrolled to controlled" warning:
  6× on every run, both versions.
- `up-up-driverrace.json` was a driver bug, kept for transparency. The hostile files already existed from
  the 0.9.12 run, so the wait returned before the new upload finished. The files did land with the new
  content (mtime 18:17:37). The driver now waits on this run's content.

`compare_runs.py` gave identical check statuses and console-signature sets for:
- base/up/cold of lorem, upload, quiz and twitter (`tw-base` vs `tw-cold-base`)
- prod 0.9.12 vs prod alpha for twitter and upload

### What each driver exercises

**twitter** (`reflex[db]`, sqlite, 3 pages, server-side login in `State.user`):
- anonymous `/` redirects to `/login` (`on_load` check_login)
- alice signs up, posts 2 tweets (newest first), searches tweets
- bob signs up in a 2nd context, tweets, searches users and follows alice
- reload keeps both logins
- sign out → `/login`; `/` redirects again
- wrong-password, duplicate-username and password-mismatch `rx.window_alert` dialogs
- re-login shows bob in alice's Followers; the same token is kept across logout/login
- in `up` mode: sessions seeded with the old tokens, posting, bob's password login, a new user following,
  and logout/login

**upload:** see Highlights.
- Throttled upload at 400 KB/s: progress goes 10→20; a Ping clicked mid-upload is processed in about
  0.25 s while the upload is still in flight, on both versions.
- Cancel: no file is saved.
- The Files list is stale for the session: it is a dependency-less cached var, a known app quirk.
- The served bytes match for spaces, unicode, nested and 12 MB files.

**lorem-stream:**
- 3 concurrent background streams
- completion, then restart of a completed task
- pause and resume
- kill
- reload mid-stream (the old tasks keep streaming into the reconnected tab and finish)
- a 2nd tab gets its own token and state
- a "duplicated tab" (same token injected into a new context) gets `new_token` and its own state
- tab 1 is unaffected

**local-component:** see Highlights. The flow also covers the right-click passthrough to
`rx.console_log(...).prevent_default`, the popover form, Escape revert, `rx.scroll_to`, color mode, and reload.

**nba:**
- gridjs (9 columns, "of 320", search, pagination)
- scatter (lowess trendline) and histogram from computed vars
- position and college selects
- age and salary sliders (`on_value_commit`)
- reload
- titles checked in the rendered SVG `.gtitle`

**quiz:**
- `rx.code_block`: 28 spans, 16 coloured, identical on both versions
- radios and checkboxes
- submit → `/result` with 100%, a reload keeps it
- Take Quiz Again
- one wrong answer gives 66% with an x icon
- browser back
- `on_load` reset gives 0%
- color mode
- direct `/result` in a fresh session

**snakegame:** a deterministic game (see the driver docstring).
- the board, stats and switch start in their initial state
- RUN
- queued keyboard moves via the custom `GlobalKeyWatcher` (`add_hooks`/`add_imports`)
- eats the food: SCORE 1, MAGIC 2, RATE 12
- forced self-collision: Game Over with a dead cell at (6,5)
- RUN after death resets
- PAUSE freezes the board
- Escape toggles via the key watcher
- the switch's on_change
- reload while running: the live board keeps moving

## Issues

### I-1 (low, no regression: intentional breaking change, UX gap) `reflex component` now fails with a misleading suggestion
```bash
cd $W/run/cli && $SB/envs/alpha/bin/reflex component --help        # same for: reflex component init|build|share|install
# -> Usage: reflex [OPTIONS] COMMAND [ARGS]...
#    Error: No such command 'component'. Did you mean 'compile'?    (rc=2)
$SB/envs/stable/bin/reflex component --help   # 0.9.12: lists init/build/install/share
```
#6425 removed the CLI on purpose. The changelog points users to "wrap React libraries directly" and the
component-template repository, but the CLI says neither. It also suggests `reflex compile`, which is
unrelated. Someone with a custom-component package whose CI runs `reflex component build` gets an opaque
failure after upgrading. A stub `component` command that prints the migration path, as other removed
commands do with "report which package to install", would close the gap. Evidence:
`logs/reflex-component-cli.txt`.

## Anomalies / context (not issues)

- **twitter, dev restarts log users out (both versions).** `reflex run` unconditionally runs
  `reset_disk_state_manager()`, which deletes `.states/*`. This is identical code in 0.9.12
  (`reflex/reflex.py:597`) and 0.10.0a1 (`reflex/reflex.py:642`).
  - Upgrade, dev: the stale tab reloads itself with the same token and lands on `/login`
    (`logs/tw-stale.driver.log`; the driver crashed afterwards before a fix, so there is no JSON).
  - 0.9.12→0.9.12 restart control: same outcome (`tw-stale-restart-0912`).
  - With Redis, sessions survive both a plain restart (`twr-base-restart`) and the upgrade (`twr-up-prod`,
    `twr-stale-prod`).
- **twitter app quirks (both versions).**
  - `following`/`followers` are cached computed vars that only recompute when `user` changes, so the lists
    are stale until re-login. Restored sessions carry the cached value.
  - Logout calls `reset()`, which empties the feed until "Click to load tweets".
  - `bg.svg` is missing from `assets/`.
  - Chromium verbose "Password field is not contained in a form".
- **Stale old-bundle tab after the upgrade** (dev and prod): the backend logs
  `Warning: Frontend version 0.9.12 for session … does not match the backend version 0.10.0a1.` and the user
  sees nothing. This is the same warning-only path as 0.9.12 (upgrades_a I-2). In prod, the old bundle kept
  working against 0.10.0a1 until a manual reload.
- **One-off on the alpha:** `[WARNING] Killing worker-1 after it refused to gracefully stop` at one of 14
  alpha dev shutdowns (quiz cold, `logs/quiz-cold.server.log:292`). The shutdown still completed in about
  3 s, ports were freed, and the state flush wrote 0 items. 0.9.12 dev shutdowns never reach a graceful
  granian stop without a TTY, so there is no baseline. Not reproduced.
- **Cosmetic, both versions: the compile progress bar always ends one past its total.** Examples:
  `Compiling: 15/14`, twitter 19/18, quiz 17/16, in every log. The total is
  `len(pages)*2 + 7 + len(config.plugins)` in `reflex/compiler/compiler.py` but there is one more
  `progress.advance`.
- **local-component, both versions.** Vite logs "Files in the public directory are served at the root path.
  Instead of /public/external/…/hello.jsx?v=…, use /external/…" at Debug level. It comes from the app's
  `library = f"/public/{asset}"` pattern (also the source of the `public//external` double slash).
- **`Debug: error: script "dev" exited with code 143`** is new at Debug level on the alpha's clean shutdown
  (upgrades_a saw it too). The 0.9.12 log has `warn: incorrect peer dependency "react@19.3.0"`, which is
  benign.
- **nba prod build (alpha):** vite says "(!) Some chunks are larger than 500 kB" at Debug level. That is the
  plotly.js bundle, and plotly.js is pinned at 3.7.0 in both versions. There was no 0.9.12 nba prod run.
- **`Warning: Attempting to send delta to disconnected client`** during reload-mid-stream (lorem, snake) on
  both versions. Counts vary with timing: 8 on 0.9.12 and 4 on the alpha for lorem.
- **Prod + Redis spawns 9 granian workers** with granian's "workers higher than CPU cores" warning, and
  `Page index is being redefined with the same component.` is logged once per worker. Both versions.
- **Websocket frames per run are fewer on the alpha** (e.g. twitter 178→160, nba 30→26). The connect now
  carries `hydrate_and_load` with per-state `hashes` (#7064), replacing separate `hydrate` + `on_load_internal`
  events. In twitter's payload several hashes repeat (e.g. `bf21a9e8fbc5a384` ×4), which looks like states
  with identical defaults; no functional effect.
- **`reflex export`:** zip lists are identical on both versions. Twitter: backend 26 files including
  alembic/, without `reflex.db`; frontend 45 files (`pkg/twitter-redis-*.zip.Z1` vs `pkg/tw-0912-*.zip.list`). Local-component: 13 and 31 files. The new #6996
  `routes.json` stays in `.web/` and is in neither zip; it is only read by reflex's own static serving.
- **Environment:** `media.geeksforgeeks.org` answers CONNECT 403 through the proxy, so nba runs on the local
  CSV stub. The harness shell exports `BUN_OPTIONS=--smol`, the same for both versions.

## Artifact map
```
NOTES.md            this file
twitter/ upload/ lorem-stream/ local-component/ nba/ quiz/ snakegame/   app sources as run (QA patches applied;
                    .web, node_modules, .states, assets/external, *.db, reflex.lock, uploaded_files, __pycache__ excluded;
                    twitter keeps the generated alembic/ + alembic.ini; nba ships nba_local.csv)
patches/            upload-qa-extras.diff, nba-qa-stub-and-extras.diff (vs upstream)
bin/                run_app.sh stop_app.sh ports.sh (from upgrades_a; ports.sh re-ranged)
scripts/            harness.py, compare_runs.py, tw_common.py, drivers and probes listed above
freeze/             uv pip freeze per venv: base/up and diffs
pkg/                .web/package.json base/up/cold per app plus diffs, reflex.lock hashes, export zip listings
logs/               every server log (base/up/cold/prod/redis/hot-edit/restart), install logs, export logs,
                    db command output, reflex component CLI output, stale-tab driver logs
shots/<app>/        <tag>.json for every run (checks, console, network, ws frames) plus selected screenshots
```
