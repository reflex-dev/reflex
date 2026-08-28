# Routing & navigation cluster — reflex 0.9.9a1 pre-release testing

Date: 2026-08-28. Agent cluster: `routing`. All installs from PyPI
(`reflex==0.9.9a1` in the shared smoke venv; `reflex==0.9.8` baseline in its own venv).

## Changelog items under test

- #6593 — stale `on_load` no longer blocks/outlives navigation; `@rx.event(supersedes=True)`
- #6790 — `[[...splat]]` catchall no longer matches mere prefix paths (`/postsomething`)
- #6953 — no spurious `RouteValueError` for `/posts/all/[x]` + `/posts/[id]` siblings (both orders)
- #6919 (reflex-base) — chained events inherit the routing data of the event that produced them

## Contents

- `routing_app/` — the 0.9.9a1 test app (pages: `/`, `/slow`, `/slowbg`, `/other`,
  `/posts/[[...splat]]`, `/postsomething`, `/articles/all/[x]`, `/articles/[id]`).
  Slow async on_load (4 x 1s steps), background-task on_load, `supersedes=True` button,
  chained-event handlers reading `self.router.url.path` + dynamic arg `self.id`.
  Every page footer exposes all state logs in DOM nodes (`#slow-progress`, `#bg-progress`,
  `#visits`, `#chain-log`) so Playwright can assert server-side behavior.
- `routing098/` — same app for the 0.9.8 baseline, with `supersedes=True` stripped
  (kwarg does not exist in 0.9.8).
- `conflict098/` — minimal rxconfig-only dir to run the conflict script under 0.9.8.
- `drive_routing.py` — main Playwright suite (all four changelog items).
- `drive_extra.py` — 404-prefix on_load-misfire probe + button-started background task probe.
- `drive_backforward.py` — browser history back/forward across catchall/static/dynamic routes.
- `route_conflict_check.py` — compile-time RouteValueError checks (#6953), subprocess per case.
- `dev_server.log`, `prod_server.log` (0.9.9a1), `dev_server_098.log`, `prod_server_098.log`.
- `shots/` (0.9.9a1 dev), `shots_prod/` (0.9.9a1 prod), `shots098/` (0.9.8) — screenshots.

## How to rerun

```bash
SB=<scratchpad>; APP=<this dir>
# dev server (0.9.9a1):
cd $APP/routing_app && REFLEX_TELEMETRY_ENABLED=false \
  $SB/envs/smoke/bin/reflex run --frontend-port 3100 --backend-port 8100 --loglevel debug
# do NOT override NO_PROXY when starting servers: the container default NO_PROXY already
# contains localhost AND registry.npmjs.org; overriding it with just "localhost,127.0.0.1"
# routes bun's npm traffic through the agent proxy, which drops it (see anomaly below).

# browser suites (playwright venv):
python drive_routing.py http://localhost:3100 shots            # all tests
python drive_routing.py http://localhost:3100 shots slowcancel # subset by key
python drive_extra.py http://localhost:3100 shots
python drive_backforward.py http://localhost:3100 shots

# compile-time conflict checks (#6953), from inside an app dir:
cd $APP/routing_app && $SB/envs/smoke/bin/python ../route_conflict_check.py       # 0.9.9a1
cd $APP/conflict098 && <0.9.8 venv>/bin/python ../route_conflict_check.py         # 0.9.8

# prod mode (0.9.9a1 requires a SINGLE port for frontend+backend):
cd $APP/routing_app && $SB/envs/smoke/bin/reflex run --env prod \
  --frontend-port 8102 --backend-port 8102 --loglevel debug
python drive_routing.py http://localhost:8102 shots_prod
```

## Results (all details in the structured findings)

### #6593 — stale on_load cancellation / supersedes=True: WORKS

- Dev + prod: navigating away from `/slow` mid-on_load cancels the chain — zero further
  state writes after navigation (0.9.8 baseline: chain survives and keeps appending
  step2..step4 after the user has left the page). Server log shows
  `Cancelling the previous unfinished ...on_load_internal chain for token ...`.
- New page's on_load fires immediately (~0.1s), never queued behind the stale 4s chain.
- Re-visiting `/slow` afterwards runs a fresh on_load to completion.
- `@rx.event(supersedes=True)` on a button: 4 rapid clicks -> all 4 invocations start
  (counter reaches 4) but only the LAST completes (`click-4-done` alone). Non-superseding
  handler baseline: all 3 clicks complete. Single click completes normally.

### #6790 — splat prefix matching: FIXED (verified against 0.9.8 repro)

- `/postsomething` renders its own page and only its own on_load fires (dev + prod,
  direct load + client-side nav). `/posts` and `/posts/a/b` hit the catchall with correct
  splat args.
- The actual 0.9.8 failure mode reproduced on baseline: visiting `/posts-archive`
  (no page, shares the `posts` prefix) renders the 404 page but the backend fires the
  CATCHALL's on_load with `path=/posts-archive` (visible in the visits log). On 0.9.9a1
  no misfire — 404 page, no catchall on_load. `reflex/route.py` regex fix confirmed.

### #6953 — static/dynamic sibling routes: FIXED both orders

`route_conflict_check.py` (fresh subprocess per case; conflicts trip at page COMPILE time,
not at `add_page` time):

| case | 0.9.8 | 0.9.9a1 |
|---|---|---|
| `/posts/[id]` then `/posts/all/[x]` | RouteValueError (`'[id]' != 'all'`) | no error |
| `/posts/all/[x]` then `/posts/[id]` | no error (order-dependent bug) | no error |
| `/posts/[id]` + `/posts/[foo]` | raises (correct) | raises (correct) |
| `/posts/[id]` + `/posts/[[...splat]]` | raises (correct) | raises (correct) |
| `/posts/all` + `/posts/[id]` both orders | no error | no error |

- Browser resolution: `/articles/all/5` -> static `all` page (x=5); `/articles/7` ->
  dynamic page (id=7); `/articles/all` (2 segments) -> dynamic page with id="all"
  (expected: the static sibling needs 3 segments). Verified on direct load, client-side
  nav, and prod.

### #6919 — chained events inherit routing data: FIXED (verified against 0.9.8 repro)

- Two tabs (`/articles/1`, `/articles/2`), chain fired in both ~simultaneously: each tab's
  chained `record_args` sees its own `path`/`id`. (Tabs have separate client tokens.)
- Sharpest case, same tab: fire the chain on `/articles/1`, client-nav to `/articles/2`
  during the 2s sleep. 0.9.9a1: chained event records `path=/articles/1:id=1` (the view
  that produced it). 0.9.8 baseline: records `path=/articles/2:id=2` (the bug).
- Works identically in prod.

### Browser history

Back/forward across postsomething -> posts catchall -> articles/all/5 -> articles/2:
every step resolves the right page and fires the right on_load with correct routing data
(dev + prod; in prod the URL shows `/postsomething/` with a trailing slash — see below).

## Anomalies / observations (none are 0.9.8 regressions)

1. **Behavior change: an on_load that is a background task is cancelled on navigation.**
   On 0.9.9a1, `@rx.event(background=True)` used as on_load starts (`bg1-start` written)
   and is then cancelled when the user navigates away (no step ever completes; no
   traceback in the server log). On 0.9.8 the same background task survives navigation and
   completes all 4 steps. Background tasks started from a normal BUTTON click still
   survive navigation on 0.9.9a1 (verified) — the cancellation is scoped to the
   superseded on_load chain. Plausibly intended (#6593 cancels "the previous unfinished
   event chain", and the bg task is a child of it), but it is a user-visible semantic
   change for apps that use a background on_load to prefetch/stream data across pages,
   and the changelog does not call it out. Repro: `drive_routing.py ... bg` vs the same
   on 0.9.8.
2. **Prod serves HTTP 404 status for direct loads of dynamic-route URLs** (`/posts`,
   `/posts/a/b`, `/articles/7`, `/articles/all/5`) while returning the SPA HTML that then
   renders the correct page. Static routes 307-redirect to `.../` and then 200. Identical
   on 0.9.8 prod -> longstanding behavior, not a regression; bad for SEO/monitoring but
   out of scope for this release.
3. **Prod-only "Page X is being redefined with the same component." warnings** for every
   page at backend startup (8 pages -> 8 warnings). Also present on 0.9.8 prod. Benign,
   noisy, pre-existing.
4. **Prod mode now requires a single port**: `reflex run --env prod` with different
   frontend/backend ports exits with "In prod mode, frontend and backend must run on the
   same port." (0.9.9 behavior; use the same value for both flags.)
5. **Cosmetic**: RouteValueError message has a double space: "same dynamic path in
   posts/[id] and ..." (present in 0.9.8 too).
6. **Environment footgun (not a reflex bug)**: prefixing `reflex run` with
   `NO_PROXY=localhost,127.0.0.1` (as the agent brief suggested for local HTTP) *replaces*
   the container's default NO_PROXY, which also contains `registry.npmjs.org`; bun's
   `bun add` then goes through the agent proxy and dies with ~120 `ConnectionClosed
   downloading package manifest ...` errors after the npmmirror fallback. With the default
   env untouched the install works. The known-benign 3x "Failed to connect"
   registry.npmmirror.com probe lines appeared as expected.
7. `/articles/[id]` with arg name `id` (shadow-prone name) works fine as a
   `DynamicRouteVar` (`rx.State.id` frontend + `self.id` in handlers).
8. Two `rx.App()` instances in one process now require
   `RegistrationContext.set(RegistrationContext.get().fork())` (0.9.9); plain repeated
   `rx.App()` raises `ReflexRuntimeError` with a helpful message. `route_conflict_check.py`
   sidesteps this with one subprocess per case (also portable to 0.9.8, which has no
   `fork`).

## VERIFICATION (independent adversarial check, 2026-08-28)

Claim verified: **"Background-task on_load is cancelled on navigation" is CONFIRMED**
as a real 0.9.9a1 behavior regression vs 0.9.8.

Method: independent minimal app written from the repro description alone
(`verify_bg_onload/vbg/` — 3 pages: `/`, `/slowbg` with
`@rx.event(background=True)` on_load doing `async with self` writes 1s apart,
`/other` with a button starting the identical background task), run from PyPI
installs only (0.9.9a1 = shared smoke venv; 0.9.8 = fresh `envs/verify098` venv),
driven by `verify_bg_onload/drive_verify.py` (ports 3600/8600 and 3601/8601).

Results (same app source, same script, only the reflex version differs):

| test | 0.9.9a1 dev | 0.9.8 dev |
|---|---|---|
| A control: stay on /slowbg | bg on_load completes step1..step4 | completes |
| B repro: client-nav away after `load1-start` | **frozen at `load1-start`; zero writes 6s after nav** | completes step1..step4 after nav |
| C contrast: button-started bg task, nav away | completes | completes |

Refutation attempts, all failed:
- Not a delta-emission artifact: after B, a hard reload of `/other` still shows
  only `load1-start` (`drive_reload_check.py`) — the state writes never happened
  server-side; the task really is cancelled.
- Not app/env specific: control A completes on 0.9.9a1, and the identical
  button-started task (C) survives navigation on 0.9.9a1 — cancellation is
  scoped exactly to the on_load chain, ruling out websocket-disconnect or
  environment explanations.
- Not API misuse: `background=True` handlers are legal `on_load` targets in both
  versions and worked in 0.9.8.

Mechanism (from release source, commit a33e02ade / PR #6713 for #6593):
`on_load_internal` is marked `supersedes=True`; on the next navigation
`EventProcessor._supersede_previous` cancels the previous chain if not
`all_done()`, and `_on_future_done` cascades `cancel()` to ALL child futures and
their asyncio tasks. A background on_load handler is a child future of the
on_load chain, and (unlike sequential children) it keeps the chain "unfinished"
for its whole lifetime, so any later navigation cancels it mid-flight.
Server log shows only a Debug-level "Cancelling the previous unfinished
...on_load_internal chain" line — no traceback, silent from the app's view.

Why this is a defect and not just an undocumented intended change:
- Background tasks exist to escape chain semantics and run long; 0.9.8 let them
  survive navigation. Apps using a background on_load to prefetch/stream data
  across pages silently lose data with no error and no opt-out
  (`supersedes` can only be set on the chain root, not opted out by the child).
- Neither news fragment (news/6593.bugfix.md, packages/reflex-base/news/6593.bugfix.md)
  mentions background tasks, and no unit test in the supersession commit covers a
  background child of a superseded chain — the interaction appears unconsidered
  rather than designed.

Suggested fix direction for the fix-agent: exclude `is_background` child futures
from the supersession cancellation cascade (or detach background children from
the chain future for supersession purposes), or provide an explicit opt-out and
a changelog/docs callout. Severity medium is fair.

## VERIFICATION (adversarial verifier, anomaly #2: prod HTTP 404 for dynamic-route direct loads)

Independently reproduced from the repro steps alone with a fresh minimal app
(`$SB/apps/verify_routing_1/vapp`: pages `/`, `/other`, `/articles/[id]`, `/posts/[[...splat]]`),
built with `reflex init --template blank` and run via
`reflex run --env prod --frontend-port 8604 --backend-port 8604` (0.9.9a1 smoke venv, PyPI).

- curl matrix (0.9.9a1): `/` 200; `/other` 307 -> `/other/` 200; `/articles/7`,
  `/articles/7/`, `/posts`, `/posts/`, `/posts/a/b` all **404**, body = 5167 bytes,
  byte-identical (`cmp`) to `.web/build/client/404.html`; `/definitely-not-a-page` also 404
  with the same body — valid dynamic URLs and true 404s are indistinguishable at the HTTP layer.
- Playwright (Chromium, document response status): `/articles/7` -> status 404, renders
  `PAGE:article:7`; `/posts/a/b` -> 404, renders correctly; `/other` -> 307/200, renders.
- 0.9.8 baseline (separate PyPI venv `routing098`, identical app in
  `$SB/apps/verify_routing_1/vapp098`, port 8605): identical curl matrix and identical
  Playwright results. Confirmed pre-existing, NOT a 0.9.9 regression.

Root cause (read from `reflex/utils/exec.py` + `reflex/utils/build.py`, identical in the
installed 0.9.8 and 0.9.9a1 wheels): prod mode mounts the built frontend with Starlette
`StaticFiles(html=True)` (`get_frontend_mount` -> `PrecompressedStaticFiles`), and the build
step copies the react-router SPA fallback (`__spa-fallback.html`) over `404.html`
(`build.py: path_ops.cp(spa_fallback, static_dir / "404.html")`). Starlette's `html=True`
semantics serve `404.html` with status 404 for any path that maps to no file; dynamic routes
are never prerendered to files, so they always take this path. Static pages exist as
`<route>/index.html` dirs, hence the 307 -> 200. This is the standard "SPA fallback via
404.html" static-hosting technique — deliberate design, correct rendering, wrong-ish status.

Verdict: the claim is **factually accurate as filed** (reproduced end-to-end, twice, plus
source-level root cause). However it is longstanding intended-tradeoff behavior identical in
stable 0.9.8 — an environment-independent framework *limitation*, not a 0.9.9a1 defect or
regression, so it is NOT actionable for this release (marking confirmed=false on the
"fix-agent should act" bar only). If ever tackled upstream: the prod backend knows the route
table (`app.router(path)`), so the static mount could serve the fallback with 200 for
routable paths and reserve 404 for genuinely unknown ones.
