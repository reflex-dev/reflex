# Cluster `upgrades_a` — in-place upgrade regression, reflex-examples set A (0.9.12 → 0.10.0a1)

Date 2026-10-06. Host: 4-CPU Linux container (shared with other agents), Python 3.12.3, Node 22.22.0,
bun 1.4.2, uv 0.11.32, Playwright 1.63 / Chromium (HeadlessChrome 141). Every framework install came
from PyPI into isolated venvs under `$SB/envs/`; nothing was installed from or run inside the
`/home/user/reflex` checkout (release source was only read via `git show origin/r/pre-2026.10.05-37378928999:…`).

`SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`, `W=$SB/apps/upgrades_a`.
Apps were copied from `$SB/downloads/reflex-examples` (commit `ebe19ff`).

## Verdict

**No regression found in any of the 7 example apps.** form-designer, reflexle, github-stats, clock,
counter, traversal and json-tree were each driven in Chromium on 0.9.12, upgraded **in place** (same
venv, same app dir with `.web/`, `reflex.lock/`, `.states/`, `reflex.db` kept), re-driven, then re-driven
again after `rm -rf .web` (cold). Every flow that worked on 0.9.12 worked after the upgrade and after the
cold rebuild, with the identical set of console error/warning signatures (all app-level, see below), no
page errors and no failed/4xx/5xx requests.
The 0.9.12-written sqlite data (bcrypt user, LocalAuth session, forms, fields, options, responses) is
fully usable on 0.10.0a1, LocalStorage written by 0.9.12 (auth token, github-stats JSON) and the
`rx.Cookie` zone set by 0.9.12 are picked up by the new `hydrate_and_load` connect path (#7064) in dev and
prod, and a Redis state pickled by 0.9.12 is unpickled correctly by 0.10.0a1.

Findings worth acting on are packaging/upgrade-path ones, not app breakages:
1. (medium) `reflex[db]==0.10.0a1` caps `sqlmodel<0.0.45`, but every `reflex[db]==0.9.12` install resolved
   sqlmodel ≥0.0.45 (0.0.45 shipped 3 h before 0.9.12). Re-resolving with the db extra downgrades
   sqlmodel 0.0.47→0.0.44, which flips plain `datetime` columns from aware-UTC to naive on read. The
   plain `-U reflex==0.10.0a1` upgrade leaves 0.0.47 installed and no checker flags it.
2. (low, not a regression) a stale 0.9.12 prod tab connected to the 0.10.0a1 backend gets no user-facing
   signal (only a server-side warning) and keeps running the old protocol through the compat path.
3. (low, not a regression) upgrading the venv while `reflex run` (dev) is running makes every later hot
   reload crash the backend worker with an opaque `ImportError` until the CLI is restarted.

## Rerun instructions

Ports (reserved range only): form-designer 3140/8140 (prod: 3140 single port), reflexle 3142/8142
(prod 3142), github-stats 3144/8144 (prod 3144; 3145 once by mistake = different origin), clock
3146/8146, clock-prod 3147 (prod), counter + counter-live 3148/8148, traversal 3150/8150, json-tree
3152/8152 (prod 3152), github-stats-redis* 3153 (prod), GraphQL stub 8158, redis 8159.

Helpers (`bin/`): `run_app.sh <appdir> <venv> <fp> <bp> <log> [reflex run args]` starts
`reflex run --loglevel debug` under `setsid`, records the pid in `run/<app>.pid`, polls `/` and
`/ping` until both answer 200. `stop_app.sh <appdir> <ports…>` sends SIGTERM to the main pid only,
reports orphans still listening, then hard-kills the group/listeners. `ports.sh` lists listeners in the
reserved range. `seq_misc.sh <app> <fp> <bp>` runs base→upgrade→up→cold for counter/traversal/json-tree.

```bash
export SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad W=$SB/apps/upgrades_a
# copy apps (never run in the clone)
cd $SB/downloads/reflex-examples && tar --exclude=.web --exclude=node_modules --exclude=.states \
  --exclude=__pycache__ --exclude='*.db' -cf - form-designer reflexle github-stats clock counter traversal json-tree | tar -C $W -xf -
# apply the two opt-in QA patches (default behaviour unchanged): patches/*.diff
#   form-designer: FD_FIX_FIELD_NAME=1 -> rx.form.field(name=field.name) (pre-existing FormMessage crash workaround)
#   github-stats : QA_GITHUB_GRAPHQL_URL=<stub> -> fetcher talks to scripts/github_stub.py (no GitHub token here)
# per-app venv, baseline as a stable user resolves it (NO prerelease flag)
cd $SB && uv --no-config venv --python 3.12 $SB/envs/upgrades_a-<app>
cd $SB && uv --no-config pip install --python $SB/envs/upgrades_a-<app>/bin/python -r $W/<app>/requirements.txt 'reflex==0.9.12'
# baseline run + drive (example: form-designer)
$W/bin/run_app.sh $W/form-designer $SB/envs/upgrades_a-form-designer 3140 8140 $W/logs/fd-base-run1.server.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/drive_form_designer.py \
  http://localhost:3140/ $W/shots/fd fd-base-full full $W/profiles/fd 0.9.12
$W/bin/stop_app.sh $W/form-designer 3140 8140
FD_FIX_FIELD_NAME=1 $W/bin/run_app.sh ... fd-base-run2-fix.server.log ; drive_form_designer.py ... fd-base-entry entry $W/profiles/fd 0.9.12
# in-place upgrade (same venv, same app dir)
cd $SB && uv --no-config pip install --python $SB/envs/upgrades_a-<app>/bin/python --prerelease=allow -U 'reflex==0.10.0a1'
# first post-upgrade run + drive ("up" mode reuses the SAME persistent browser profile)
$W/bin/run_app.sh ... fd-up-run1.server.log ; drive_form_designer.py ... fd-up-up up $W/profiles/fd 0.10.0a1
# cold
rm -rf $W/<app>/.web ; run_app.sh ... ; drive ...
```

Drivers (`scripts/`, all run with `$SB/envs/driver/bin/python`, `NO_PROXY=localhost,127.0.0.1` on the
driver only; each asserts it runs from the driver venv and writes `<outdir>/<tag>.json` with checks,
full console, page errors, failed/≥400 requests, `/_event` websocket frames, plus screenshots):

| script | invocation |
|---|---|
| `drive_form_designer.py` | `<url> <outdir> <tag> full\|up\|entry <profile_dir> [expect_version]` |
| `drive_reflexle.py` | `<url> <outdir> <tag>` |
| `drive_github_stats.py` | `<url> <outdir> <tag> fresh\|persist <profile_dir> http://127.0.0.1:8158` (needs `github_stub.py 8158` running and the server started with `QA_GITHUB_GRAPHQL_URL=http://127.0.0.1:8158/graphql GITHUB_API_TOKEN=qa-dummy-token`) |
| `drive_clock.py` | `<url> <outdir> <tag>` |
| `drive_misc.py` | `counter\|traversal\|json-tree <url> <outdir> <tag>` |
| `stale_tab_clock.py` | `<url> <outdir> <tag> <ctldir>` — keeps one tab open; operator touches `<ctldir>/down`, `<ctldir>/up` |
| `stale_tab_redis_gh.py` | same control protocol, github-stats + Redis (writes `<ctldir>/token`) |
| `live_tab_counter.py` | `<url> <outdir> <tag> <ctldir>` — operator touches `<ctldir>/edited` |
| `sqlmodel_datetime_probe.py` | `<venv>/bin/python sqlmodel_datetime_probe.py <venv-substring> <db> write\|read` |
| `compare_runs.py` | `<json>…` — check-status + console-signature diff between runs |
| `github_stub.py` | `<port>` — canned GraphQL `userInfo`, unknown users `ghost*` → `user: null`, `GET /count` |

Prod runs: `REFLEX_API_URL=http://localhost:<P> run_app.sh <app> <venv> <P> <P> <log> --env prod`.

## Resolution / upgrade mechanics

Baseline freeze (all 7 apps, `freeze/<app>-base.txt`): reflex 0.9.12, reflex-base 0.9.12, components
code 0.9.6, core 0.9.10.post1, gridjs 0.9.2.post1, markdown 0.9.4.post1, moment 0.9.4, plotly 0.9.7,
radix 0.9.10.post1, recharts 0.9.4.post1, sonner 0.9.4, dataeditor 0.9.3.post1, hosting-cli 0.1.72,
wrapt 2.3.0; form-designer adds reflex-local-auth 0.5.0, pydantic 2.13.5, **sqlmodel 0.0.47**,
alembic 1.20.0; reflexle adds reflex-global-hotkey 1.2.3; clock adds pytz 2022.7.1.

`uv pip install --prerelease=allow -U 'reflex==0.10.0a1'` (the brief's command; `freeze/<app>-base-to-up.diff`,
identical for all 7): reflex/reflex-base 0.10.0a1, + reflex-build-sdk 0.0.5, components code/core/gridjs/
markdown/moment/plotly/radix/recharts → 0.10.0a1, hosting-cli 0.1.73a1, wrapt 2.5.0. sonner 0.9.4 /
dataeditor 0.9.3.post1 / lucide / react-player unchanged (no alphas published). **pydantic did NOT jump to
the beta and sqlmodel stayed 0.0.47** with this command (the db extra is not part of the resolution).
`uv pip check` and `pip check` both report the result as consistent although reflex[db] 0.10.0a1 says
`sqlmodel<0.0.45` (reflex-local-auth requires `reflex[db]`).

Other upgrade commands, against the baseline form-designer env (`freeze/form-designer-dryrun-*.txt`,
`freeze/fd-pip-*.txt`):
| command | result |
|---|---|
| `uv pip install 'reflex==0.10.0a1'` (no flag) and `uv pip install -U 'reflex[db]==0.10.0a1'` | **fails**: "no version of reflex-base==0.10.0a1 … pre-releases weren't enabled" (uv only allows pre-releases named by the user; the 0.9.12a1 campaign's older uv produced a mixed graph instead) |
| `uv pip install --prerelease=allow -U 'reflex[db]==0.10.0a1'` | all alphas **plus pydantic 2.13.5→2.14.0b2 (beta) and sqlmodel 0.0.47→0.0.44 (downgrade)** |
| `pip install -U 'reflex==0.10.0a1'` (no `--pre`; real install in a copy venv) | only reflex + reflex-base → 0.10.0a1; every component stays 0.9.x, hosting-cli 0.1.72 (mixed graph) — the app works in it (below) |

`.web/package.json` diff after the upgrade (`pkg/<app>-base-to-up.package.diff`, same for every app):
react / react-dom 19.2.8→19.3.0, react-error-boundary 6.1.2→6.1.6, socket.io-client 4.8.3→4.8.4,
autoprefixer 10.5.4→10.6.1, postcss 8.5.26→8.5.29, vite 8.2.2→8.3.2, and moment 2.30.1→2.31.0 where
moment is used (form-designer). Nothing pruned (no `bun remove`), no unexpected dependency, `mergician`
still `"v2.0.2"` (known cosmetic leading-v from the 0.9.12a1 campaign, unchanged). No old pins left in
`bun.lock`; `reflex.lock/{package.json,bun.lock}` byte-identical to `.web/` after every run; cold runs
converge to the byte-identical `package.json` for all 7 apps; an in-place-upgraded `.web/` has exactly the
same file set as a cold-built one (counter, `pkg/counter-*.web.files`).

First post-upgrade run (e.g. `logs/fd-up-run1.server.log`): "Restoring lockfiles" copies
`reflex.lock/bun.lock` into `.web`, `bun install --frozen-lockfile` reinstalls the 0.9.12 graph (376
packages), then `bun add -d …vite@8.3.2…` and `bun add …react@19.3.0…` move to the new pins and the
lockfiles are saved back. No warnings, no "lockfile had changes", no npmmirror fallback, no vite
`configLoader` warning; startup 4–7 s (warm bun cache). The only new log line is Debug-level
`error: script "dev" exited with code 143` at shutdown.

Shutdown (`stop_app.sh`, SIGTERM to the main pid, no TTY): on **0.9.12** the main pid never exits within
15 s and the `react-router dev` node process keeps the frontend port (orphan) — every 0.9.12 run; on
**0.10.0a1** "Reflex app stopped." in ~2–3 s with all ports free — every run (#7328, positive change).

Hot reload (dev): on 0.9.12 a worker reload re-runs `bun install --frozen-lockfile` + two `bun add`
(`logs/fd-base-run1.server.log` 253-300); on 0.10.0a1 it logs "Using cached value for
_install_frontend_packages" and skips the package manager (`logs/counter-up-hotreload.server.log`, #7236,
positive change).

## Per-app results (`shots/<app>/<tag>.json`; checks pass/fail/anomaly)

| app | base 0.9.12 | up (in place) | cold | prod 0.10.0a1 | notes |
|---|---|---|---|---|---|
| form-designer `full`/`up` | 16/0/3 | 10/0/2 | 10/0/3 | 12/0/1 (`fd-up-prod-up`) | anomalies = the pre-existing app bugs below, identical on every run |
| form-designer `entry` (FD_FIX=1) | 13/1*/1 | 14/0/1 | – | 15/0/0 (`fd-up-prod-entry`) | *driver looked for a cookie literally named `client_token`; the cookie `reflex___state____state.form_designer___pages___form_entry____form_entry_state.client_token_rx_state_` is present in `fd-base-entry.json` notes.final_cookies — fixed driver, later runs pass |
| reflexle | 19/0/0 | 19/0/0 | 19/0/0 | 18/0/1 (favicon.ico 404: app ships no favicon) | real keyboard via reflex-global-hotkey, toast, bg task, @rx.memo buttons, reload, 2nd context |
| github-stats `fresh`/`persist` | 14/1/1 | 12/0/2 | 12/0/2 (`gh-cold3`) | 13/0/1 (`gh-up-prod2`) | base fail = dark-appearance check (pre-existing, see below); `gh-cold`/`gh-cold2` fails were driver key-matching bugs (fixed, see below); `gh-up-prod` used port 3145 = new origin with empty LocalStorage (not a bug) |
| clock | 17/0/0 | 17/0/0 | 17/0/0 | stale-tab test only | rx.Cookie zone survives reload and the upgrade |
| counter | 8/0/0 | 8/0/0 | 8/0/0 | – | |
| traversal | 13/0/0 | 13/0/0 | 13/0/0 | – | DFS/BFS self-requeueing event chains + rx.toast, deque var with @serializer |
| json-tree | 8/0/0 | 8/0/0 | 8/0/0 | 8/0/0 | dynamic components in a state var + computed var, rx.clipboard paste, survives reload |
| form-designer, pip mixed graph | 16/0/4 | 10/0/3 (`fdpip-mixed-up`), entry 14/0/1 | – | – | reflex 0.10.0a1 + 0.9.x components: identical behaviour |
| form-designer, full `reflex[db]` alpha graph | (same copy) | 10/0/3 (`fdpip-dbextra-up`), entry 14/0/1 | – | – | pydantic 2.14.0b2 + sqlmodel 0.0.44 after `--prerelease=allow -U -r requirements.txt 'reflex[db]==0.10.0a1'`: identical behaviour, 0.0.47-written rows readable |

`compare_runs.py` over base/up/cold(/prod): identical check statuses and identical unexpected-console
signature sets for every app (`logs/compare_runs.txt`); the only status differences are the driver
artifacts explained in the table.

### form-designer (reflex[db] + reflex-local-auth 0.5.0)
Flows: home (README via rx.markdown, `importlib.metadata` version text), register, login, protected
editor, create form via debounced input, add text / number(required) / radio(2 options) / select(2
options) fields (options dialog; `rx.call_script` focus on the newest option input verified), reload,
preview page, logout → protected page bounces to /login, re-login. `entry` mode (server started with
`FD_FIX_FIELD_NAME=1`): required-field toast ("Required field 'How old are you?' is missing a
response"), fill + submit → /form/success, rx.Cookie client token set, responses page accordion with
`rx.moment` timestamps.
Across the upgrade, with the same persistent Chromium profile: `/edit/form/` renders **without logging
in** (0.9.12-written LocalStorage `_auth_token` → `hydrate_and_load` → `authenticated_user`), the form
is listed by `on_mount`, fields persist, a new email field is added; the responses page lists the 0.9.12
response next to the new ones with correct moment timestamps.
DB (`logs/fd-db-rows-after-upgrade.txt`): alembic head `4c92535dbbbd`, 1 user, the same LocalAuth
session id, 1 form, 6 fields, 4 options, 3 responses / 12 field values — every 0.9.12 row intact.
`reflex db migrate` after the upgrade: rc 0, no output (no-op); `reflex db makemigrations --message
qa_probe`: rc 0, no file generated, DB untouched (no schema drift).
Prod (0.10.0a1): dynamic routes `/edit/form/1`, `/form/1`, `/responses/1` now answer **200** (were 404 on
0.9.12, #6996); unknown `/nope` 404; `/login` 307→`/login/`.
Pre-existing app bugs re-checked (identical on 0.9.12 and 0.10.0a1, not regressions):
`/form/<id>` crashes with "``FormMessage` must be used within `FormField` or specify the `name` prop`"
(unchanged since 0.9.8); login never auto-redirects away from `/login` (dev URL stays `/login`, prod
`/login/`); responses page console errors: `collapsible` non-boolean attribute, `<button>` nested in
`<button>` (accordion header + tooltip button), 3× emotion `:first-child` SSR warning. The 0.9.8-era
"Invalid DOM property stroke-linecap" errors no longer appear on either version. App-level pydantic
serializer UserWarnings (`form_id` str vs int, `type_` str vs enum) appear on both versions.

### github-stats (rx.LocalStorage, recharts, bg task, dynamic route)
GitHub's API answers 403 through the agent proxy without a token, so the fetcher was pointed at
`scripts/github_stub.py` (opt-in env var). Flows: add alice/bob/ghost1 (unknown → chip, no data),
remove bob, LocalStorage `selected_users_json`/`user_stats_json` written, reload restores both via
`on_load` **without refetching** (stub counts), widget `/widget/Alice?appearance=dark` (+ reload within
60 s served from the `last_fetch` LocalStorage cache). After the upgrade (same profile) the 0.9.12-written
LocalStorage is restored by 0.10.0a1 without refetch; same in the cold run and in **prod** on the same
origin (`gh-up-prod2`). The `hydrate_and_load` connect payload carries the LocalStorage values
(`shots/gh/gh-up.json`).
Pre-existing (both versions): `rx.text_area(value=…)` without on_change → React "value prop without
onChange" console error; `?appearance=dark` is never applied because `Theme._render` unconditionally
`remove_props("appearance")` (identical code in reflex-components-radix 0.9.10.post1 and 0.10.0a1;
compiled `RadixThemesTheme` gets no appearance) — a framework quirk for nested `rx.theme(appearance=…)`,
not a regression; the app's `fetch_missing_stats` re-queues itself forever while an unknown user is
selected (129 stub fetches in ~5 s; stops when the tab disconnects; "Attempting to send delta to
disconnected client" warnings on 0.9.12 when navigating away) — app bug.
Driver bugs fixed during the run (not product issues): `gh-cold` expected the 0.9.12 user set,
`gh-cold2` matched the WidgetState `user_stats_json` key; `gh-cold3` is the clean rerun.

### clock (rx.Cookie zone, bg tick loop, on_load reset)
Render, stopped on load, switch starts ticking, US/Pacific time correct, switching to Asia/Tokyo applies
while ticking, cookie `reflex___state____state.clock___clock____state.zone_rx_state_=Asia%2FTokyo`, reload
keeps the zone and resets the switch, switch-off stops ticks, fresh context gets the default — identical
on base/up/cold. Note: the app's `rx.switch(is_checked=State.running)` compiles to
`css:{isChecked: …}` (unknown prop treated as style), i.e. the switch is uncontrolled — app bug, both
versions; it matters for the stale-tab reading below.

## Stale tab across the upgrade

* **Dev, clock** (`stale_tab_clock.py`, `shots/ck/ck-stale-dev*`): tab on 0.9.12 (Europe/Paris, ticking);
  server stopped → "Cannot connect to server: websocket error" toast; venv upgraded, 0.10.0a1 started →
  vite reloads the page by itself, the new JS connects with `hydrate_and_load`, zone cookie kept,
  interaction works, manual reload keeps Asia/Tokyo. Expected dev behaviour.
* **Prod, clock** (`clock-prod` copy + venv `upgrades_a-clockprod`, port 3147, `shots/ckprod/`): the old
  0.9.12 bundle stays loaded (marker kept), reconnects to 0.10.0a1, sends the legacy `hydrate`,
  `on_load_internal`, `update_vars_internal` events and gets correct deltas; zone change works; manual
  reload switches to the new JS and keeps the cookie zone. The user sees **no version-mismatch prompt**;
  the backend only logs `Warning: Frontend version 0.9.12 for session … does not match the backend version
  0.10.0a1.` (`logs/ckprod-up.server.log:299`). 0.9.12 has the same warning-only code path
  (`reflex/app.py` on_connect), so this is not a regression. The "switch shows ON but clock frozen"
  state in `ck-stale-prod_C_after_up.png` (and the resulting `D` check fail) is the uncontrolled-switch
  app bug + `on_load` resetting `running` on reconnect, not a version problem.
* **Prod + Redis, github-stats** (`stale_tab_redis_gh.py`, shared `$SB/envs/stable` then `$SB/envs/alpha`,
  app copy `github-stats-redis2`, redis on 8159, `shots/ghredis/ghredis2-stale*`): state pickled by 0.9.12
  in Redis (`username='dave'` typed but not submitted, visible in the pickle) is unpickled by 0.10.0a1 —
  the reconnect hydrate delta carries `"username_rx_state_":"dave"`; the stale tab adds carol through the
  new backend; reload (new JS, same token) restores users, stats and the backend-only `username`; a second
  context with the token injected (after closing the first tab) sees the same Redis state. No unpickle /
  schema warnings. (`ghredis-stale` = first attempt; its F check failed because the original tab still
  held the token, so the newcomer was issued a fresh one — harness design, fixed in v2.) Prod+Redis
  spawns 9 granian workers on this 4-CPU box with granian's "workers higher than CPU cores" warning and
  logs "Page widget/[selected_user_param] is being redefined" once per worker — identical on 0.9.12.

## Additional probes

* **pip-style upgrade = mixed graph** (`form-designer-pip`, venv `upgrades_a-fd-pip`): `pip install -U
  'reflex==0.10.0a1'` → reflex/reflex-base alpha with all 0.9.x components. Compiles, all flows identical
  (`fdpip-mixed-up`, `fdpip-mixed-entry`); package.json keeps moment 2.30.1 and react-error-boundary 6.1.2
  (pinned by the 0.9.x component packages).
* **Full `reflex[db]` alpha graph** (same copy/venv, then `uv pip install --prerelease=allow -U -r
  requirements.txt 'reflex[db]==0.10.0a1'`, `logs/fd-pip-dbextra-upgrade.install.log`): components →
  alphas, pydantic 2.13.5→**2.14.0b2**, sqlmodel 0.0.47→**0.0.44**. form-designer still passes every flow
  (`fdpip-dbextra-up`, `fdpip-dbextra-entry`; responses written under sqlmodel 0.0.47 and 0.0.44 both
  render) because its datetime columns use explicit `sa_column` types — see I-1 for plain `datetime` fields.
* **Venv upgraded under a running dev server** (`counter-live`, venv `upgrades_a-counterlive`,
  `live_tab_counter.py`, `logs/counterlive.server.log`): the upgrade itself is not noticed; the next code
  edit hot-reloads a worker that mixes already-imported 0.9.12 modules with freshly imported 0.10.0a1
  ones → `ImportError: cannot import name 'state_manager_disk_debounce' from 'reflex_base.environment'`,
  `[ERROR] Unexpected exit from worker-1`, `/ping` dead, browser shows "Cannot connect to server" until
  `reflex run` is restarted; every further edit repeats it. Restart → 8/8 (`counterlive-restart`).
* **SQLModel cap** (`sqlmodel_datetime_probe.py`, `logs/sqlmodel-probe.txt`): a plain `datetime` field
  written under sqlmodel 0.0.47 (what 0.9.12 resolves; column type `UTCDateTime()`, naive writes rejected)
  reads back **naive** under sqlmodel 0.0.44 (what `reflex[db]==0.10.0a1` forces; column `DateTime()`):
  `datetime(2026,10,6,17,0)` instead of `…tzinfo=utc`, isoformat loses `+00:00`, comparing with
  `datetime.now(timezone.utc)` raises `TypeError: can't compare offset-naive and offset-aware datetimes`.
  PyPI upload times: sqlmodel 0.0.45 2026-09-21T21:51Z, reflex 0.9.12 2026-09-22T00:53Z.
  form-designer and reflex-local-auth are unaffected (explicit `sa_column=Column(DateTime(timezone=True))`).
* **Timings**: compile 0.01–0.8 s and frontend install 0.17–7 s on every run, no cliff after the upgrade.

## Issues (repro steps)

### I-1 (medium, regression for apps that store tz-aware datetimes) — `reflex[db]` 0.10.0a1's `sqlmodel<0.0.45` cap flips datetime semantics for 0.9.12 upgraders
Every `reflex[db]==0.9.12` install resolved sqlmodel ≥0.0.45 (sqlmodel 0.0.45 was uploaded
2026-09-21T21:51Z, reflex 0.9.12 2026-09-22T00:53Z; this cluster's baseline got 0.0.47). From 0.0.45 a
plain `datetime` field maps to `UTCDateTime` (naive writes rejected, reads return aware UTC). The
0.10.0a1 db extra pins `sqlmodel<0.0.45` (#7424, changelog: "keep SQLModel below 0.0.45 to preserve
existing datetime storage behavior"); for 0.9.12 users that *changes* the behaviour:
```bash
cd $SB && uv --no-config venv --python 3.12 $SB/envs/upgrades_a-x0912 && uv --no-config pip install --python $SB/envs/upgrades_a-x0912/bin/python 'reflex[db]==0.9.12'   # -> sqlmodel 0.0.47
uv --no-config pip install --python $SB/envs/upgrades_a-x0912/bin/python --dry-run --prerelease=allow -U 'reflex[db]==0.10.0a1'           # -> sqlmodel 0.0.47 -> 0.0.44 (and pydantic -> 2.14.0b2)
uv --no-config pip install --python $SB/envs/upgrades_a-x0912/bin/python --dry-run --prerelease=allow -U 'reflex==0.10.0a1'               # -> sqlmodel stays 0.0.47; `uv pip check`/`pip check` say OK
# mechanism (no browser needed): write with 0.0.47, read with 0.0.44
$SB/envs/upgrades_a-x0912/bin/python $W/scripts/sqlmodel_datetime_probe.py /envs/upgrades_a-x0912/ $W/run/p.db write
$SB/envs/alpha/bin/python $W/scripts/sqlmodel_datetime_probe.py /envs/alpha/ $W/run/p.db read
```
Observed (`logs/sqlmodel-probe.txt`): 0.0.47 reads `datetime(2026,10,6,17,0,tzinfo=utc)`; after the
reflex[db] 0.10.0a1 resolution the same row reads `datetime(2026,10,6,17,0)` (naive), `isoformat()` loses
`+00:00`, and `row.at < datetime.now(timezone.utc)` raises `TypeError: can't compare offset-naive and
offset-aware datetimes`. Apps that write naive datetimes go the other way (rejected on 0.9.12 + 0.0.45+,
accepted again after the cap) — that is the population #7424 protects. The outcome after "upgrading"
depends on whether the user re-requests the `[db]` extra, and no checker reports the out-of-range
sqlmodel. Not observable in form-designer itself (its datetime columns use explicit
`sa_column=Column(DateTime(timezone=True))`). Postgres `timestamptz` vs `timestamp` autogenerate drift
after the downgrade is plausible but was NOT tested (no Postgres here).

### I-2 (low, not a regression) — stale frontend after an upgrade gets no user-visible signal
```bash
cd $SB && uv --no-config venv --python 3.12 $SB/envs/upgrades_a-clockprod && uv --no-config pip install --python $SB/envs/upgrades_a-clockprod/bin/python -r $W/clock/requirements.txt 'reflex==0.9.12'
cd $SB/downloads/reflex-examples && tar --exclude=.web -cf - clock | tar -C $W -xf - --transform 's#^clock#clock-prod#'
REFLEX_API_URL=http://localhost:3147 $W/bin/run_app.sh $W/clock-prod $SB/envs/upgrades_a-clockprod 3147 3147 $W/logs/ckprod-base.server.log --env prod
mkdir -p $W/run/stale_ck_prod; NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/stale_tab_clock.py http://localhost:3147/ $W/shots/ckprod ck-stale-prod $W/run/stale_ck_prod &   # wait for run/stale_ck_prod/ready
$W/bin/stop_app.sh $W/clock-prod 3147; touch $W/run/stale_ck_prod/down
cd $SB && uv --no-config pip install --python $SB/envs/upgrades_a-clockprod/bin/python --prerelease=allow -U 'reflex==0.10.0a1'
REFLEX_API_URL=http://localhost:3147 $W/bin/run_app.sh $W/clock-prod $SB/envs/upgrades_a-clockprod 3147 3147 $W/logs/ckprod-up.server.log --env prod; touch $W/run/stale_ck_prod/up
```
The old bundle reconnects, runs the legacy hydrate/on_load/update_vars events against 0.10.0a1 and
keeps working; only `Warning: Frontend version 0.9.12 for session … does not match the backend version
0.10.0a1.` in the server log, no toast/reload prompt (`shots/ckprod/ck-stale-prod_C_after_up.png`).
0.9.12 has the same warning-only path, so this is context, not a blocker. Same with Redis
(`ghredis2-stale`), where the old tab also keeps the 0.9.12-pickled state.

### I-3 (low, not a regression) — upgrading the venv under a running dev server breaks every later hot reload with an opaque ImportError
```bash
cd $SB/downloads/reflex-examples && tar --exclude=.web -cf - counter | tar -C $W -xf - --transform 's#^counter#counter-live#'
cd $SB && uv --no-config venv --python 3.12 $SB/envs/upgrades_a-counterlive && uv --no-config pip install --python $SB/envs/upgrades_a-counterlive/bin/python -r $W/counter-live/requirements.txt 'reflex==0.9.12'
$W/bin/run_app.sh $W/counter-live $SB/envs/upgrades_a-counterlive 3148 8148 $W/logs/counterlive.server.log
cd $SB && uv --no-config pip install --python $SB/envs/upgrades_a-counterlive/bin/python --prerelease=allow -U 'reflex==0.10.0a1'   # while it runs
echo "# edit" >> $W/counter-live/counter/counter.py      # triggers hot reload
```
Log: `ImportError: cannot import name 'state_manager_disk_debounce' from 'reflex_base.environment'`
→ `[ERROR] Unexpected exit from worker-1`; `/ping` stops answering, the page shows "Cannot connect to
server", the CLI and vite keep running; each further edit repeats it; restarting `reflex run` fixes it.
Generic mixed-module hazard (old process, new files on disk); a version check on reload that tells the
user to restart would turn it into a clear message.

### Not issues, recorded for context
* Pre-existing app bugs (identical on 0.9.12): form-designer FormMessage crash / no login redirect /
  responses-page React warnings; github-stats infinite refetch for unknown users and controlled-less
  text_area; clock's `is_checked` (uncontrolled switch).
* Pre-existing framework quirk (identical code in both versions): nested `rx.theme(appearance=…)` drops
  `appearance` (`Theme._render(...).remove_props("appearance")` in reflex-components-radix
  `themes/base.py`), so github-stats' `/widget/<user>?appearance=dark` never turns dark.
* `uv pip install 'reflex==0.10.0a1'` without `--prerelease=allow` fails to resolve (uv semantics for the
  transitive `reflex-base==0.10.0a1` pin); `pip` succeeds but yields the mixed graph above.

## Benign / environment noise seen (not findings)
SitemapPlugin "enabled by default" warning (all apps except form-designer, both versions); `@rx.memo`
without annotations DeprecationWarning (reflexle, both); `RouterData.page` DeprecationWarning
(github-stats widget.py:18, both); bun `incorrect peer dependency "react@19.3.0"` (0.9.12 installs);
`Unable to bind to any port for 10: [Errno 97]` (no IPv6 here); Chromium verbose "Input elements should
have autocomplete attributes"; WebSocket ERR_CONNECTION_REFUSED while a server was intentionally down;
reflexle prod `/favicon.ico` 404 (no favicon in assets); vite HMR/HydrateFallback/React DevTools lines.

## Artifact map
```
NOTES.md                this file
form-designer/ reflexle/ github-stats/ clock/ counter/ traversal/ json-tree/   app sources as run
                        (.web, reflex.lock, .states, *.db, __pycache__ excluded; the copies
                        form-designer-pip, clock-prod, github-stats-redis2, counter-live are plain
                        tar copies of these made by the commands above)
patches/                the two opt-in QA patches (env-var gated, default = upstream)
bin/                    run_app.sh stop_app.sh ports.sh seq_misc.sh
scripts/                drivers, harness, stub, probes (see table above)
freeze/                 uv pip freeze per app base/up, diffs, dry-runs, pip report
pkg/                    .web/package.json per app base/up/cold, diffs, reflex.lock listings, .web file lists
logs/                   server logs (all runs), driver logs, db dumps, migrate/makemigrations output,
                        sqlmodel probe output
shots/<app>/            <tag>.json (checks + console + network + ws frames) and selected screenshots
```

## VERIFICATION

Independent verifier `verify_upgrades_a_0`, 2026-10-06. Scope: I-1 in full, plus a sanity check of I-3 (does a restart
fully resolve it, and is the resulting state sane). Every venv is fresh from PyPI (`uv 0.11.32 --no-config`, cwd=`$SB`,
Python 3.12.3) under `$SB/envs/verify_upgrades_a_0-*`. Work dir `$SB/apps/verify_upgrades_a_0/`, ports 3640/8640 (apps)
and 8643 (a private PostgreSQL 16 cluster). Artifacts: `verification/sqlmodel-datetime/` (scripts, logs, shots, `dtapp/`
source including its generated alembic migration) and `verification/hot-reload-after-upgrade/`.

### I-1: the written repro reproduces exactly

`logs/explorer-probe-rerun.txt` runs `scripts/sqlmodel_datetime_probe.py` verbatim. It writes with a fresh
`reflex[db]==0.9.12` venv and reads with both the shared `$SB/envs/alpha` and a fresh alpha venv. The output is identical to
`logs/sqlmodel-probe.txt`: 0.0.47 reads `tzinfo=utc`, 0.0.44 reads naive, and comparing against an aware now raises
`TypeError`.

**Resolution today** (`logs/venv-*.install.log`):

| command (fresh venv unless noted) | sqlmodel / pydantic |
|---|---|
| `uv pip install 'reflex[db]==0.9.12'` | **0.0.47** / 2.13.5 |
| `uv pip install --prerelease=allow 'reflex[db]==0.10.0a1'` | **0.0.44** / 2.14.0b2 |
| `uv pip install 'reflex[db]==0.10.0a1'` (no flag) | fails: `reflex-base==0.10.0a1` pre-release not enabled |
| `pip install 'reflex[db]==0.10.0a1'` (pip 26.2.1, no `--pre`) | **0.0.44** / 2.13.5 (reflex and reflex-base on the alpha, components on 0.9.x) |
| `pip install --pre 'reflex[db]==0.10.0a1'` | **0.0.44** / 2.14.0b2 |
| from a pip `reflex[db]==0.9.12` env: `pip install [-U] 'reflex[db]==0.10.0a1'`, or uv `--prerelease=allow 'reflex[db]==0.10.0a1'` | 0.0.47 → **0.0.44** |
| from that env: `pip install -U 'reflex==0.10.0a1'` or uv `--prerelease=allow -U 'reflex==0.10.0a1'` (no extra) | stays 0.0.47 |
| simulated pre-2026-09-21 env (`reflex[db]==0.9.11` + sqlmodel 0.0.44): `pip install -U 'reflex[db]==0.9.12'`, `pip install -U 'reflex[db]'`, `uv pip install 'reflex[db]==0.9.12'` | **stays 0.0.44** (pip's only-if-needed strategy; uv without `-U`) |
| same env: `uv pip install -U 'reflex[db]==0.9.12'` | 0.0.44 → 0.0.47 |
| `uv pip compile`: `reflex[db]==0.10.0a1` + `sqlmodel>=0.0.45` | unsatisfiable |
| `uv pip compile`: `reflex==0.10.0a1` + `reflex-local-auth` + `sqlmodel>=0.0.45` | resolves, but silently picks **reflex-local-auth 0.4.0**, the last release that does not require `reflex[db]` |

`pip check` and `uv pip check` both report OK for reflex 0.10.0a1 + sqlmodel 0.0.47 + reflex-local-auth 0.5.0 (which
requires `reflex[db]>=0.8.1`), so no checker catches the out-of-range sqlmodel. PyPI upload times: sqlmodel 0.0.44
2026-09-21T16:02Z, **0.0.45 21:51Z**, 0.0.46 2026-09-22T09:38Z, 0.0.47 2026-09-23T17:31Z; reflex 0.9.12a2
2026-09-21T21:20Z, **0.9.12 2026-09-22T00:53Z**. Published metadata: `reflex-0.9.12.dist-info/METADATA:52`
`sqlmodel<0.1,>=0.0.24; extra == 'db'`; `reflex-0.10.0a1.dist-info/METADATA:52` `sqlmodel<0.0.45,>=0.0.24; extra == 'db'`.
The `v0.9.12` tag's `uv.lock` holds sqlmodel 0.0.39 (7-day `exclude-newer`), so 0.9.12 was never CI-tested on ≥0.0.45.

Correction to the claim: "every `reflex[db]==0.9.12` install resolved ≥0.0.45" holds for every **fresh** resolution
(new venvs, Docker or CI builds without a lockfile, `uv pip install -U`). It does not hold for pip in-place upgrades,
`uv pip install` without `-U`, or locked projects; those kept ≤0.0.44.

**What sqlmodel 0.0.45 changed** (diff of the installed wheels, `logs/sqlmodel-0.0.44-vs-0.0.47.diff`; GitHub access
to fastapi/sqlmodel and its docs site are blocked here):
- 0.0.44 `sqlmodel/main.py:757` maps `datetime` to `DateTime`.
- 0.0.47 `main.py:757-760` maps `datetime` and `AwareDatetime` to the new `UTCDateTime()`, and `NaiveDatetime` to
  `DateTime(timezone=False)`.
- `UTCDateTime` (`sqlmodel/sql/sqltypes.py:9-49`) has `impl=DateTime(timezone=True)`. It raises `ValueError` on naive bind
  values, which covers WHERE clauses too. It converts aware values to UTC on write and attaches UTC to tz-less DB values
  on read.
- The SKILL.md bundled in the wheel documents this and points to sqlmodel's datetime upgrade guide.

**PR #7424** (GitHub MCP): "Lock SQLModel to 0.0.44 and cap it below 0.0.45. The newer default UTC storage rejects
existing naive datetime values; the existing migration test reproduced the break." The fragment type is `misc`. The
pyproject comment reads "Keep naive datetime defaults working until a compatibility path is available." Nothing
discusses environments where 0.9.12 already resolved ≥0.0.45.

**SQLite matrix** (`scripts/dt_matrix_probe.py`, `logs/dt-matrix.txt`, `logs/dt-alone-*.txt`). Three tables:
SQLModel `at: datetime`, `rx.Model` `created_at: datetime`, and `rx.Model` with
`sa_column=Column(DateTime(timezone=True))`. Three written values: aware 17:00Z, aware 19:00+02:00 (the same instant),
and naive 17:00. Both directions were run (A: 0.9.12 writes, alpha reads and writes, 0.9.12 re-reads; B: the reverse),
plus each version alone:

| column | write under 0.0.47 | write under 0.0.44 | read under 0.0.47 | read under 0.0.44 |
|---|---|---|---|---|
| plain `datetime` (SQLModel or `rx.Model`, identical) | naive **rejected** (`StatementError ... must have timezone information`); aware stored as UTC | everything accepted; **aware +02:00 stored as wall clock `19:00`** (offset dropped) | **aware** UTC (a 0.0.44-written +02 row reads `19:00+00:00`, 2 h wrong) | **naive** |
| `sa_column=Column(DateTime(timezone=True))` | everything accepted, +02 stored as `19:00` | same | naive | naive |

- Stored bytes: SQLite TEXT `'2026-10-06 17:00:00.000000'` is byte-identical for UTC-instant values whichever version
  wrote them. The only difference is aware non-UTC input: 0.0.47 normalizes it to `17:00`, 0.0.44 writes `19:00`.
- Comparisons: values read under 0.0.47 compare with an aware now but raise `TypeError` against a naive now; 0.0.44 is
  the reverse.
- Filters: `where(col > naive)` raises under 0.0.47 and is accepted under 0.0.44.
- Frontend: reflex serializes with `str(dt)` (`reflex_base/utils/serializers.py:450`), so `+00:00` disappears under
  0.0.44.
- Isolation: reflex 0.9.12 + sqlmodel 0.0.44 matches 0.10.0a1 + 0.0.44 exactly, and 0.10.0a1 + 0.0.47 matches
  0.9.12 + 0.0.47. pydantic 2.13.5 vs 2.14.0b2 makes no difference. **The behavior depends only on the sqlmodel version;
  the alpha's sole contribution is the cap that forces 0.0.44.**

**PostgreSQL 16** (private cluster, `scripts/dt_matrix_probe_pg.py`, `logs/dt-matrix-postgres.txt`). Tables created
under 0.0.47 are `timestamp with time zone`. After the downgrade, psycopg2 still returns **aware** values: `+00:00` with
the server-default UTC session, `13:00-04:00` with session TZ America/New_York. Comparisons with an aware now keep
working, and naive writes are accepted again (interpreted in the session TZ). **The claimed naive-read flip is
SQLite-only (and presumably MySQL); on Postgres it does not happen for tables created under 0.9.12.** Tables created
under 0.0.44 are `timestamp without time zone`, which read naive under 0.0.44 and aware under 0.0.47.

**Real app, in-place upgrade, Chromium in America/New_York** (`dtapp/`, `scripts/drive_dtapp.py`, `shots/dt-*`,
`logs/dtapp-*`). The model is `Post(rx.Model)` with `created_at: datetime`. `on_load=State.load` computes
`datetime.now(timezone.utc) - p.created_at`, and there are Add aware and Add naive buttons.
- **0.9.12 + 0.0.47** (`dt-0912c`): rows render as `2026-10-06 18:00:59.471870+00:00` and `rx.moment` shows
  `14:00 -04:00`. Add aware works. **Add naive raises a toast "StatementError: (builtins.ValueError) Datetime values must
  have timezone information…" and no row is written.** That is the breakage the cap removes for naive-datetime code.
- **Upgrade:** `uv pip install --prerelease=allow -U 'reflex[db]==0.10.0a1'` (0.0.47 → 0.0.44). In place,
  `reflex db migrate` and `reflex db makemigrations` both exit 0 as no-ops; reflex autogenerate passes
  `compare_type=False` (`reflex/model.py:448`).
- **0.10.0a1 + 0.0.44** (`dt-a1-inplace`): page load raises a toast "TypeError: can't subtract offset-naive and
  offset-aware datetimes" and the list is empty. Every Add shows the same toast, although the rows are persisted. There
  are 4 tracebacks in `logs/dtapp-a1-run.server.log`.
- **Display** (`dt-a1-inplace-display`, with `load` reordered so the rows still render; see
  `dtapp/load-order-change.diff`; on 0.0.47 nothing raises, so the order is irrelevant there): the same row now shows
  `2026-10-06 18:00:59.471870` and `rx.moment` shows `18:00 -04:00`. **Every displayed timestamp shifts by the viewer's
  UTC offset** (4 h in New York).

**Hard breaks the original report missed** (they don't depend on the database):
1. **Migrations.** `reflex db init` on 0.9.12 + 0.0.47 generated `alembic/versions/9b68327541da_.py` containing
   `sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False)`. After upgrading to
   `reflex[db]==0.10.0a1`, `reflex db migrate` on a **fresh database** (new deploy, CI, a teammate's clone) fails with
   `AttributeError: module 'sqlmodel.sql.sqltypes' has no attribute 'UTCDateTime'` (rc 1), leaving only an empty
   `alembic_version` table (`logs/dtapp-a1-db-migrate-freshdb.log`). Controls on the same copy: 0.9.12 + 0.0.47 rc 0;
   0.10.0a1 + 0.0.47 rc 0; 0.9.12 + 0.0.44 rc 1.
2. **Model declarations that sqlmodel ≥0.0.45 documents** (`scripts/sqlmodel_guidance_probe.py`,
   `logs/sqlmodel-guidance-probe.txt`). Under 0.0.44, `at: AwareDatetime` and `at: NaiveDatetime` raise
   `ValueError: <class 'pydantic.types.AwareDatetime'> has no matching SQLAlchemy type` at class creation, and
   `from sqlmodel import UTCDateTime` raises `ImportError`, so the app no longer imports. Only `sa_type=` or `sa_column=`
   with an explicit `DateTime(...)` works on both versions.

**Populations.**
- **Protected by the cap:** code written for naive datetimes (`datetime.now()`, `utcnow()`, naive filters), i.e.
  reflex[db]'s whole pre-2026-09-21 history. On 0.9.12 that code breaks at its next fresh resolution, as `dt-0912c`
  shows.
- **Broken by the cap:** environments that resolved ≥0.0.45 under 0.9.12 and rely on it:
  - on SQLite: TypeErrors in handlers, lost `+00:00`, displays shifted by the viewer's offset, and aware non-UTC writes
    silently stored as wall clock;
  - on any database: migrations rendered with `UTCDateTime()` fail on a fresh DB, and `AwareDatetime`/`NaiveDatetime`/
    `UTCDateTime` declarations fail to import.

  These users cannot keep `reflex[db]` and opt out of the cap: the resolution is unsatisfiable, or reflex-local-auth
  silently drops to 0.4.0.
- **Unaffected either way:** the canonical reflex-examples (`form-designer`, `basic_crud`), which use explicit
  `sa_column=Column(DateTime(timezone=True))`.

**Decision: (b), with action required before 0.10.0 final.** The cap is a deliberate, documented, defensible choice,
not a coding defect. It restores the semantics reflex[db] always had and that 0.9.12's CI tested. However:
- the changelog's "preserve existing datetime storage behavior" is wrong for every environment that resolved
  `reflex[db]==0.9.12` fresh;
- the fragment is filed as `misc`, not `breaking`;
- the hard failures above need at least a documented recipe. For example: replace `sqlmodel.sql.sqltypes.UTCDateTime()`
  in migrations with `sa.DateTime(timezone=True)`; replace `AwareDatetime`/`NaiveDatetime` columns with
  `sa_type=DateTime(...)`; or drop `[db]` and depend on `sqlmodel>=0.0.45` directly.

Severity medium: alpha only, limited to db-extra users with plain `datetime` fields whose environment resolved ≥0.0.45,
and a workaround exists. It is a regression for that population.

**Side observation (not triaged).** In `shots/dt-a1-inplace-display.json`, when a chained handler raises
(`add_aware` → `return State.load` → TypeError), the partial `posts` delta is not delivered with that event's error
toast. It arrives with the next event's delta (frames at t=20.18 vs 23.92). The same failure inside the initial
`on_load` does deliver it (t=1.35). Worth a separate look at exception-path delta flushing.

### I-3 sanity check (`verification/hot-reload-after-upgrade/`)

Repro as written, using a counter copy, venv `verify_upgrades_a_0-counterlive`, ports 3640/8640:
- **Baseline:** 0.9.12 drive 8/8.
- **Upgrade under the running server:** `uv pip install --prerelease=allow -U 'reflex==0.10.0a1'`. `/ping` stays 200
  until the next edit.
- **Edit 1:** the granian worker, forked from the 0.9.12 CLI, imports the 0.10.0a1 file
  `reflex/istate/manager/disk.py:14`. Its `from reflex_base.environment import state_manager_disk_debounce` runs
  against the already-loaded 0.9.12 module, so it fails with `ImportError`, followed by
  `[ERROR] Unexpected exit from worker-1`, and `/ping` returns 000. Edit 2 repeats it. **Reproduced.**
- **Restart:** stopping needed SIGTERM then kill on the 0.9.12 CLI, its known shutdown behavior. The new server was UP
  in 6 s: lockfiles restored, frozen install, then `bun add` to the new pins. Drive 8/8 (`i3-counter-after-restart`).
  Edit 3 hot-reloads cleanly (`/ping` 200, cached frontend install).
- **State after restart:**
  - `.web/package.json` is JSON-identical to the explorer's cold 0.10.0a1 build (`pkg/counter-cold.web.package.json`);
  - `reflex.lock/{package.json,bun.lock}` is byte-identical to `.web/`;
  - `.web/reflex.json` reports `0.10.0a1`;
  - the `.web` file set equals the cold build's, plus react-router dev typegen files written by the new server.

**Restart fully resolves it and leaves no stale state.** The crash happens inside the old CLI's process, so 0.10.0a1
cannot prevent it for this transition. It is not a regression.

### Cleanup

The dtapp servers (0.9.12 and 0.10.0a1), the counter-live servers (0.9.12 and after restart), the private Postgres,
and every Chromium instance are stopped. `lsof` shows ports 3640-3643 and 8640-8643 free.
