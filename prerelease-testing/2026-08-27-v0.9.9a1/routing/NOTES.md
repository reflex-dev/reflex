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
