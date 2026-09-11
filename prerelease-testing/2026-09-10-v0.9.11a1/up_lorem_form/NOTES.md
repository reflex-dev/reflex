# Cluster `up_lorem_form` — upgrade testing 0.9.10.post2 → 0.9.11a1

Two unmodified apps from `reflex-dev/reflex-examples`:

| App | What it exercises |
| --- | --- |
| `lorem-stream` | `@rx.event(background=True)` streaming tasks, many concurrent tasks, four dicts keyed by task id, a computed var driving `rx.foreach`, pause / resume / restart / kill mid-stream, `rx.progress`. This is the event hot path the train reworked (#7025). |
| `form-designer` | `reflex[db]` (`rx.Model` + `rx.session` + alembic) plus the third-party `reflex-local-auth` 0.5.0: register, login, dynamic route args, a form designer with a modal field editor, enumerated options, public form entry, `rx.toast` validation, response viewing with `rx.accordion` + `rx.moment`, cascade deletes. |

Date: 2026-09-11. All installs PyPI-only in isolated uv venvs, every run driven in real
headless Chromium (Playwright) with console / network / server-log capture.

## Verdict

**No regressions.** Every user flow of both apps behaves identically on reflex 0.9.10.post2
(previous stable) and on the full 0.9.11a1 alpha train — baseline, in-place upgrade (same venv,
same `.web/`, same `reflex.lock/`, same sqlite DB) and cold (`rm -rf .web`) — in dev and in prod.

Two real defects were found in `form-designer`; **both reproduce identically on 0.9.10.post2**, so
both are pre-existing, not release blockers for this train:

1. **`/form/<id>` (fill-out-a-form, the app's headline flow) is completely broken**: the page is
   replaced by reflex's error boundary with `` `FormMessage` must be used within `FormField` or
   specify the `name` prop ``. Root cause isolated to `rx.form.field(...)` **without** `name=`
   containing an `rx.form.message(...)` child — a 12-line repro app (`formmsg/`) fails the same way
   on both versions and on both `@radix-ui/react-form` 0.1.14 (radix 0.9.8) and 0.1.16
   (radix 0.9.9a1). Adding `name=field.name` to the one `rx.form.field()` call in
   `form_designer/components/field_view.py` fixes the app completely (`form-designer-patched/`:
   25/25 checks pass on both versions).
2. **In prod mode, logging in dead-ends on the login page.** `reflex run --env prod` answers
   `GET /login` with `307 → /login/`; `reflex_local_auth`'s `LoginState.redir` then compares
   `router.url.path` (`"/login/"`) against its `LOGIN_ROUTE` (`"/login"`), the equality fails and
   the post-login `rx.redirect` never fires. The session is valid (the navbar shows the user after
   a manual navigation), but a real user sees the login form again with no error. Dev mode does not
   redirect `/login`, so dev works and prod does not. Identical on both reflex versions.

Everything else — including 8 anomalies worth knowing about (below) — is unchanged between the two
versions.

## Ports / environments

Reserved range used: frontend 5460-5479, backend 9860-9879 (prod: one port for both). One dev
server at a time.

| app dir | reflex | venv | ports |
| --- | --- | --- | --- |
| `lorem-stream` | 0.9.10.post2 → in-place 0.9.11a1 train | `$SB/envs/up_lorem_form_lorem` | dev 5460/9860, prod 5470 |
| `lorem-stream-b0910` | 0.9.10.post2 (prod control only) | `$SB/envs/up_lorem_form_lorem_b0910` | prod 5471 |
| `form-designer` | 0.9.10.post2 → in-place 0.9.11a1 train | `$SB/envs/up_lorem_form_form` | dev 5461/9861 |
| `formmsg` / `formmsg_b0910` | 0.9.11a1 / 0.9.10.post2 | form venvs above | dev 5462/9862, 5463/9863 |
| `form-designer-patched` | 0.9.11a1 train | `$SB/envs/up_lorem_form_form` | dev 5464/9864, prod 5472 |
| `form-designer-patched-b0910` | 0.9.10.post2 | `$SB/envs/up_lorem_form_form_b0910` | dev 5465/9865, prod 5473 |
| `dbmig_a1` / `dbmig_b0910` | alembic CLI probes (no server) | as above | — |

`serve.sh` sets `REFLEX_DIR=$SB/reflex_dirs/<app dir basename>` per app. That isolation matters:
the 0.9.10.post2 runs then pick the **system bun 1.3.11** off `PATH` (its minimum is 1.3.0) and the
0.9.11a1 runs perform the real **bun 1.4.0** download/install themselves (0.9.11a1's minimum is
1.4.0), instead of reusing a bun 1.4.0 that another agent's alpha run left in
`~/.local/share/reflex`. `REFLEX_TELEMETRY_ENABLED=false` everywhere. `NO_PROXY` is set only for
curl/Playwright (client side) — exporting it into the server environment breaks bun's installs
through the egress proxy.

## Rerun commands (exact)

```sh
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
WD=$SB/apps/up_lorem_form            # copy this artifact directory here to reproduce
DRIVER=$SB/envs/driver/bin/python    # playwright venv; chromium at /opt/pw-browsers/chromium

# ---------- lorem-stream ----------------------------------------------------------------
cp -r /home/user/reflex-dev/reflex-examples/lorem-stream $WD/lorem-stream
uv venv $SB/envs/up_lorem_form_lorem --python 3.11
cd $WD/lorem-stream && uv pip install --python $SB/envs/up_lorem_form_lorem/bin/python \
    'reflex==0.9.10.post2' -r requirements.txt          # BASELINE, no --prerelease
cd $WD && ./serve.sh $WD/lorem-stream $SB/envs/up_lorem_form_lorem 5460 9860 logs/lorem_run_0910.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER drive_lorem.py http://localhost:5460 artifacts/lorem/0910 lorem_0910 $WD/lorem-stream
cp $WD/lorem-stream/.web/package.json      snapshots/lorem_webpkg_0910.json     # snapshot first
cp $WD/lorem-stream/reflex.lock/bun.lock   snapshots/lorem_bunlock_0910.lock
./stop.sh $WD/lorem-stream 5460 9860

# in-place upgrade to the FULL alpha train (component alphas must be named explicitly:
# reflex only floors them with >=, so a reflex-only upgrade leaves them at stable)
cd $WD/lorem-stream && uv pip install --python $SB/envs/up_lorem_form_lorem/bin/python \
    --prerelease=allow 'reflex==0.9.11a1' 'reflex-components-radix==0.9.9a1' \
    'reflex-components-code==0.9.5a1' 'reflex-components-moment==0.9.4a1' \
    'reflex-components-plotly==0.9.6a1' 'reflex-components-recharts==0.9.3a1' \
    'reflex-components-sonner==0.9.3a1' 'reflex-hosting-cli==0.1.72a1' -r requirements.txt
cd $WD && ./serve.sh $WD/lorem-stream $SB/envs/up_lorem_form_lorem 5460 9860 logs/lorem_run_0911_inplace.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER drive_lorem.py http://localhost:5460 artifacts/lorem/0911_inplace lorem_0911_inplace $WD/lorem-stream
./stop.sh $WD/lorem-stream 5460 9860

rm -rf $WD/lorem-stream/.web            # cold
cd $WD && ./serve.sh $WD/lorem-stream $SB/envs/up_lorem_form_lorem 5460 9860 logs/lorem_run_0911_cold.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER drive_lorem.py http://localhost:5460 artifacts/lorem/0911_cold lorem_0911_cold $WD/lorem-stream
./stop.sh $WD/lorem-stream 5460 9860

# prod (SAME port twice) and the two-session isolation probe
cd $WD && ./serve.sh $WD/lorem-stream $SB/envs/up_lorem_form_lorem 5470 5470 logs/lorem_run_0911_prod.log --env prod
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER drive_lorem.py http://localhost:5470 artifacts/lorem/0911_prod lorem_0911_prod $WD/lorem-stream
./stop.sh $WD/lorem-stream 5470 5470
cd $WD && ./serve.sh $WD/lorem-stream $SB/envs/up_lorem_form_lorem 5460 9860 logs/lorem_run_0911_twosession.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER probe_two_sessions.py http://localhost:5460 artifacts/lorem/0911_twosession lorem_0911_twosession
./stop.sh $WD/lorem-stream 5460 9860

# ---------- form-designer ---------------------------------------------------------------
cp -r /home/user/reflex-dev/reflex-examples/form-designer $WD/form-designer
uv venv $SB/envs/up_lorem_form_form --python 3.11
cd $WD/form-designer && uv pip install --python $SB/envs/up_lorem_form_form/bin/python \
    'reflex[db]==0.9.10.post2' -r requirements.txt      # BASELINE
cd $WD && ./serve.sh $WD/form-designer $SB/envs/up_lorem_form_form 5461 9861 logs/form_run_0910.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER drive_form.py http://localhost:5461 artifacts/form/0910 form_0910 $WD/form-designer
./stop.sh $WD/form-designer 5461 9861
# in-place upgrade (same venv, same .web/, same reflex.db) — same package list as above but
# with 'reflex[db]==0.9.11a1', then re-run serve.sh + drive_form.py (…/0911_inplace), then
# rm -rf $WD/form-designer/.web and run again (…/0911_cold).

# ---------- minimal FormMessage repro (finding 1) ----------------------------------------
cd $WD && ./serve.sh $WD/formmsg $SB/envs/up_lorem_form_form 5462 9862 logs/formmsg_0911.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER drive_formmsg.py http://localhost:5462 artifacts/formmsg/0911 formmsg_0911
./stop.sh $WD/formmsg 5462 9862        # /unnamed fails, /named passes — on BOTH versions
# baseline: uv venv $SB/envs/up_lorem_form_form_b0910 --python 3.11;
#   cd $WD/formmsg_b0910 && uv pip install --python $SB/envs/up_lorem_form_form_b0910/bin/python \
#       'reflex==0.9.10.post2' -r requirements.txt; serve on 5463/9863; drive to artifacts/formmsg/0910

# ---------- patched form-designer: the rest of the app, dev + prod, both versions --------
# form-designer-patched/ == form-designer/ with `name=field.name` added to the single
# rx.form.field() call in form_designer/components/field_view.py (see finding 1).
cd $WD && ./serve.sh $WD/form-designer-patched $SB/envs/up_lorem_form_form 5464 9864 logs/formpatched_0911.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER drive_form.py http://localhost:5464 artifacts/form_patched/0911 formpatched_0911 $WD/form-designer-patched
./stop.sh $WD/form-designer-patched 5464 9864
cd $WD && ./serve.sh $WD/form-designer-patched $SB/envs/up_lorem_form_form 5472 5472 logs/formpatched_0911_prod.log --env prod
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER drive_form.py http://localhost:5472 artifacts/form_patched/0911_prod formpatched_0911_prod $WD/form-designer-patched
./stop.sh $WD/form-designer-patched 5472 5472
# 0.9.10.post2 equivalents: form-designer-patched-b0910 on 5465/9865 (dev) and 5473 (prod)
# with $SB/envs/up_lorem_form_form_b0910.

# ---------- login trailing-slash probe (finding 2) --------------------------------------
# needs a registered user: take it from artifacts/form_patched/<run>/identifiers.json
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER probe_login_slash.py http://localhost:5464 <user> foobarbaz43 slash   shots/x.png
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $DRIVER probe_login_slash.py http://localhost:5464 <user> foobarbaz43 noslash shots/y.png

# ---------- alembic probes --------------------------------------------------------------
cp -r /home/user/reflex-dev/reflex-examples/form-designer $WD/dbmig_a1
cd $WD/dbmig_a1 && REFLEX_DIR=$SB/reflex_dirs/dbmig_a1 REFLEX_TELEMETRY_ENABLED=false \
    $SB/envs/up_lorem_form_form/bin/reflex db migrate               # silent, creates reflex.db
#   add a column to form_designer/models.py, then:
cd $WD/dbmig_a1 && REFLEX_DIR=$SB/reflex_dirs/dbmig_a1 REFLEX_TELEMETRY_ENABLED=false \
    $SB/envs/up_lorem_form_form/bin/reflex db makemigrations --message probe
```

Script signatures:

- `serve.sh <app_dir> <venv_dir> <FP> <BP> <log> [extra reflex-run args]` — starts with the
  per-app `REFLEX_DIR`, polls the frontend for HTTP 200 (up to 7.5 min), writes the pgid to
  `<app_dir>/logs/server.pid`.
- `stop.sh <app_dir> <port>…` — kills the whole process group, then verifies the ports are free.
- `drive_lorem.py <frontend_url> <artifacts_dir> <label> [<app_dir>]` — 16 checks.
- `drive_form.py <frontend_url> <artifacts_dir> <label> [<app_dir>]` — 26/27 checks; registers a
  fresh `u<timestamp>` user and an `F-<timestamp>` form per run, so it is safe to re-run against
  an existing `reflex.db`, and deletes its own form at the end. Identifiers are written to
  `<artifacts_dir>/identifiers.json`.
- `drive_formmsg.py <frontend_url> <artifacts_dir> <label>` — 5 checks (the isolation repro).
- `probe_two_sessions.py <frontend_url> <artifacts_dir> <label>` — 3 checks.
- `probe_login_slash.py <frontend_url> <user> <password> <slash|noslash> <screenshot>`.
- `probe_login_delay.py`, `probe_dialog.py`, `explore_lorem.py` — DOM/timing scratch probes kept
  because they document how the selectors were derived.

Each driver writes `results.json`, `console.json`, `bad_responses.json`, `page_errors.json` and
screenshots into its artifacts dir. `drive_common.py` holds the shared plumbing (borrowed from the
`up_upload_traversal_quiz` cluster).

**Driver gotcha worth knowing** (it cost me two runs): in Playwright's sync API `page.url` is
event-cached and is *not* refreshed inside a `time.sleep()` poll loop, so a predicate like
`lambda: "/login" not in page.url` can report a stale URL for as long as you poll. `drive_form.py`
reads the URL with `page.evaluate("() => location.href")` instead. A "the app never redirected"
observation from a `page.url` poll is a driver artifact, not a framework bug.

## Results

Legend: B = 0.9.10.post2 baseline, I = 0.9.11a1 in-place upgrade, C = 0.9.11a1 cold (`rm -rf .web`),
P = prod (`--env prod`). Counts from `artifacts/<app>/<run>/results.json`.

### lorem-stream — 16 checks per run, 4 runs, all identical

| run | result |
| --- | --- |
| B dev (`artifacts/lorem/0910`) | 16 pass |
| I dev (`artifacts/lorem/0911_inplace`) | 16 pass |
| C dev (`artifacts/lorem/0911_cold`) | 16 pass |
| P prod 0.9.11a1 (`artifacts/lorem/0911_prod`) | 16 pass |
| two-session isolation probe, 0.9.11a1 (`artifacts/lorem/0911_twosession`) | 3 pass |

`diff` of the (name, status) lists B↔I and I↔C: **identical, zero lines**. Checks: index loads
empty; one `stream_text` task streams (progress and text both advance, `end_at` inside
`ITERATIONS_RANGE`); three concurrent tasks all advance inside the same 2 s window; pausing one
task freezes exactly that task (progress and text byte-stable for 2.5 s) and leaves the others
advancing; resuming continues from the paused progress without losing text; a task runs to
completion (`data-state=complete`, `value == max`) and its button flips to 🔄; restarting a
completed task resets progress to 0, clears the text and re-rolls `end_at`; ❌ removes the card;
after a full page reload the task ids and accumulated text survive **and a still-running
background task keeps streaming deltas into the reloaded page**; a burst of six clicks yields six
cards all streaming; killing all six leaves the page clean; no console errors/warnings beyond the
known-benign set, no failed or ≥400 requests, no page errors.

### form-designer as shipped — 26 checks per run, 3 runs, all identical

| run | result |
| --- | --- |
| B dev (`artifacts/form/0910`) | 16 pass, 1 fail, 8 skipped, 1 anomaly |
| I dev (`artifacts/form/0911_inplace`) | 16 pass, 1 fail, 8 skipped, 1 anomaly |
| C dev (`artifacts/form/0911_cold`) | 16 pass, 1 fail, 8 skipped, 1 anomaly |

The fail is `preview_renders_fields` (finding 1); the 8 skips are the checks that need the form
entry page (submit, anonymous submit, responses list, response values, delete response, the toast
validation, logout). Pass on all three runs: home page (README markdown card + the
`importlib.metadata.version("reflex")` badge, `v0.9.10.post2` → `v0.9.11a1`), editor is
login-gated, registration password-mismatch error, registration, duplicate-username rejection,
wrong-password error, login (lands on the gated `/edit/form/` in 0.4 s), navbar shows the user,
form creation via the debounced name input (redirect to `/edit/form/<id>/`), add a text field
through the modal, rename it and mark it required, add a `select` field and an option through the
nested options dialog, delete a field, delete the form (gone from the `rx.select` dropdown).

### form-designer with the one-line `name=` fix — the whole app, both versions, dev and prod

| run | result |
| --- | --- |
| B dev (`artifacts/form_patched/0910`) | 25 pass, 1 anomaly (console) |
| 0.9.11a1 dev (`artifacts/form_patched/0911`) | 25 pass, 1 anomaly (console) |
| B prod (`artifacts/form_patched/0910_prod`) | 23 pass, 1 fail (finding 2), 3 anomalies |
| 0.9.11a1 prod (`artifacts/form_patched/0911_prod`) | 23 pass, 1 fail (finding 2), 3 anomalies |

Dev B vs dev 0.9.11a1 and prod B vs prod 0.9.11a1: identical status for every check, and the
console error sets are the same six messages. The full flow works: required-field `rx.toast`
validation blocks submission and names the field, a logged-in submission saves and redirects to
`/form/success`, logout, an anonymous submission of the same public form saves,
`/responses/<id>/` is login-gated and returns to itself after login, both responses appear as
accordion items with the `rx.moment` timestamp and the stored values, deleting one leaves one.
The `rx.moment` render is pixel-identical between react-moment 1.2.2 (B) and 2.0.2 (0.9.11a1) —
`Fri Sep 11 2026 07:48:20 GMT+0000` — see `artifacts/form_patched/*/14_response_open.png`.
(The two dev runs predate the `login_redirect_workaround_used` check the prod runs added, hence
25 vs 27 entries.)

### minimal `FormMessage` repro — `formmsg/`

| run | `/unnamed` | `/named` |
| --- | --- | --- |
| 0.9.10.post2 (`artifacts/formmsg/0910`, react-form 0.1.14) | fail — error boundary, no heading, no input | pass, submit works |
| 0.9.11a1 (`artifacts/formmsg/0911`, react-form 0.1.16) | fail — error boundary, no heading, no input | pass, submit works |

### alembic / `reflex[db]` CLI

| probe | 0.9.10.post2 | 0.9.11a1 |
| --- | --- | --- |
| `rx.model.migrate()` at app import creates `reflex.db` with all 8 tables (incl. `localuser`, `localauthsession`), `alembic_version = 4c92535dbbbd` | yes | yes |
| in-place upgrade over the existing `reflex.db` — data intact, no migration needed | yes | yes |
| `reflex db migrate` on a fresh checkout | exit 0, creates a 57344-byte DB, **prints nothing** | identical |
| `reflex db makemigrations --message X` with no model change | exit 0, no file, **prints nothing** | identical |
| `reflex db makemigrations --message X` after adding one column | `Generating …/4c0321fc4326_probe.py … done`; body is one `batch_alter_table` add_column | `Generating …/9d203ac4119e_probe.py … done`; **byte-identical migration body** |
| applying it (`reflex db migrate`) | — | column added, `alembic_version` advanced |

Evidence: `logs/dbmig_*.log`, `dbmig_a1/alembic/versions/9d203ac4119e_probe.py`,
`dbmig_b0910/alembic/versions/4c0321fc4326_probe.py`, `snapshots/form_db_0910.txt`.

## Upgrade mechanics observed on the first 0.9.11a1 run

Read from `logs/lorem_run_0911_inplace.log` and `logs/form_run_0911_inplace.log`:

- **Bun**: `[Bun 1.3.11 (Minimum: 1.4.0) (PATH: /root/.bun/bin/bun)]` → reflex downloads and
  installs its own **bun 1.4.0** into `REFLEX_DIR/bun` (`bun was installed successfully`). The
  0.9.10.post2 baseline runs logged `[Bun 1.3.11 (Minimum: 1.3.0)]` and used the system bun.
  The three `registry.npmmirror.com` failures before the fallback are the known-benign noise.
- **Re-init of `.web`**: `Info: Initializing the web directory` → the whole `.web` template is
  re-copied, `reflex.lock/bun.lock` is restored into it, then copied back; bun config, `.npmrc`,
  `public/`, `react-router.config.js`, `vite.config.js`, `reflex.json` are re-initialized;
  `Debug: Resetting disk state manager.` wipes `.states/` (session state from before the upgrade is
  gone — expected, but worth knowing if you test session persistence across an upgrade).
- **Lockfile**: `bun install --legacy-peer-deps --frozen-lockfile` succeeds against the retained
  v1 lockfile (lorem 238 packages / form-designer 393 packages), then two `bun add` calls install
  the bumped dev and app dependencies and `Saved lockfile`. The app-root `reflex.lock/bun.lock`
  **stays at `lockfileVersion: 1`** — bun 1.4 keeps an existing v1 lockfile at v1. A *new* app dir
  created under 0.9.11a1 (`form-designer-patched/`) gets `lockfileVersion: 2`, so an upgraded
  project and a fresh project are not byte-comparable. Hashes in
  `snapshots/lockfile_sha256.txt`, header in `snapshots/lockfile_versions.txt`.
  Note `rm -rf .web` is *not* a lockfile reset: `reflex.lock/` lives outside `.web`, so the cold
  run reuses (and keeps) the v1 lockfile.
- **`utils/context.js` → `utils/context.jsx`** (#7071): the stale `.js` is gone after the upgrade
  and `context.jsx` plus a new `context-registry.js` are in place (`snapshots/*_utils_0910.txt`
  vs the current tree). Both apps, in place and cold.
- **Package installer messages**: form-designer's first alpha run logs four transient
  `warn: incorrect peer dependency "react-router@8.3.0"` / `"react@19.3.0"` lines during the
  migration; the final lockfile is consistent and the app runs (known-benign per the brief).
- One surprising log line during an *upgrade* run:
  `Success: Initialized form_designer. Install dependencies from requirements.txt with
  uv pip install -r requirements.txt … before running uv run reflex run` — a first-run "init"
  message printed in the middle of `reflex run` on an existing project whose dependencies are
  obviously already installed. Same text on 0.9.10.post2 when the template needs re-initializing.
- `Debug: Latest version of reflex: 0.9.10.post2` — the version check reports the latest *stable*
  while running a prerelease; no misleading "update available" banner is printed.

### `.web/package.json` diffs (identical for both apps where the dependency exists)

0.9.10.post2 → 0.9.11a1 train:

| package | before | after |
| --- | --- | --- |
| `react-router`, `@react-router/node`, `@react-router/dev`, `@react-router/fs-routes` | 8.3.0 | 8.3.1 |
| `isbot` | 5.2.1 | 5.2.2 |
| `sonner` | 2.0.7 | 2.0.8 |
| `vite` | 8.2.0 | 8.2.2 |
| `postcss` | 8.5.23 | 8.5.26 |
| `postcss-import` | 16.1.1 | 17.0.0 |
| `@radix-ui/react-form` (form-designer) | 0.1.14 | 0.1.16 |
| `@radix-ui/react-accordion` (form-designer) | 1.2.18 | 1.2.20 |
| `react-moment` (form-designer) | 1.2.2 | 2.0.2 |

Unchanged: react/react-dom 19.2.8, `@radix-ui/themes` 3.3.0, socket.io-client 4.8.3,
lucide-react 1.26.0, react-error-boundary 6.1.2, universal-cookie 8.1.2, react-helmet 6.1.0,
autoprefixer 10.5.4, `@emotion/react` 11.14.0, react-markdown 10.1.0 & friends.
**Cold run converges to a byte-identical `.web/package.json` and `reflex.lock/bun.lock` for both
apps** (`snapshots/*_webpkg_0911_inplace.json` vs the post-cold tree).

Python side, in place (`uv pip install` without `-U`): only the nine packages named on the command
line move (reflex, reflex-base, the six component alphas, reflex-hosting-cli). `wrapt` stays at
2.1.2 (reflex 0.9.11a1 allows `<2.4`); `sqlmodel` 0.0.42, `sqlalchemy` 2.0.52, `alembic` 1.19.2,
`reflex-local-auth` 0.5.0, `bcrypt`, `passlib` untouched. Confirms the campaign's FINDING-007: a
reflex-only upgrade leaves the component packages at stable, so the alpha sub-packages must be
named explicitly.

## Findings

### F1 — `rx.form.field()` without `name=` + an `rx.form.message` child blanks the page; it breaks form-designer's main flow (pre-existing, both versions)

- Severity: high impact (the page is unusable), **regression: no** — identical on 0.9.10.post2.
- Repro (minimal, 12 lines — `formmsg/formmsg/formmsg.py`):
  1. `uv venv $SB/envs/x --python 3.11 && cd formmsg && uv pip install --python … 'reflex==0.9.11a1' -r requirements.txt`
     (repeat with `reflex==0.9.10.post2` for the baseline).
  2. `reflex run --frontend-port 5462 --backend-port 9862`.
  3. Open `/named` → heading, card, input render; submitting works.
  4. Open `/unnamed` → the identical tree with `name=` removed from `rx.form.field(...)`:
     reflex's error boundary replaces the entire page with
     `` Error: `FormMessage` must be used within `FormField` or specify the `name` prop ``.
- Repro (the shipped example): run `form-designer` unmodified, log in, create a form, add any
  field, click **Preview** → `/form/<id>` is the error boundary. The app's own
  `tests/test_create_form.py` walks exactly this path, so it cannot be passing either.
- Evidence: `artifacts/formmsg/{0910,0911}/results.json` + `unnamed.png` / `named.png`;
  `artifacts/form/{0910,0911_inplace,0911_cold}/09_preview.png` (full-page error boundary) and
  their `console.json`; server-side copy of the React stack in `logs/form_run_0910.log`
  (`[Reflex Frontend Exception]`) and the same in `logs/form_run_0911_{inplace,cold}.log`.
- Root cause: `reflex_components_radix/primitives/form.py` exposes `name` as an *optional* Var on
  both `FormField` and `FormMessage`. Radix's `Form.Message` requires a field name from either its
  own prop or the enclosing `Form.Field` context, and throws when both are missing. Reflex neither
  defaults nor validates it, and there is no Python-side hint — the failure is a blank page at
  runtime. Unchanged by the `@radix-ui/react-form` 0.1.14 → 0.1.16 bump in this train.
- Fix that works end to end: `name=field.name` on the single `rx.form.field()` call in
  `form_designer/components/field_view.py` (see `form-designer-patched/`), after which 25/25
  checks pass on both reflex versions. A framework-side improvement would be to require `name`
  (or warn at compile time) when a `form.message` is nested without one.

### F2 — prod mode: `GET /login` 307s to `/login/`, so reflex-local-auth's post-login redirect never fires (pre-existing, both versions; downstream trigger)

- Severity: high for any prod deployment of a reflex-local-auth app, **regression: no** —
  identical on 0.9.10.post2. Downstream component: `reflex-local-auth` 0.5.0.
- Repro:
  1. `cd form-designer-patched && reflex run --env prod --frontend-port 5472 --backend-port 5472`
     (the unpatched app reproduces this too — it just dies later, at F1).
  2. `curl -sI --noproxy '*' http://localhost:5472/login` → `307` to `http://localhost:5472/login/`
     (`/edit/form` → `/edit/form/` likewise; in dev `/login` is served directly, no redirect).
  3. In Chromium open `http://localhost:5472/login`, fill a registered user + password, click
     **Sign in**: the URL settles on `/login/` and the login card stays on screen with no error.
     Waiting 30 s changes nothing.
  4. Navigate to `/` by hand → the navbar menu shows the username, i.e. the session is valid; the
     only thing that failed is the redirect.
- Evidence: `artifacts/form_patched/0911_prod/results.json`
  (`login_success: left_login_page=False landed_on=/login/ seconds=30.1`,
  `login_redirect_workaround_used: anomaly`) and the identical
  `artifacts/form_patched/0910_prod/results.json`; screenshots `03_logged_in.png` in both;
  `shots/loginslash_{0910,0911}_{slash,noslash}.png` plus the `probe_login_slash.py` output
  (dev, trailing slash → stays on `/login/` while authenticated; dev, no slash → lands on `/`).
- Root cause: `LoginState.redir` (site-packages/reflex_local_auth/login.py) does
  `current_route = self.router.url.path` and then `elif self.is_authenticated and current_route ==
  routes.LOGIN_ROUTE`, with `LOGIN_ROUTE = "/login"`. Reflex reports `router.url.path` verbatim, so
  the trailing slash the prod server adds (and that any user who types `/login/` supplies in dev)
  makes the comparison fail silently. Reflex's own side of it: the dev server and the prod server
  disagree about trailing slashes for the same route, which makes this class of bug invisible in
  development.
- Workarounds for app authors: `reflex_local_auth.routes.set_login_route("/login/")`, or compare
  with `rstrip("/")`.

## Anomalies (all identical on 0.9.10.post2 and 0.9.11a1 — recorded, not blockers)

1. **`Warning: Page index is being redefined with the same component.`** — printed once by
   `lorem-stream` in **prod only** (`logs/lorem_run_0911_prod.log:207`, control
   `logs/lorem_run_0910_prod.log:293`). The app declares its only page with `@rx.page` and never
   calls `add_page`; prod applies the decorated page twice. Cosmetic but it tells users their app
   has duplicate routes when it does not. Same on both versions (that is why
   `lorem-stream-b0910/` exists: a 0.9.10.post2 prod control).
2. **`Warning: Attempting to send delta to disconnected client`** (×5 in
   `logs/lorem_run_0910.log`, ×1 in each 0.9.11a1 dev run, ×13 in the two-session probe) — background tasks still
   streaming when the driver closes the browser. Expected, but it is a `Warning` in the server log
   for a completely normal "user closed the tab mid-task" situation.
3. **Pydantic serializer warnings from form-designer's own models** (`logs/form_run_0910.log:279`,
   `logs/form_run_0911_inplace.log:329`):
   `PydanticSerializationUnexpectedValue(Expected int … field_name='form_id', input_value='1', input_type=str)`
   and `(Expected enum … field_name='type_', input_value='text', input_type=str)`. The app assigns
   the string route arg to `Field.form_id` and a plain string to `type_`. App-level sloppiness, but
   the warning surfaces as reflex-server noise with a site-packages traceback path and no hint
   about which state/model is at fault.
4. **Three `Invalid DOM property \`stroke-linecap\`/\`stroke-linejoin\`/\`stroke-width\`** console
   errors every time reflex's own error boundary renders (campaign FINDING-024) — reproduced here
   on both versions whenever F1 fires.
5. **`Received \`true\` for a non-boolean attribute \`collapsible\`.`** — `rx.accordion.root(collapsible=True)`
   leaks `collapsible` to the DOM on the responses page. Both versions,
   `artifacts/form_patched/*/console.json`.
6. **`In HTML, <button> cannot be a descendant of <button>. This will cause a hydration error.`**
   (plus the companion `<button> cannot contain a nested <button>`) — form-designer's response
   accordion header nests a delete `rx.button` inside the `AccordionTrigger` button. Both
   versions; the delete button still works.
7. **`The pseudo class ":first-child" is potentially unsafe when doing server-side rendering`** ×3
   (emotion, radix themes) on every form-designer page. Both versions.
8. **Prod: dynamic routes answer the first document request with HTTP 404** —
   `/form/1`, `/edit/form/1/`, `/responses/1/` all return 404 in prod (the SPA fallback body is
   served, so the app works and the checks pass, but the status line is wrong). Both versions,
   `artifacts/form_patched/{0910_prod,0911_prod}/bad_responses.json`. Prerender logs
   `⚠️ Paths with dynamic/splat params cannot be prerendered when using prerender: true`. Adjacent
   to the campaign's FINDING-037.
9. **`reflex db migrate` and a no-op `reflex db makemigrations` print absolutely nothing** (exit 0)
   — you cannot tell from the output whether the DB was created, already current, or skipped.
   Identical on both versions; `reflex db makemigrations -m X` is also rejected (the flag is
   `--message`, no short form). Usability, not a defect.
10. **The `SitemapPlugin` "enabled by default but not explicitly added" warning** appears 5× per
    run in `lorem-stream`'s log (its `rxconfig.py` lists only `RadixThemesPlugin`). Known reflex
    behaviour, repeated once per app-module import; noted only because it is the loudest thing in
    an otherwise clean log.

## Files

```
NOTES.md                      this file
lorem-stream/                 app source as run (pristine example; .web, reflex.lock, *.db excluded)
lorem-stream-b0910/           identical copy used for the 0.9.10.post2 prod control
form-designer/                app source as run (pristine example)
form-designer-patched/        + name=field.name on the one rx.form.field() call (F1 fix)
form-designer-patched-b0910/  same, run against 0.9.10.post2
formmsg/, formmsg_b0910/      12-line minimal repro app for F1
dbmig_a1/, dbmig_b0910/       alembic probe copies: models.py carries the one extra column the
                              probe added, alembic/versions/ the migration each version generated
drive_common.py               shared Playwright plumbing (console/network/results capture)
drive_lorem.py                lorem-stream driver (16 checks)
drive_form.py                 form-designer driver (26/27 checks)
drive_formmsg.py              minimal F1 repro driver (5 checks)
probe_two_sessions.py         two independent sessions streaming background tasks
probe_login_slash.py          F2: /login vs /login/ post-login redirect
probe_login_delay.py          timing probe for the post-login redirect (0.6 s when it works)
probe_dialog.py, explore_lorem.py   selector-discovery probes
serve.sh, stop.sh             start/stop helpers (per-app REFLEX_DIR, pgid kill, port check)
artifacts/<app>/<run>/        results.json, console.json, bad_responses.json, page_errors.json,
                              package.json, identifiers.json, screenshots
logs/                         server logs for every run + the alembic CLI logs
snapshots/                    .web/package.json per app+version, utils/ listings, pip lists,
                              DB dump, lockfile hashes and headers
shots/                        probe screenshots
```

## VERIFICATION: rx.form.field() without name= plus an rx.form.message child blanks the whole page; it breaks form-designer's core "fill out a form" flow

Independent adversarial verification (second agent, own working dir
`$SB/apps/verify2_up_lorem_form_0/`, own app written from the written repro, own runs on ports
6160-6163 / 10560-10563, shared read-only venvs `$SB/envs/smoke` = 0.9.11a1 and
`$SB/envs/base0910` = 0.9.10.post2 plus a fresh `$SB/envs/verify2_up_lorem_form_0`).

### Verdict: CONFIRMED as a real, deterministic framework defect — but re-scoped on two points

1. **Confirmed**, exactly as described and not an environment artifact: `rx.form.field()` with no
   `name=` containing an `rx.form.message(...)` throws
   `` Error: `FormMessage` must be used within `FormField` or specify the `name` prop `` at render
   time and reflex's page-level `ErrorBoundary` replaces the entire page with "An error occurred
   while rendering this page." Deterministic (5/5 page loads), no proxy/port/cwd involvement — the
   throw is in `.web/node_modules/@radix-ui/react-form/dist/index.mjs`.
2. **Confirmed pre-existing / not a regression in this train**: byte-for-byte identical status on
   0.9.10.post2 (react-form 0.1.14) and 0.9.11a1 (react-form 0.1.16). I ran the baseline myself.
3. **Re-scope A — the claim is too narrow.** It is *not* about `form.message`. `rx.form.label` and
   `rx.form.control` throw the same invariant, so an unnamed `rx.form.field` also blanks the page
   with `` `FormLabel` must be used within `FormField`… `` / `` `FormControl` must be used
   within… ``. Those two are the documented anatomy of a field
   (`docs/library/forms/form-ll.md`: `form.field(form.label, form.control, form.message)`), so the
   accurate statement is: **`rx.form.field()` without `name=` is unusable — any Radix form part
   inside it takes the whole page down.** Only a field whose children are all plain components
   (my `/nomsg` page) survives.
4. **Re-scope B — this is a dated regression, from reflex 0.9.8, caused by reflex's own dependency
   bump.** Upstream added the three `must be used within` throws in `@radix-ui/react-form`
   **0.1.12** (published 2026-07-06); 0.1.8 and 0.1.11 have zero such throws and pass
   `name === undefined` straight through (message simply never matches, page renders). Reflex
   pinned react-form 0.1.8 until commit `9fcce6059` "Bump frontend and component library
   dependencies (#6678)" (2026-08-03) moved it to 0.1.14, shipped as
   **reflex-components-radix 0.9.7 / reflex 0.9.8 (2026-08-04)**. So form-designer's Preview page
   worked on reflex <= 0.9.7 and has been dead since 0.9.8 — one release before this train, which
   is why both versions tested here look the same. The radix changelog for 0.9.7 mentions the
   version bump but not the behavioral break.

### Refutation attempts and what they showed

| angle | result |
| --- | --- |
| environment (proxy / NO_PROXY / ports / cwd shadowing) | refuted — error originates in vendored JS; app asserts `"/envs/" in rx.__file__` and the server log echoes the venv path |
| flaky | refuted — 100% reproducible, 4 crashing pages per run, 2 runs per version |
| pre-existing on 0.9.10.post2 | **true** (ran it myself; identical results table) |
| API misuse / documented behaviour | partly true: every reflex doc example passes `name=`, and upstream types it required (`FormFieldProps { name: string }` in `index.d.mts`). But reflex declares `name: Var[str]` optional on `FormField` and the generated stub is `name: Var[str] \| str \| None = None`, so there is **no** type error, no compile-time error and no runtime warning — pyright is happy and the first signal a user gets is a blank page. |
| demo/example bug rather than framework bug | both: `form-designer/form_designer/components/field_view.py:138` calls `rx.form.field(...)` with no `name=` and `pages/form_entry.py:87` puts an `rx.form.message` inside it — that example app is broken and needs a one-line fix; the framework-side defect is the missing guard plus the unannounced dependency behaviour change |
| release blocker for 0.9.11 | **no** — nothing in this train changed it |

### My own severity / regression / downstream call

- severity **medium** (claim said high): user-visible impact is severe when hit (page gone, no
  Python-side hint), but it is avoidable with a documented prop, it is not a regression in this
  train, and it is one release old rather than new. Worth a fix in 0.9.11 or 0.9.12 as a
  compile-time check, not a blocker.
- regression **false for this train** (true relative to reflex 0.9.7 — see Re-scope B).
- downstream **false**: the pin (`reflex_components_radix/primitives/form.py:21`
  `library = "@radix-ui/react-form@0.1.16"`), the optional `name` declaration and the missing
  check are all in reflex's own package. The app that trips it (`reflex-dev/reflex-examples`
  form-designer) is reflex-owned too.

### Mechanism (file:line)

- `packages/reflex-components-radix/src/reflex_components_radix/primitives/form.py:44-53` (release
  branch `origin/r/pre-2026.09.10-34457666442`, same in the installed
  `reflex_components_radix-0.9.9a1`): `FormField.name` is `Var[str]` declared with plain `field(...)`,
  i.e. optional, and `FormField.create` does no validation. `FormLabel` and `FormControl`
  (lines 68, 84) do not even expose a `name` prop, so they can only get one from the field context.
- `.web/node_modules/@radix-ui/react-form/dist/index.mjs` (0.1.16): `FormMessage` line 325-329,
  `FormLabel` line 156-160, `FormControl` line 191-195 — each does
  `const name = nameProp ?? fieldContext?.name; if (!name) throw new Error(...)`.
- `@radix-ui/react-form@0.1.16/dist/index.d.mts:18-21` — `interface FormFieldProps { name: string; ... }`,
  i.e. **required** upstream; reflex weakens it to optional.
- Suggested framework fix (not applied — verifier does not fix): make `name` required on
  `FormField.create`, or raise/warn at compile time when a `FormField` has a
  `FormLabel`/`FormControl`/`FormMessage` descendant and no `name`. Reflex 0.9.11a1 already does
  this class of static form checking in
  `reflex_components_core/el/elements/forms.py:405-491` (`_validate_on_submit_typed_dict_fields`,
  which raises `EventHandlerValueError` for a TypedDict field with no matching control), so the
  machinery and the precedent both exist.
- Separate, app-side: add `name=field.name` to `rx.form.field(...)` in
  `reflex-examples/form-designer/form_designer/components/field_view.py:138` (the claimant already
  verified that fix end to end).

### Exact commands (all re-runnable)

```sh
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
WD=$SB/apps/verify2_up_lorem_form_0        # == this directory's verification/ contents
# app: verification/fmsg/fmsg/fmsg.py — 7 pages:
#   /unnamed  field w/o name + form.message            -> error boundary
#   /named    same + name="who"                        -> renders, submits
#   /msgname  field w/o name, form.message(name="who") -> renders, submits
#   /nomsg    field w/o name, no radix form parts      -> renders, submits
#   /msgtop   form.message directly under rx.form      -> error boundary
#   /labelonly field w/o name + form.label             -> error boundary
#   /controlonly field w/o name + form.control         -> error boundary

# 0.9.11a1 (reflex 0.9.11a1 + reflex-components-radix 0.9.9a1 -> react-form 0.1.16)
cd $WD && ./serve.sh $WD/fmsg       $SB/envs/smoke     6160 10560 $WD/logs/fmsg_0911.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python drive_fmsg.py http://localhost:6160 $WD/artifacts/fmsg/0911 fmsg_0911
./stop.sh $WD/fmsg 6160 10560

# 0.9.10.post2 baseline (radix 0.9.8 -> react-form 0.1.14)
cd $WD && ./serve.sh $WD/fmsg_b0910 $SB/envs/base0910 6161 10561 $WD/logs/fmsg_0910.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python drive_fmsg.py http://localhost:6161 $WD/artifacts/fmsg/0910 fmsg_0910
./stop.sh $WD/fmsg_b0910 6161 10561

# dating the break at the JS level (no reflex needed)
curl -s https://registry.npmjs.org/@radix-ui/react-form -o /tmp/rf.json
# for v in 0.0.3 0.1.8 0.1.11 0.1.12 0.1.14 0.1.16: fetch dist.tarball, then
#   grep -c 'must be used within' package/dist/index.mjs
#   -> 0 for <=0.1.11, 6 from 0.1.12 (2026-07-06) on
git -C /home/user/reflex show 9fcce6059 -- '*primitives/form.py' | grep react-form
#   -    library = "@radix-ui/react-form@0.1.8"
#   +    library = "@radix-ui/react-form@0.1.14"     (#6678, 2026-08-03 -> radix 0.9.7 / reflex 0.9.8)
```

### Results table (my runs, identical statuses on both versions)

| page | 0.9.11a1 | 0.9.10.post2 |
| --- | --- | --- |
| `unnamed_renders` | fail (error boundary) | fail (error boundary) |
| `named_renders` / `named_submit` | pass / pass | pass / pass |
| `msgname_renders` / `msgname_submit` | pass / pass | pass / pass |
| `nomsg_renders` / `nomsg_submit` | pass / pass | pass / pass |
| `msgtop_renders` | fail (error boundary) | fail (error boundary) |
| `labelonly_renders` | fail (error boundary) | fail (error boundary) |
| `controlonly_renders` | fail (error boundary) | fail (error boundary) |

`named` and `msgname` also show the validation message on an empty submit
(`empty_submit_msg_shown=True`) and submit `{'who': 'alice', ...}` to the handler, so the feature
itself is intact once a name is reachable; `nomsg` submits but of course shows no message.

### Evidence (this cluster dir)

- `verification/fmsg/` — my 7-page repro app (as run), `verification/drive_fmsg.py`,
  `verification/serve.sh`, `verification/stop.sh`
- `verification/artifacts/fmsg_verify/{0911,0910}/results.json`, `console.json`,
  `page_errors.json`, `bad_responses.json` and one screenshot per page
  (`unnamed.png`, `labelonly.png`, `controlonly.png`, `msgtop.png` are the error boundary;
  `named.png`, `msgname.png`, `nomsg.png` render)
- `verification/logs/fmsg_{0911,0910}_frontend_exceptions.txt` — the server-side
  `[Reflex Frontend Exception]` blocks for all four crashing pages on both versions

### One check I could not complete (environment, not a finding)

I tried to demonstrate the pre-0.9.8 behaviour live with `reflex==0.9.7` +
`reflex-components-radix==0.9.6` (react-form 0.1.8) in `$SB/envs/verify2_up_lorem_form_0` on
6162/10562. Both attempts died in bun's install with dozens of
`error: ConnectionClosed downloading package manifest …` through the egress proxy (that older
dependency set, with other agents loading the proxy at the same time) — tail in
`verification/logs/fmsg_0907_bun_install_failure_tail.txt`. The dating in Re-scope B therefore
rests on reading the pinned dependency's own source at each version (react-form 0.1.8/0.1.11 have
no such throw at all) plus the reflex pin history, which is conclusive at the JS level but was not
re-confirmed by a live 0.9.7 run.

## VERIFICATION: Prod serves GET /login as 307 -> /login/, which silently defeats reflex-local-auth's post-login redirect (dev does not, so it is invisible in development)

Independent adversarial verification of F2 (verifier `verify2_up_lorem_form_1`, 2026-09-11). Everything
below was reproduced from the written repro alone in a **new 12-line app** and in **own venvs**
(`$SB/envs/verify2_up_lorem_form_1` = `reflex[db]==0.9.11a1` + `reflex-local-auth==0.5.0`,
`$SB/envs/verify2_up_lorem_form_1_b0910` = same with `reflex[db]==0.9.10.post2`), on my own ports
(6164-6167 / 10564-10567). None of the claimant's processes or artifacts were used.

### Verdict: CONFIRMED as described, but re-scoped — severity medium, not high; the login breakage is a reflex-local-auth bug, the dev/prod divergence is the (minor) reflex-side defect. NOT a regression.

Every factual claim in F2 reproduces, deterministically, and the root cause is exactly as stated.
Three things the original report missed change the severity:

1. **Only a *hard document load* of `/login` breaks.** In prod, client-side navigation to the login
   page keeps the clean path and logs in normally (0.5-0.6 s):
   `require_login`'s bounce (`rx.redirect("/login")`) and an `rx.link(href="/login")` click never hit
   the server, so no 307, `router.url.path == "/login"`, redirect fires. Only typing/bookmarking
   `/login`, an external link, or a reload lands on `/login/` and dead-ends. The claimant's driver
   always did `page.goto(".../login")`, i.e. only the failing case.
2. **Reflex does expose the trailing-slash-normalized route, and it is the documented var for this
   comparison.** On the *same* prod page load: `router.url.path == "/login/"` (MISMATCH) while
   `router.route_id == "/login"` (MATCH) — see `verification/loginslash/artifacts/prod0911_noslash_routeid/results.json`.
   `docs/utility_methods/router_attributes.md:110,184-186` states `route_id` = "the route pattern that
   matched the current request" and `url.path` = "the actual path in the browser", and the
   `router.page` deprecation table maps the old `router.page.path` to **`router.route_id`**, not to
   `url.path`. `reflex_local_auth/login.py:59` compares `self.router.url.path` (browser path) against
   its own route constant, so the library is comparing the wrong one of the two documented vars.
   The one-line library fix is `current_route = self.router.route_id`.
3. **The reflex-side part is real but smaller than "login is broken in prod":** reflex's own prod
   server disagrees with its dev server about trailing slashes, and reflex's own build code contains
   the fix that does not take effect (see mechanism).

Not a release blocker: byte-identical behaviour on 0.9.10.post2 (run myself, see below) and identical
source in both wheels.

### Mechanism (release branch `origin/r/pre-2026.09.10-34457666442`; line numbers verified against the branch and the installed 0.9.11a1 wheel)

- `reflex/utils/exec.py:343-368` `get_frontend_mount()` mounts
  `PrecompressedStaticFiles(directory=.web/build/client, html=True, ...)` at `/`.
- Prerendering is on by default in prod (`reflex/utils/exec.py:894-902 should_prerender_routes()` ->
  `is_prod_mode()`), so the build emits **directories**: `build/client/login/index.html`.
- `starlette/staticfiles.py:134-144` (starlette 1.6.0): a directory URL that has an `index.html` and
  does not end in `/` returns `RedirectResponse(url + "/")`, whose default status is **307**
  (`starlette/responses.py:208`). That is the entire source of the 307 — not reflex code, but reflex's
  chosen mount.
- `reflex/utils/build.py:171-190` `_duplicate_index_html_to_parent_directory`, docstring *"This makes
  accessing /route and /route/ work in production"*, copies `login/index.html` to `login.html`
  (confirmed in the log: `Copying .web/build/client/login/index.html to .web/build/client/login.html`,
  and `GET /login.html` -> 200). **StaticFiles resolves the `login/` directory before it would ever
  consider `login.html`, so the duplicate is dead weight for extensionless URLs and the 307 happens
  anyway.** This is the concrete reflex-side defect: the intent expressed in reflex's own build step
  is not achieved by its own prod server. A fix that removes the whole class of bug: in
  `PrecompressedStaticFiles.get_response`, try `path + ".html"` before delegating to `StaticFiles`
  (the files are already generated), so prod serves `/login` with 200 exactly like dev.
- Reflex's *internal* route matching is trailing-slash insensitive
  (`reflex/route.py:222` `path = "/" + path.removeprefix("/").removesuffix("/")`, regex `^...?/?$` at
  `reflex/route.py:183`), and `reflex/app.py:2225-2229` overwrites `router_data["pathname"]` with that
  matched route, which becomes `RouterData.route_id` (`reflex/istate/data.py:460`). `RouterData.url` is
  built from the raw browser URL instead (`reflex/istate/data.py:454-459`), which is why `url.path`
  keeps the slash. So `on_load`, dynamic args and page lookup all keep working on `/login/` — only
  user-code string comparisons against `router.url.path` change behaviour between dev and prod.
- Downstream trigger: `reflex_local_auth/login.py:59-64` (`LoginState.redir`).

### Exact commands (all run with cwd outside /home/user/reflex; PyPI-only installs)

```sh
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
WD=$SB/apps/verify2_up_lorem_form_1          # == verification/loginslash/ in this repo
DRIVER=$SB/envs/driver/bin/python

uv venv $SB/envs/verify2_up_lorem_form_1 --python 3.11
cd $WD && uv pip install --python $SB/envs/verify2_up_lorem_form_1/bin/python \
    --prerelease=allow 'reflex[db]==0.9.11a1' 'reflex-local-auth==0.5.0'
uv venv $SB/envs/verify2_up_lorem_form_1_b0910 --python 3.11
cd $WD && uv pip install --python $SB/envs/verify2_up_lorem_form_1_b0910/bin/python \
    'reflex[db]==0.9.10.post2' 'reflex-local-auth==0.5.0'

# minimal app: pages /, /login (reflex_local_auth.pages.login_page as the library's own docstring
# prescribes), /register, /protected (@require_login); every page prints router.url.path,
# router.route_id and the two comparisons against reflex_local_auth.routes.LOGIN_ROUTE.

# 1) 0.9.11a1 DEV
cd $WD && ./serve.sh $WD/slashauth $SB/envs/verify2_up_lorem_form_1 6166 10566 $WD/logs/slashauth_0911_dev.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $DRIVER drive_slash.py \
    http://localhost:6166 dev0911_noslash artifacts/dev0911_noslash noslash   # login works, 0.6 s
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $DRIVER drive_slash.py \
    http://localhost:6166 dev0911_slash   artifacts/dev0911_slash   slash     # typed /login/ -> stuck
./stop.sh $WD/slashauth 6166 10566

# 2) 0.9.11a1 PROD (same port twice)
cd $WD && ./serve.sh $WD/slashauth $SB/envs/verify2_up_lorem_form_1 6164 6164 $WD/logs/slashauth_0911_prod2.log --env prod
curl -sI --noproxy '*' http://localhost:6164/login          # 307, location: .../login/
NO_PROXY=... $DRIVER drive_slash.py http://localhost:6164 prod0911_noslash_routeid artifacts/prod0911_noslash_routeid noslash
NO_PROXY=... $DRIVER drive_paths.py http://localhost:6164 prod0911_paths artifacts/prod0911_paths
./stop.sh $WD/slashauth 6164

# 3) 0.9.10.post2 PROD baseline (fresh copy; delete reflex.lock first - a bun-1.4 v2 lockfile
#    makes 0.9.10.post2 abort with "delete the reflex.lock directory and rerun")
cd $WD && ./serve.sh $WD/slashauth_b0910 $SB/envs/verify2_up_lorem_form_1_b0910 6165 6165 $WD/logs/slashauth_0910_prod.log --env prod
NO_PROXY=... $DRIVER drive_slash.py http://localhost:6165 prod0910_noslash artifacts/prod0910_noslash noslash
NO_PROXY=... $DRIVER drive_paths.py http://localhost:6165 prod0910_paths artifacts/prod0910_paths
./stop.sh $WD/slashauth_b0910 6165

# 4) mechanism check: prod with prerendering off
cd $WD/slashauth && REFLEX_DIR=$SB/reflex_dirs/v2ulf1_slashauth REFLEX_TELEMETRY_ENABLED=false \
    REFLEX_SSR=false $SB/envs/verify2_up_lorem_form_1/bin/reflex run --env prod \
    --frontend-port 6167 --backend-port 6167 --loglevel debug
NO_PROXY=... $DRIVER drive_slash.py http://localhost:6167 prod0911_nossr artifacts/prod0911_nossr noslash
```

### Results

| run | GET /login | `router.url.path` on the login page | `url.path == LOGIN_ROUTE` | `route_id` | post-login redirect | session created |
| --- | --- | --- | --- | --- | --- | --- |
| 0.9.11a1 dev, typed `/login` | 200 | `/login` | MATCH | `/login` | yes, 0.6 s -> `/` | yes |
| 0.9.11a1 dev, typed `/login/` | 200 | `/login/` | MISMATCH | `/login` | **never (20 s)** | yes (AUTHED on `/`) |
| 0.9.11a1 prod, typed `/login` | **307 -> /login/** | `/login/` | MISMATCH | `/login` | **never (20 s)** | yes (AUTHED on `/`) |
| 0.9.10.post2 prod, typed `/login` | **307 -> /login/** | `/login/` | MISMATCH | `/login` | **never (20 s)** | yes (AUTHED on `/`) |
| 0.9.11a1 prod, `require_login` bounce | n/a (client nav) | `/login` | MATCH | `/login` | yes, 0.6 s -> `/protected/` | yes |
| 0.9.11a1 prod, `rx.link` click | n/a (client nav) | `/login` | MATCH | `/login` | yes, 0.5 s -> `/` | yes |
| 0.9.10.post2 prod, bounce / link click | n/a | `/login` | MATCH | `/login` | yes, 0.6 s | yes |
| 0.9.11a1 prod, `REFLEX_SSR=false` | 404 (no redirect) | `/login` | MATCH | `/login` | yes, 0.6 s -> `/` | yes |

No console errors or page errors in any run beyond the known-benign set; no failed requests other than
the 404s in the `REFLEX_SSR=false` run (reflex issue #6983). Deterministic: 3 prod runs on 0.9.11a1,
2 on 0.9.10.post2, all identical. The 307 preserves the query string (`/login?next=x` ->
`/login/?next=x`) and uses the request Host, so it is not a proxy artifact (all probes ran with
`--noproxy '*'` / client-side `NO_PROXY` only).

### Refutations attempted and their outcome

- *Environment quirk (proxy / ports / cwd shadowing)*: ruled out. Own ports, own venvs, the app asserts
  `"/envs/verify2_up_lorem_form_1" in rx.__file__` at import, `--noproxy '*'` on every curl, and the
  redirect is emitted by granian/starlette locally.
- *Example-app bug*: ruled out. The minimal app registers `reflex_local_auth.pages.login_page` at
  `reflex_local_auth.routes.LOGIN_ROUTE` exactly as the library's own module docstring documents; no
  form-designer code involved.
- *API misuse*: **partially lands** — not by the app, but by the library: `router.url.path` is
  documented as the browser path, `router.route_id` as the matched route pattern (see above). This is
  why the fix belongs in reflex-local-auth.
- *Pre-existing*: **confirmed pre-existing.** 0.9.10.post2 prod behaves identically, and
  `reflex/utils/exec.py` (`html=True` mount), `reflex/utils/build.py`
  (`_duplicate_index_html_to_parent_directory`), `reflex/route.py:220` and starlette 1.6.0 are the same
  in both installs. Nothing in this train touches it.
- *Flaky*: no, 5/5 deterministic.
- *Documented behaviour*: no reflex doc or issue mentions the prod trailing-slash redirect; GitHub
  search over reflex-dev/reflex found no issue for it (the adjacent prod-404 one is #6983).

### Recommended actions (neither blocks this release)

1. reflex-local-auth: `current_route = self.router.route_id` in `LoginState.redir` (or compare
   `rstrip("/")`). App-author workaround today: `reflex_local_auth.routes.set_login_route("/login/")`
   is prod-only-correct and breaks dev — prefer monkey-patching `redir` or pinning nothing and using
   in-app links, which already work.
2. reflex: make the prod server serve `/route` with 200 instead of 307 — the `route.html` duplicates
   `build.py` already writes are exactly what is needed; consult them in
   `PrecompressedStaticFiles.get_response` before falling through to `StaticFiles`' directory branch.
   This also removes the dev/prod divergence for every app that compares `router.url.path` to a route
   literal (e.g. active-nav highlighting), which is the general form of this bug.

### Evidence

```
verification/loginslash/slashauth/            minimal repro app (0.9.11a1)
verification/loginslash/slashauth_b0910/      same app, 0.9.10.post2 baseline copy
verification/loginslash/drive_slash.py        register + login via /login or /login/, records
                                              url.path, route_id, both comparisons, where it lands
verification/loginslash/drive_paths.py        the three ways of reaching the login page (hard load /
                                              require_login bounce / rx.link click), fresh context each
verification/loginslash/serve.sh, stop.sh     per-app REFLEX_DIR, pgid kill, port check
verification/loginslash/http_probes.txt       the full curl status matrix (dev / prod / prod+no-SSR)
verification/loginslash/artifacts/dev0911_noslash|dev0911_slash|prod0911_noslash|
   prod0911_noslash_routeid|prod0911_paths|prod0910_noslash|prod0910_paths|prod0911_nossr/
                                              results.json + 02_login_page.png, 03_after_login.png,
                                              04_index.png (AUTHED), a_hard_load_login.png etc.
verification/loginslash/logs/slashauth_0911_dev.log, slashauth_0911_prod.log,
   slashauth_0911_prod2.log, slashauth_0910_prod.log, slashauth_0911_prod_nossr.log
                                              (the prod logs contain the
                                              "Copying .web/build/client/login/index.html to
                                              .web/build/client/login.html" line)
```

All processes started for this verification were killed (`stop.sh` + explicit `kill` of the two
lingering `reflex run` parents); ports 6164-6167 and 10564-10567 are free.

## VERIFICATION: Prod returns HTTP 404 for the first document request of any dynamic route (the SPA fallback body is served with the 404 status)

Independent adversarial verification (second agent, own working dir
`$SB/apps/verify2_up_lorem_form_2/`, own 35-line app written from the written repro alone — no
form-designer, no `reflex[db]`, no `reflex-local-auth` — own ports 6168/6169/6170 + backend 10570,
shared read-only venvs `$SB/envs/smoke` = 0.9.11a1 and `$SB/envs/base0910` = 0.9.10.post2,
`$SB/envs/driver` for Chromium).

### Verdict: CONFIRMED as a real framework defect, but it is ALREADY FILED UPSTREAM

`reflex-dev/reflex#6983` — *"Prod mode serves HTTP 404 status for direct loads of valid
dynamic-route URLs (SPA fallback body renders fine)"*, opened **2026-08-28 during 0.9.9a1
pre-release testing**, still open, assigned (ENG-11822), with an open fix PR
`reflex-dev/reflex#6996` *"Serve SPA fallback with 200 for routable paths in prod static serving"*
(route-matcher on `PrecompressedStaticFiles`, `closes #6983`) that **did not land in this train**.
The issue body already contains the same curl matrix and the same root-cause analysis, and this
campaign's own **FINDING-037** is the SSR-off sibling of it (its 2026-09-11 comment on #6983 says
so). So this claim is genuine but a **duplicate**: it should be folded into FINDING-037 / the #6983
thread as "still unfixed in 0.9.11a1; PR #6996 pending", not filed as a new finding.

### What I reproduced myself

`verification/dyn404/` — pages `/` (static), `/static-page` (static), `/item/[item_id]` (dynamic),
`/posts/[[...splat]]` (catchall). `reflex run --env prod` on one port; every status via
`curl --noproxy '*'`.

| request | 0.9.11a1 prod | 0.9.10.post2 prod | 0.9.11a1 dev |
| --- | --- | --- | --- |
| `/` | 200 | 200 | 200 |
| `/static-page` | 307 → `/static-page/` | 307 → `/static-page/` | 200 |
| `/static-page/` | 200 | 200 | 200 |
| `/item/1`, `/item/1/`, `/item/abc`, `/item/7` | **404** | **404** | 200 |
| `/posts`, `/posts/`, `/posts/a`, `/posts/a/b` (catchall) | **404** | **404** | n/a |
| `/nonexistent-route` | 404 | 404 | **200** |

Body of every 404: 5262 bytes, byte-identical to `.web/build/client/404.html`, which is in turn
byte-identical (md5 `f6347ab7…`) to `.web/build/client/__spa-fallback.html`. So a live dynamic page
and a typo'd URL are indistinguishable at the HTTP layer — status *and* body.

Chromium (`verification/drive_dyn404.py`, results in
`verification/artifacts/dyn404_verify/browser_0911_prod/results.json`): `/item/42` document
response **status 404**, `#marker` = `item-page`, and the state var echoes `/item/42` — the page and
its dynamic arg work perfectly. It is a status-line-only defect for browser users.

### Corrections to the claim as written

1. **Not "the first document request" — every document request.** Five consecutive identical
   `GET /item/7` → 404, 404, 404, 404, 404; `HEAD /item/7` → 404 (so HEAD-based uptime monitors see
   it too); `Accept-Encoding: gzip` → 404 with `content-encoding: gzip` (the precompressed sidecar
   re-route preserves the 404 deliberately). Only *client-side* navigations escape it, because they
   issue no document request at all — that is why it looks like "the first" one.
2. **Catchall/splat routes are hit as well**, including the bare `/posts` and `/posts/` forms of
   `/posts/[[...splat]]`, which are real routable pages with no args at all.
3. **Dev is not "correct", it merely never 404s**: dev answers `/nonexistent-route` with 200 too.
   The dev/prod disagreement is real but both sides are wrong in opposite directions (cf. #6463,
   "soft 404: 200 for non-existent routes").
4. **Pre-existing is understated as "0.9.10.post2 also"** — the mechanism dates to
   `0d01de553` *"use sirv with spa fallback (#5711)"*, 2025-08-14 (the `404.html` copy) and
   `1dd2d1a99` *"ENG-8961: Single port is only prod option (#6297)"*, 2026-04-09 (serving the build
   through Starlette `StaticFiles(html=True)`). Nothing in this train touches it: the only commit in
   `v0.9.10..origin/r/pre-2026.09.10-34457666442` over `build.py`/`exec.py`/
   `precompressed_staticfiles.py` is `e3e39a83c` (#7044, the `frontend_path`-without-prerender build
   fix).

### Refutation attempts and what they showed

| angle | result |
| --- | --- |
| environment (proxy / `NO_PROXY` / ports / cwd shadowing) | refuted — `curl --noproxy '*'` on my own reserved ports, own app dir, app asserts `"/envs/" in rx.__file__` and prints the venv path into the log (`logs/dyn404_0911_prod2_trimmed.txt:62`); Chromium sees the same 404 |
| flaky | refuted — 5/5 identical requests, 3 prod builds, 2 reflex versions, GET + HEAD + gzip |
| pre-existing on 0.9.10.post2 | **true** (ran the baseline myself in a separate app dir + venv; identical matrix) |
| demo/example-app bug | refuted — a 35-line app with zero third-party deps reproduces it; nothing in form-designer is involved |
| API misuse / documented behavior | not misuse: the app uses the documented `[arg]`/`[[...splat]]` route syntax and the documented prod command. It is *undocumented* behavior, which is exactly what #6983 asks to resolve ("fix the status or document the limitation") |
| regression in this train | **no** — see correction 4 |
| already known | **yes — #6983 open since 2026-08-28, fix PR #6996 open, not in 0.9.11a1** |
| release blocker for 0.9.11 | **no** — unchanged from the previous stable, and it is a status line, not a broken page |

### Mechanism (file:line, release branch `origin/r/pre-2026.09.10-34457666442`)

1. `reflex/utils/build.py:278-283` — after the prod build, the react-router SPA fallback is copied
   over the 404 document:
   ```python
   spa_fallback = static_dir / constants.ReactRouter.SPA_FALLBACK   # "__spa-fallback.html"
   if not spa_fallback.exists():
       spa_fallback = static_dir / "index.html"
   if spa_fallback.exists():
       path_ops.cp(spa_fallback, static_dir / "404.html")
   ```
   (`SPA_FALLBACK` / `STATIC` at `packages/reflex-base/src/reflex_base/constants/base.py:176` and
   `:44`.)
2. `reflex/utils/exec.py:343-370` `get_frontend_mount()` mounts `.web/build/client` as
   `PrecompressedStaticFiles(directory=static_dir, html=True, …)`.
3. `starlette/staticfiles.py:147-152` (starlette 1.6.0) — `html=True` semantics: any path that maps
   to no file is answered with `FileResponse(404.html, status_code=404)`.
4. `reflex/utils/precompressed_staticfiles.py:170-192` re-routes exactly that fallback through
   `file_response(..., status_code=404)` to attach the gzip/br sidecar and `Vary`, so the compressed
   path keeps the 404 as well.

Dynamic and splat routes are never prerendered to files — the build log says so itself
(`⚠️ Paths with dynamic/splat params cannot be prerendered when using prerender: true`,
`logs/dyn404_0911_prod2_trimmed.txt:185`) — so they always land on step 3. Static routes escape only
because prerendering wrote them as `<route>/index.html` (hence their 307 → 200).
Note this is a property of the *build artifact* as much as of reflex's server: the fallback document
is literally named `404.html`, so any static host that honors that convention (GitHub Pages, an S3
website error document) will serve exported dynamic routes with 404 too.
PR #6996's approach — match the request path against `app.router` / a compiled `routes.json`
manifest and serve the fallback with 200 for routable paths only — is the right fix and would also
close FINDING-037 and #6463.

### My own severity / regression / downstream call

- severity **low-medium** (claim said medium): no user-visible breakage in a browser (page and
  dynamic args render fine), but crawlers, uptime monitors, CDNs and error dashboards all treat live
  deep links as missing, and `curl` cannot distinguish a real page from a typo. Already triaged
  upstream with a fix in flight.
- regression **false** for this train (mechanism from 2025-08-14 / 2026-04-09; baseline verified by
  hand).
- downstream **false** — `reflex/utils/build.py`, `reflex/utils/exec.py` and
  `reflex/utils/precompressed_staticfiles.py` are all reflex's own; starlette's `html=True`
  semantics are correct for what reflex asked for.
- **Action: no new finding.** Add to FINDING-037 / #6983 that 0.9.11a1 still ships the behavior and
  that PR #6996 has not landed.

### Exact commands (all re-runnable)

```sh
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
WD=$SB/apps/verify2_up_lorem_form_2          # copy verification/dyn404 + the scripts here
# app: verification/dyn404/ — /, /static-page, /item/[item_id], /posts/[[...splat]]

# 0.9.11a1 prod (ONE port for both)
cd $WD && ./serve.sh $WD/dyn404 $SB/envs/smoke 6168 6168 $WD/logs/dyn404_0911_prod2.log --env prod
./probe_status.sh http://localhost:6168 $WD/artifacts/status_0911_prod2.json \
    / /static-page/ /item/7 /posts /posts/ /posts/a /posts/a/b /nonexistent-route
for i in 1 2 3 4 5; do curl -s -o /dev/null -w '%{http_code}\n' --noproxy '*' \
    http://localhost:6168/item/7; done                      # 404 x5, not just the first
curl -sI -o /dev/null -w 'HEAD %{http_code}\n' --noproxy '*' http://localhost:6168/item/7
curl -s -D - -o /dev/null -H 'Accept-Encoding: gzip' --noproxy '*' http://localhost:6168/item/7 | head -3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python drive_dyn404.py http://localhost:6168 \
    $WD/artifacts/dyn404/0911_prod dyn404_0911_prod     # /item/42 -> status 404, renders
md5sum $WD/dyn404/.web/build/client/{404.html,__spa-fallback.html}   # identical
./stop.sh $WD/dyn404 6168

# 0.9.10.post2 prod baseline (separate app dir; delete the copied reflex.lock first — it is a
# bun-1.4 v2 lockfile and 0.9.10 uses the system bun 1.3.11, which rejects it)
mkdir -p $WD/dyn404_b0910 && tar -C $WD/dyn404 --exclude=.web --exclude=logs -cf - . \
    | tar -C $WD/dyn404_b0910 -xf - && rm -rf $WD/dyn404_b0910/reflex.lock
cd $WD && ./serve.sh $WD/dyn404_b0910 $SB/envs/base0910 6169 6169 $WD/logs/dyn404_0910_prod.log --env prod
./probe_status.sh http://localhost:6169 $WD/artifacts/status_0910_prod.json \
    / /static-page/ /item/1 /item/abc /nonexistent-route
./stop.sh $WD/dyn404_b0910 6169

# 0.9.11a1 dev contrast
cd $WD && ./serve.sh $WD/dyn404 $SB/envs/smoke 6170 10570 $WD/logs/dyn404_0911_dev.log
./probe_status.sh http://localhost:6170 $WD/artifacts/status_0911_dev.json \
    / /static-page /item/1 /nonexistent-route     # all 200, including the nonexistent one
./stop.sh $WD/dyn404 6170 10570

# dating it
git log --reverse --oneline -S'404.html' --all -- reflex/utils/build.py     # 0d01de553 2025-08-14 (#5711)
git log --oneline -S'get_frontend_mount' --all -- reflex/utils/exec.py      # 1dd2d1a99 2026-04-09 (#6297)
git log --oneline v0.9.10..origin/r/pre-2026.09.10-34457666442 -- \
    reflex/utils/build.py reflex/utils/exec.py reflex/utils/precompressed_staticfiles.py  # only e3e39a83c (#7044)
```

Two app-authoring mistakes of my own, recorded because they cost a run each and are *not* framework
bugs: a `@rx.var` named `item_id` on a state trips
`DynamicRouteArgShadowsStateVarError` for the `[item_id]` route (good error), and an app package
without `__init__.py` builds fine but granian then dies with
`AttributeError: module 'dyn404' has no attribute 'app'` (a poor error for a missing `__init__.py`).
`[[...rest]]` is rejected — reflex only allows the literal `[[...splat]]`.

### Evidence (this cluster dir)

- `verification/dyn404/` — my 35-line repro app as run; `verification/probe_status.sh`,
  `verification/drive_dyn404.py`
- `verification/artifacts/dyn404_verify/status_0911_prod.json`, `status_0911_prod2.json`
  (splat + repeats), `status_0910_prod.json`, `status_0911_dev.json` — the status matrices above
- `verification/artifacts/dyn404_verify/browser_0911_prod/results.json` (+ `item_42.png`,
  `index.png`, `static-page.png`, empty `console.json`/`bad_responses.json` apart from the 404
  document itself) — Chromium: document status 404, page renders
- `verification/logs/dyn404_0911_prod2_trimmed.txt`, `verification/logs/dyn404_0910_prod_trimmed.txt`
  — venv assertion line, the dynamic/splat prerender warning, and the list of routes actually
  prerendered on each version
