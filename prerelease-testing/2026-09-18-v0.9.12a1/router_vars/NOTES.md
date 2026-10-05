# Cluster `router_vars` — reflex 0.9.12a1 pre-release QA

Covers the router split into per-field base vars (**#7068**), inherited-var shadowing errors
(**#7077**) and reserved-name validation (**#7136**). Everything below was produced with
packages installed from PyPI only; the `/home/user/reflex` checkout was never installed or used
as a working directory.

## Resolved versions

`uv pip freeze | grep reflex` for the **new** env (`$SB/envs/shared`, python 3.11):

```
reflex==0.9.12a1                      reflex-components-markdown==0.9.4a1
reflex-base==0.9.12a1                 reflex-components-moment==0.9.4
reflex-components-code==0.9.6a1       reflex-components-plotly==0.9.7a1
reflex-components-core==0.9.10a1      reflex-components-radix==0.9.10a1
reflex-components-dataeditor==0.9.3a1 reflex-components-react-player==0.9.2
reflex-components-gridjs==0.9.2a1     reflex-components-recharts==0.9.4a1
reflex-components-lucide==1.0.4       reflex-components-sonner==0.9.4a1
                                      reflex-hosting-cli==0.1.72
```

Baseline env (`$SB/envs/prev`): `reflex==0.9.11.post1`, `reflex-base==0.9.11.post1`,
`reflex-components-core==0.9.9`, `-radix==0.9.9`, `-code==0.9.5`, `-dataeditor==0.9.2`,
`-gridjs==0.9.1`, `-markdown==0.9.3`, `-plotly==0.9.6`, `-recharts==0.9.3`, `-sonner==0.9.3`.

Driver env (`$SB/envs/driver`): playwright 1.63, chromium at `/opt/pw-browsers/chromium`.

## How to rerun from scratch

```bash
SB=/tmp/rv                         # any neutral dir OUTSIDE /home/user/reflex
mkdir -p $SB && cd $SB

# new env
uv venv $SB/envs/shared --python 3.11
uv pip install --python $SB/envs/shared/bin/python --prerelease=allow \
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
  'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
  'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
  'reflex-components-sonner==0.9.4a1' redis

# baseline env
uv venv $SB/envs/prev --python 3.11
uv pip install --python $SB/envs/prev/bin/python 'reflex==0.9.11.post1'

# driver env
uv venv $SB/envs/driver --python 3.11
uv pip install --python $SB/envs/driver/bin/python playwright httpx websockets

cp -r <this dir>/routerlab <this dir>/scripts $SB/
```

### 1. Compile-time / negative cases (no server needed)

```bash
cd $SB && $SB/envs/shared/bin/python scripts/negative_cases.py   # 0.9.12a1
cd $SB && $SB/envs/prev/bin/python   scripts/negative_cases.py   # 0.9.11.post1 baseline
cd $SB && $SB/envs/shared/bin/python scripts/deps_probe.py       # computed-var dep granularity
cd $SB && $SB/envs/shared/bin/python scripts/deps_legacy.py      # legacy deps=["router"] expansion
cd $SB && $SB/envs/shared/bin/python scripts/backend_shadow.py   # backend-var shadow gap
cd $SB && $SB/envs/shared/bin/python scripts/keyerror_repro.py   # real class stmts (no type() artifact)
```

Recorded output: `logs/negative_new.txt`, `logs/negative_prev.txt`.

> Caveat for whoever rereads `negative_cases.py`: cases constructed with `type(name, bases, ns)`
> report `KeyError: '__module__'` for *unreserved* names on both versions — that is an artifact of
> the three-arg `type()` call, not framework behaviour. `scripts/keyerror_repro.py` re-runs the
> interesting names with real `class` statements and shows `process` / `json` are simply not
> reserved in 0.9.12a1 (neither exists on `BaseState` any more). Only the `StateValueError` /
> `EventHandlerShadowsBuiltInStateMethodError` / `BaseVarShadowsInheritedVarError` rows are real.

### 2. Dev server + browser matrix

```bash
cd $SB/routerlab
REFLEX_TELEMETRY_ENABLED=false $SB/envs/shared/bin/reflex run \
    --frontend-port 3100 --backend-port 8100 --loglevel debug > $SB/dev.log 2>&1 &
# poll http://localhost:3100/ for 200 (first run does a bun install, 1-2 min)
cd $SB && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python scripts/drive_router.py http://localhost:3100 $SB/out_dev
$SB/envs/driver/bin/python scripts/analyze_frames.py $SB/out_dev/ws_frames.txt
```

`drive_router.py` runs 24 labelled steps (load / client-side nav / dynamic-arg change / catch-all /
query / back / forward / reload / direct load with query+fragment / redirect / on_load redirect /
event chain / second tab / second browser context / background task / ComponentState click /
client_state set) and records, per step: every `/_event` websocket frame, which
`rx_router_*` keys appear in the delta and the frame byte size, the rendered value of every
computed var, plus console messages, page errors and >=400 responses.

### 3. Baseline (0.9.11.post1)

```bash
cp -r $SB/routerlab $SB/routerlab_prev && rm -rf $SB/routerlab_prev/.web
cd $SB/routerlab_prev
REFLEX_TELEMETRY_ENABLED=false REFLEX_REDIS_URL=redis://localhost:8115 \
  $SB/envs/prev/bin/reflex run --frontend-port 3101 --backend-port 8101 &
cd $SB && $SB/envs/driver/bin/python scripts/drive_router.py http://localhost:3101 $SB/out_prev
```

The **identical app source imports and runs unchanged on both versions** — no source-level
breakage from #7068/#7077/#7136 for this app.

### 4. Redis persistence + upgrade path

```bash
redis-server --port 8115 --save '' --daemonize yes --dir /tmp
# (a) populate with 0.9.11.post1 as in step 3, then stop that server
# (b) start 0.9.12a1 against the SAME redis
cd $SB/routerlab
REFLEX_TELEMETRY_ENABLED=false REFLEX_REDIS_URL=redis://localhost:8115 \
  $SB/envs/shared/bin/reflex run --frontend-port 3100 --backend-port 8100 --loglevel debug &
TOK=$(redis-cli -p 8115 keys '*_reflex___state____state' | head -1 | sed 's/_reflex.*//')
cd $SB && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python scripts/redis_upgrade.py http://localhost:3100 "$TOK" $SB/out_dev
```

`redis_upgrade.py` loads the app once, discovers the client token in `sessionStorage["token"]`,
overwrites it with a token whose state was pickled by 0.9.11.post1, and reloads.

### 5. Prod mode + disk state manager

```bash
cd $SB/routerlab && rm -rf .states
REFLEX_TELEMETRY_ENABLED=false REFLEX_STATE_MANAGER_MODE=disk \
  $SB/envs/shared/bin/reflex run --env prod --frontend-port 3102 --backend-port 3102 &
cd $SB && $SB/envs/driver/bin/python scripts/drive_router.py http://localhost:3102 $SB/out_prod
```

### 6. Reconnect

```bash
cd $SB && $SB/envs/driver/bin/python scripts/reconnect.py http://localhost:3100 $SB/out_dev
```

## What was verified to work

**Every dependency form re-evaluates on every form of navigation**, in dev *and* prod, with the
memory, redis and disk state managers:

| form | in the app | result |
|---|---|---|
| auto-dep via `self.router.url.path` | `State.cv_auto_path` | reactive |
| `deps=[State.router]` | `State.cv_deps_whole_router` | reactive (all five fields) |
| `deps=[State.router.url]` | `State.cv_deps_router_url` | reactive |
| legacy `deps=["router"]` | `State.cv_deps_legacy_string` | reactive — expands to all five + `router` |
| `self.router.headers.*` | `State.cv_headers` | correct |
| `self.router.session.client_ip/client_token/session_id` | `State.cv_session` | correct |
| deprecated `self.router.page.params` | `State.cv_page_params` | correct, incl. catch-all list |
| `self.router.url.query_parameters` | `State.cv_query_params` | correct |
| `self.router.url.fragment` | `State.cv_frag` | correct (`#frag` on direct load) |
| substate computed var + handler reading `self.router` | `SubState.sub_cv` / `read_router` | correct |
| `rx.ComponentState` render using `State.router.url.path` | `RouterComponentState` | correct, 5 instances |
| `@rx.memo` fed `State.router.url.path` as a prop | `memo_path(...)` | correct |
| whole-router render `rx.code(State.router.to_string())` | `#whole_router` | still emits the pre-split object literal |
| `rx.cond(State.router.url.path == "/", ...)` / `rx.match(State.router.route_id, ...)` | `#cond_out` / `#match_out` | correct |
| `rx._x.client_state` set from `State.router.url.path` | `#cs_value` | correct |
| background task (`@rx.event(background=True)`) reading the router | `bg_read_router` | correct |
| `on_load` reading `self.router.page.params["id"]` + `rx.redirect` | `ItemState.on_load_item` | correct |
| event chain `yield`/return list + `rx.redirect` | `chain_then_nav` | correct |
| `State.router.session.client_token` straight into a component prop | `#direct_token` | correct |

Navigation-delta matrix — measured, **matches PR #7068's table exactly**, identical in dev and prod:

| event | `rx_router_*` keys in the delta |
|---|---|
| first event on a connection (load / reload / direct load / new tab / new context) | all five |
| client-side nav to a different route | `page`, `url`, `route_id` |
| nav within the same dynamic route (different `id`) | `page`, `url` |
| event with no route change (bump, substate handler, background task, ComponentState click) | none |
| `rx.redirect` from a handler / on_load | `page`, `url`, `route_id` |
| browser back / forward | same as the nav they reproduce |

Perf claim verified end-to-end (full websocket frame, same app, same steps, dev mode):

| step | 0.9.11.post1 | 0.9.12a1 | delta |
|---|---|---|---|
| nav to different route (`/items/1`) | 2535 B | 1334 B | **−47%** |
| nav within same route (`/items/2`) | 2535 B | 1289 B | **−49%** |
| nav to catch-all (`/docs/a/b`) | 2624 B | 1423 B | −46% |
| nav to `/search?q=hello` | 2567 B | 1366 B | −47% |
| redirect to `/about` | 2468 B | 1267 B | −49% |
| event with no route change | 112 B | 112 B | 0% |
| initial hydrate | 3408 B | 3483 B | +2% (five keys instead of one) |

Router-var portion of the 0.9.12a1 navigation delta is 426–505 B (vs the whole `router` object on
0.9.11). Raw numbers in `logs/matrix_dev.txt`, `logs/drive_dev.log`, `logs/drive_prev.log`.

**URL is persisted once, not as parsed pieces** (#7068 claim) — confirmed for both back ends:
* redis (`redis-cli --no-raw get <token>_reflex___state____state`): the root pickle contains
  `_url_data_from_href` + the href string, and **no** `scheme` / `netloc` / `query_parameters` /
  `fragment` entries for `rx_router_url`.
* disk (`.states/<hash>.pkl`, `REFLEX_STATE_MANAGER_MODE=disk`): same — one
  `_url_data_from_href` + `http://localhost:3102/items/1`.

**Upgrade from 0.9.11.post1 over the same redis is graceful** — states pickled by 0.9.11 are
discarded silently by the schema check, a fresh state is created (`counter` back to `0`), the page
renders correctly, navigation and events work, and there is **no traceback in the server log, no
browser console error, no page error and no failed request**. Evidence:
`shots/dev_redis_upgrade.png`, `shots/dev_redis_upgrade_after_nav.png`,
`logs/dev_redis_server.log`.

**Shadowing now errors clearly** (#7077/#7136). `logs/negative_prev.txt` vs `logs/negative_new.txt`:

| declaration | 0.9.11.post1 | 0.9.12a1 |
|---|---|---|
| substate `rx_router_url: str` (and `_session`/`_headers`/`_page`/`_route_id`) | silently accepted | `BaseVarShadowsInheritedVarError: The var \`rx_router_url\` in ...C1 shadows a var inherited from ...P1; use a different name instead` |
| substate base var named `router` | silently accepted | `StateValueError: State name \`router\` is reserved by BaseState; use a different name instead.` |
| substate shadows parent base var (issue #7074 repro, `x: int` → `x: str`) | silently accepted, `Child.x` was a raw `int` | `BaseVarShadowsInheritedVarError` |
| same-type/default shadow (`count: int = 0` in both) | silently accepted | `BaseVarShadowsInheritedVarError` |
| grandchild shadows grandparent var | silently accepted | `BaseVarShadowsInheritedVarError` |
| substate shadows root `is_hydrated` | silently accepted | `BaseVarShadowsInheritedVarError` (names `reflex.state.State`) |
| computed var named `router` | `ComputedVarShadowsBaseVarsError` | `StateValueError` (reserved name) |
| state var named `dirty_vars`/`get_delta`/`router_data`/`parent_state`/`substates`/`get_value`/`dict`/`set`/`get_fields`/`setvar`/`reset`/`get_name`/`_get_was_touched`/`_update_was_touched` | crash with `KeyError: '__module__'` | `StateValueError: State name \`X\` is reserved by BaseState; use a different name instead.` |
| event handler named `dirty_vars`/`get_delta`/`set`/`dict`/`reset`/`setvar` | crash with `KeyError: '__module__'` | `EventHandlerShadowsBuiltInStateMethodError: The event handler name \`X\` shadows a builtin State method; use a different name instead` |
| dynamic route arg `[router]` | `DynamicRouteArgShadowsStateVarError` | `StateValueError` (reserved name) |

All the new messages name the offending member, both classes where relevant, and say "use a
different name instead" — a user can act on them without reading framework source.

Browser hygiene: **zero console errors, zero page errors, zero >=400 responses in dev**
(24-step run, two contexts, three tabs). Prod had four 404s, see anomalies below.

## Issues found

### 1. The documented `deps=["router"]` deprecation warning never fires (low)

Changelog: *"Declaring a computed var dependency on the `router` var (`deps=["router"]`) is
deprecated"*; PR #7068: *"An explicit legacy `deps=["router"]` is expanded to all five with a
`console.deprecate()` warning (deprecated 0.9.12, removal 1.0)"*.

In `reflex/state.py:1205-1219` the `console.deprecate()` call is guarded by
`if dvar_set.isdisjoint(constants.ROUTER_VARS):`, but by the time `_init_var_dependency_dicts`
sees it, the string dep `"router"` has already resolved through the `router` switchboard Var and
carries all five `rx_router_*` names, so the set is never disjoint and the branch is dead.

Repro (`scripts/deps_legacy.py`):

```
cd $SB && $SB/envs/shared/bin/python scripts/deps_legacy.py
```

Expected: one `DeprecationWarning` naming `ComputedVar deps=["router"] on S.legacy`.
Observed: no warning; deps print as
`{'rx_router_route_id', 'rx_router_page', 'rx_router_session', 'rx_router_url', 'router', 'rx_router_headers'}`.

The same holds in a real app: `routerlab` declares `cv_deps_legacy_string` with
`deps=["router"]` and neither `reflex run` nor a bare import prints the warning (the *other*
deprecations — `@rx.memo` without annotations, `RouterData.page` — do print, so warnings are not
being suppressed). Consequence: nobody is told to migrate before the 1.0 removal.

**Not a regression** (the deprecation is new in this release); baseline checked for context —
0.9.11.post1 has no such warning at all.

### 2. Any computed var touching the router is invalidated by *all five* router fields (low, perf)

`scripts/deps_probe.py` output on 0.9.12a1:

```
only_session       -> ['rx_router_headers','rx_router_page','rx_router_route_id','rx_router_session','rx_router_url']
only_headers       -> ['rx_router_headers','rx_router_page','rx_router_route_id','rx_router_session','rx_router_url']
only_path          -> ['rx_router_headers','rx_router_page','rx_router_route_id','rx_router_session','rx_router_url']
explicit_session   -> root: ['rx_router_session']   + substate: (all five)
explicit_url       -> root: ['rx_router_url']       + substate: (all five)
```

The auto-dep walk through the `router` property getter always yields the whole set, and it is not
suppressed by an explicit narrow `deps=` (`cv._auto_deps` stays `True`). Net effect observed in
the delta: on every navigation the app re-sends `cv_headers` and `cv_session` — computed vars that
depend only on `rx_router_headers` / `rx_router_session`, neither of which changed. In `routerlab`
that is ~10 computed vars re-sent per navigation, which is why the whole-frame saving is −47%
rather than the −67% PR #7068 measured for the router payload alone.

Two sub-observations worth a look:
* the explicit-dep rows are attributed to two different states, and the substate entry credits the
  substate with owning `rx_router_*` fields that live on the root state
  (`reflex___state____state.__main_____s -> ['rx_router_headers', ...]`). Functionally fine (the
  defining-state walk in `_init_var_dependency_dicts` resolves it), but it means a narrow
  `deps=[State.router.url]` cannot actually narrow anything while the body reads `self.router`.
* nothing in the changelog promises per-field computed-var invalidation, so this is a missed
  opportunity rather than a broken promise. Recording it because the headline perf number in the
  PR is not what a realistic app sees on the wire.

Behaviour is correct throughout; this is a perf/precision note, **not a regression**
(0.9.11.post1 had one `router` var so every router-reading computed var was invalidated anyway).

### 3. Shadowing a parent's *backend* var is still silently ignored (low)

`scripts/backend_shadow.py`:

```python
class P(rx.State):
    _priv: int = 1
class C(P):
    _priv: str = "shadow"     # no error on 0.9.12a1
```

Output: `C.backend_vars` is `{'_reflex_internal_links': None, '_priv': 1}` — the child's
declaration is discarded and reads resolve to the parent's `int`, exactly the #7074 failure mode
that #7077 fixed for *base* vars. The changelog sentence ("Declaring a substate var that shadows a
var inherited from a parent state now raises `BaseVarShadowsInheritedVarError`") reads as though it
covers this. **Not a regression** — 0.9.11.post1 behaves identically (`logs/negative_prev.txt`,
row `substate shadows a parent BACKEND var`). A gap in the new guard, worth either fixing or
wording the changelog around.

## Anomalies (benign but surprising)

### A. Prod mode: two 404s for direct loads of dynamic routes

In `--env prod`, `GET /items/7?x=1` and `GET /items/redirectme` return **404** (visible in the
console as "Failed to load resource: 404" and in the network log), yet the page then renders
correctly with the right params. Related: a reload in prod rewrites `/search?q=hello` to
`/search/?q=hello` (trailing slash), and `self.router.url.path` consequently reads `/search/`
instead of `/search` — a router-visible difference between dev and prod that an app doing
`router.url.path == "/search"` would trip over.

Evidence: `logs/drive_prod.log` (BAD RESPONSES section), `out_prod/records.json` step
`13_reload_on_search`, `shots/prod_16_item7.png`.
**Baseline NOT checked** — I did not build a 0.9.11.post1 prod bundle (time). This looks like the
pre-existing static-export + trailing-slash behaviour rather than anything #7068 introduced, but
somebody should confirm before dismissing it.

### B. `reflex run --env prod` logs "Page X is being redefined with the same component"

Four such warnings (`items/[id]`, `docs/[[...splat]]`, `search`, `about`) on every prod start;
dev does not print them. The app uses `@rx.page(route=...)` decorators plus one
`app.add_page(index, route="/")`. Harmless (same component), but noisy and unexplained.
Evidence: `logs/prod_server.log`. **Baseline not checked.**

### C. Reconnect test inconclusive

`scripts/reconnect.py` toggles `context.set_offline(True/False)` for 4 s to try to force a
socket.io reconnect and observe the "reconnect → only `rx_router_session`" row of the PR table.
No reconnect frames were captured — socket.io's `pingTimeout` is 120 s, so a 4 s outage does not
drop the connection. State survived intact (counter preserved, then incremented), and the
subsequent navigation produced the normal `page`/`url`/`route_id` delta with no errors, so nothing
is broken; the specific "session-only on reconnect" claim is simply **unverified**. To verify
properly, restart the backend with the tab open (needs `--backend-only` plus a separately served
frontend) or stub the socket.io ping timeout.

### D. Custom request headers do not reach `router.headers` from Playwright

`browser.new_context(extra_http_headers={"x-rxtest": "CTX-ONE"})` does not put `x-rxtest` into
`self.router.headers.raw_headers` — `cv_headers` reads `xtest=MISSING` in every run. The captured
`rx_router_headers` payload is the **websocket handshake** header set
(`host: localhost:8100`, `upgrade: websocket`, `sec-websocket-*`, …), and Chromium does not apply
`extra_http_headers` to websocket handshakes. So this is a **test-harness limitation, not a reflex
bug**, and the "change the header for a new context / confirm the connect-time cache is
per-connection" sub-test could not be run this way. `HeaderData.raw_headers` does still exist
(fields: host, origin, upgrade, connection, cookie, pragma, cache_control, user_agent,
sec_websocket_version, sec_websocket_key, sec_websocket_extensions, accept_encoding,
accept_language, raw_headers). The mutation-isolation half was still exercised: clicking
`#btn_mutate` writes `"CORRUPTED"` into `self.router_data["headers"]`, and the next event's
`cv_headers` still reports the pristine user agent (`out_dev/records.json`, steps 14/15) — the
copy-per-event claim holds.

### E. Compiled page does not contain a literal `rx_router_session`

The cluster brief suggested grepping `.web/` for `rx_router_session` to prove class-level
`State.router.session.client_token` compiles to the per-field var. It is not greppable there —
`.web/app/` contains no state-var identifiers at all in this build (state access goes through the
`@reflex` runtime in `node_modules`). The wire evidence is equivalent and stronger: the delta keys
are `rx_router_session_rx_state_` etc. and `#direct_token` renders the right value
(`out_dev/ws_frames.txt`).

### F. `analyze_frames.py` silently drops large frames

`drive_router.py` truncates each frame to 3000 chars when writing `ws_frames.txt`, so the
post-hoc analyzer cannot decode the big hydrate deltas and under-reports them. The per-step totals
printed live by `drive_router.py` (in `logs/drive_*.log`) are complete and are the numbers used in
the tables above. Noted so nobody re-derives the matrix from `ws_frames.txt` alone.

## Housekeeping

Servers on 3100/3101/3102 and 8100/8101, the redis on 8115 and all Chromium processes were killed;
`ss -ltnp` over 3100-3119 / 8100-8119 is clear. `.web/`, `node_modules/` and `.states/` are
excluded from this directory (the app rebuilds them on first `reflex run`).

## VERIFICATION

Independent adversarial verification (second agent, 2026-09-19). Worked from this NOTES.md, the
scripts/ and routerlab/ sources in this directory and the claimed-issue list only — no access to
the explorer's conversation. Everything was run from the neutral dir
`$SB/apps/verify_router_vars/` (`SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad`)
with the prebuilt PyPI-only venvs; the checkout was never installed nor used as a cwd. No server
was started for this pass (all three issues are class-creation-time behaviour); ports 3600-3619 /
8600-8619 stayed unused.

Versions (`uv pip freeze --python $SB/envs/shared/bin/python | grep reflex`):
`reflex==0.9.12a1`, `reflex-base==0.9.12a1`, `-components-code==0.9.6a1`, `-core==0.9.10a1`,
`-dataeditor==0.9.3a1`, `-gridjs==0.9.2a1`, `-lucide==1.0.4`, `-markdown==0.9.4a1`,
`-moment==0.9.4`, `-plotly==0.9.7a1`, `-radix==0.9.10a1`, `-react-player==0.9.2`,
`-recharts==0.9.4a1`, `-sonner==0.9.4a1`, `-hosting-cli==0.1.72`.
Baseline: `$SB/envs/prev` = `reflex==0.9.11.post1`.

New scripts and output live in `verification/scripts/` and `verification/logs/`.

### Issue 1 — `deps=["router"]` deprecation never fires: **CONFIRMED, but the stated root cause and
the "dead code" framing are wrong**

Reproduced as written:

```
cd $SB/apps/verify_router_vars && $SB/envs/shared/bin/python scripts/deps_legacy.py
```
→ `verification/logs/deps_legacy_new.txt`: no warning; deps are the five `rx_router_*` plus
`router`, exactly as claimed.

Refutation attempt turned up the real rule (`verification/scripts/v_deps_legacy_matrix.py`,
`verification/logs/v_deps_legacy_matrix.txt`) — the guard is **not** dead, it fires in 3 of 4
legacy-string cases:

| declaration | body reads `self.router`? | warning |
|---|---|---|
| `@rx.var(deps=["router"], auto_deps=False)` | yes | **fires** |
| `@rx.var(deps=["router"], auto_deps=False)` | no | **fires** |
| `@rx.var(deps=["router"])` (auto_deps default) | no | **fires** |
| `@rx.var(deps=["router"])` (auto_deps default) | **yes** | **silent** ← the reported case |

So the warning is lost precisely when the var body also touches the router — which is the normal
way anybody writes this (and what `routerlab.State.cv_deps_legacy_string` does). The framework's
own test `tests/units/test_state.py::test_router_var_dep_does_not_warn_for_the_var_form` only
covers `auto_deps=False`, which is why CI is green.

Corrected root cause (`verification/scripts/v_static_dep_pollution.py`): at declaration the static
deps are exactly `{None: {'router'}}`; `ComputedVar._deps()`
(`reflex_base/vars/base.py:2876-2895`) seeds `DependencyTracker` with **the same set objects** it
took from `_static_deps`, so the auto-detected `rx_router_*` names are merged into the static set
in place. By the time `reflex/state.py:1205-1221` runs `dvar_set.isdisjoint(constants.ROUTER_VARS)`
the legacy string is indistinguishable from the Var form. A fix must flag the legacy string where
it is parsed (`_add_static_dep`, the `isinstance(dep, str)` branch) — reading `_static_deps` after
`_deps()` has run is already too late, because that dict has been polluted.

Not a regression (0.9.11.post1 has no such deprecation at all; its `_deps` for the same
declaration is just `{'router'}` — `verification/logs/deps_legacy_prev.txt`). Severity low:
missing migration signal only, the var stays reactive.

Note on the NOTES.md wording: "the other deprecations in the same import (`@rx.memo` without
annotations, `RouterData.page`) do print" was **not** reproducible on a bare
`python -c "import routerlab.routerlab"` — that import prints only the `rx._x` experimental notice
and the SitemapPlugin notice. Those other deprecations fire when pages are rendered/compiled, not
at import. The main observation (no warning for `cv_deps_legacy_string`) does hold, and the
per-case matrix above is the stronger evidence that warnings are not globally suppressed.

### Issue 2 — router computed vars invalidated by all five fields: **measurement accurate, but
REFUTED as a defect**

`scripts/deps_probe.py` reproduces exactly (`verification/logs/deps_probe_new.txt`).

Three refutations:

1. **Narrow deps *can* narrow.** `verification/scripts/v_narrow_deps.py`:
   `@rx.var(deps=[rx.State.router.url], auto_deps=False)` resolves to
   `{'reflex___state____state': ['rx_router_url']}` and the root state's `_var_dependencies`
   registers it under `rx_router_url` only — `rx_router_headers/page/route_id/session` invalidate
   nothing. Same for `deps=[State.router.session]`. `State.router.url._get_all_var_data()
   .field_dependencies` is `{'reflex___state____state': ('rx_router_url',)}`, i.e. the per-field
   Vars are properly narrow. The deps_probe script simply omitted `auto_deps=False`, and `deps=`
   being *additive* unless `auto_deps=False` is long-standing reflex behaviour, not new in 0.9.12.
2. **Not a regression, and strictly better than before.** On 0.9.11.post1 the same probe prints
   `['router']` for every var including the explicit ones (`verification/logs/deps_probe_prev.txt`)
   — one var, so any router change invalidated every router-reading computed var and no narrowing
   was possible at all.
3. **No broken promise.** Nothing in `news/7068.*` claims per-field *computed-var* invalidation;
   the −67% figure is the router payload, and this cluster's own numbers confirm the router portion
   of the delta did shrink.

What remains is a real but inherent limitation of *auto* dependency detection: `self.router` is the
composed switchboard Var whose `field_dependencies` names all five, so any attribute read through
it depends on all five (confirmed in the routerlab app itself: `cv_headers` / `cv_session` carry all
five, which is why the recorded `logs/matrix_dev.txt` step 03 re-sends them). Follow-up
optimisation at most, not a release issue.

### Issue 3 — backend (underscore) var shadowing silently ignored: **CONFIRMED (pre-existing, low)**

`scripts/backend_shadow.py` reproduces on both versions (`verification/logs/backend_shadow_new.txt`,
`..._prev.txt`). Characterised further in a real state tree
(`verification/scripts/v_backend_shadow_tree.py`): with `P._priv: int = 1` and `C(P)._priv:
str = "shadow"`, `c._priv` reads `1` (the child's declared default is discarded) and `c._priv = x`
writes through to `P` — identical output on 0.9.12a1 and 0.9.11.post1
(`verification/logs/v_backend_shadow_tree_*.txt`). Same failure mode as issue #7074.

The exclusion is explicit, not an oversight of collection: `_check_overridden_inherited_vars`
(`reflex/state.py:1316-1350`) skips any field whose `name.startswith("_")` at **state.py:1335**.
A fix must restrict itself to names in `cls.inherited_backend_vars`, since that skip also covers
private non-var fields and framework internals. Alternatively narrow `news/7077.breaking.md`, which
as written ("a substate var that shadows a var inherited from a parent state") reads as covering
backend vars too. Not a regression, not a blocker.

### Housekeeping

No servers, browsers or redis started by this pass; nothing to kill. Nothing was written outside
this directory and `$SB/apps/verify_router_vars/`.
