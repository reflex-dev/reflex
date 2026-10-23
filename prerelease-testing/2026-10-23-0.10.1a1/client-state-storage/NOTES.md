# Cluster `client-state-storage` — reflex 0.10.1a1 prerelease testing

Tested on 2026-10-23 with the PyPI venvs `$SB/envs/shared` (reflex 0.10.1a1) and `$SB/envs/prev`
(reflex 0.10.0), Python 3.11, Chromium via Playwright (`$SB/envs/driver`).
`SB=/tmp/claude-0/-home-user-reflex/7eb9e30f-e96c-5de5-9b0e-4a12be91e0f3/scratchpad/prt`.

## Layout

- `app/` — the test app (`rxconfig.py`, `csapp/csapp.py`). The app module asserts it imports reflex
  from a `/scratchpad/prt/envs/` venv. Pages:
  - `/` global `rx._x.client_state` vars (`shared`, `pushed`, `pushed_bg`): readers always mounted,
    inside `@rx.memo`, inside `rx.foreach`, and behind `rx.cond` (late mount); `on_load` pushes
    `pushed` before any reader has mounted; a background task pushes `pushed_bg`.
  - `/second` readers/setters for the same client_state vars on another page.
  - `/storage` three `rx.LocalStorage(sync=True, name="shared")` vars in `SubA`, `SubB`, `Nested(SubB)`,
    one `other` synced var, `rx.Cookie`, `rx.SessionStorage`, two `@rx.var(cache=True)` reading
    storage vars with server-side evaluation counters (`EVALS`, printed as `[EVAL]` in the server
    log and shown on the page via the `read-counts` button).
  - `/bloat` `rx.LocalStorage` var filled with 1.1 MB / 500 kB to push the hydrate over the 1 MB default
    `REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE`.
  - `/expire` counter + LocalStorage `note` + background task sleeping 8 s; used with
    `REFLEX_REDIS_TOKEN_EXPIRATION=3 REFLEX_STATE_MANAGER_MODE=memory` (the memory/disk managers use
    `redis_token_expiration` as their expiry too).
- `app-prev/` — identical sources used for the 0.10.0 baseline (separate dir so `.web` differs).
- `scripts/run_server.sh <shared|prev> <fp> <bp> <logname> [extra args]` (env `APPDIR=app-prev` for
  the baseline), `scripts/stop_server.sh <logname>`, `scripts/test_cluster.py <base-url>
  <client_state|sync|computed|bloat|expire|all> --tag <label>`, `scripts/probe_404.py <url>`.
- `logs/*.log` server logs (`--loglevel debug`), `logs/<tag>-<scenario>.json` per-run console /
  pageerror / failed-request / websocket-open capture plus check results. `shots/` screenshots.

## How to rerun

```bash
SB=/tmp/claude-0/-home-user-reflex/7eb9e30f-e96c-5de5-9b0e-4a12be91e0f3/scratchpad/prt
A=$SB/apps/client-state-storage            # or a copy of this directory; scripts resolve paths from their own location... see note
# dev, 0.10.1a1
$A/scripts/run_server.sh shared 3140 8140 dev-shared
# wait until: curl --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3140/  -> 200
cd $A/scripts
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python test_cluster.py http://localhost:3140 client_state --tag new-dev
...  sync / computed / bloat the same way
$A/scripts/stop_server.sh dev-shared
# expiry scenario (needs the env knobs)
REFLEX_REDIS_TOKEN_EXPIRATION=3 REFLEX_STATE_MANAGER_MODE=memory $A/scripts/run_server.sh shared 3140 8140 dev-shared-expire
NO_PROXY=... test_cluster.py http://localhost:3140 expire --tag new-dev
# prod: both ports must be the same
$A/scripts/run_server.sh shared 3141 3141 prod-shared --env prod
# baseline 0.10.0
APPDIR=app-prev $A/scripts/run_server.sh prev 3142 8142 dev-prev
```
Note: `run_server.sh`/`stop_server.sh` hard-code `$SB/apps/client-state-storage`; adjust `A=` at
the top when running from the repo copy. `test_cluster.py` writes to `../logs` and `../shots`
relative to itself.

## Results (0.10.1a1 dev and prod unless noted; 0.10.0 baseline in brackets)

### client_state (#7407)
- PASS push before mount from `on_load` (reader behind `rx.cond` revealed later shows
  `pushed-on-load-1`). [0.10.0: FAIL, `_call_script TypeError: refs._client_state_setPushedcs is not a
  function`, reader shows default]
- PASS push before mount from a background task. [0.10.0: FAIL, same TypeError]
- PASS all readers (always-mounted, `@rx.memo`, `rx.foreach`, late `rx.cond`) follow `set_value`.
- PASS `push(None)` renders empty.
- PASS late-mounted reader: set to `clicked`, reveal, set back to default `initial` -> all readers
  `initial`. [0.10.0: FAIL, late reader stays `clicked`]
- PASS `on_load` push runs again after client-side nav away and back; `/second` loaded directly works.
- INFO value survives client-side navigation between pages (`/` -> `/second` shows `clicked`), both versions.

### sync=True vars sharing one storage name (#7545)
- PASS edit `SubA.shared_a` in tab A -> tab B shows `a=b=n=hello` for all three vars sharing
  `name="shared"`. [0.10.0: FAIL, only `a` updates; `b`, `n` stay empty]
- PASS edit `SubB.shared_b` in tab B -> tab A shows all three `world`. [0.10.0: FAIL]
- PASS non-sharing synced var `other` syncs; cookie visible in other tab after reload; session
  storage per-tab and survives reload.
- INFO (both versions): in the *same* tab, editing `shared_a` does not update `shared_b`/`shared_n`
  that share the same storage `name` (they only converge after a reload or via another tab's
  storage event). Pre-existing, not a regression.

### cached computed vars over storage (#7568)
- PASS exactly one evaluation of each cached var per full page load (`derived=1 derived_cookie=1`).
  [0.10.0: `derived=2 derived_cookie=1`, i.e. the synced LocalStorage dependency was evaluated twice]
- PASS not re-evaluated on an unrelated event; one eval per dependency change.
- INFO (both versions): after client-side navigation away from `/storage` and back, `derived`
  (depends on the `sync=True` LocalStorage var) is evaluated twice, `derived_cookie` zero times.
  Same on 0.10.0, so not a regression; noted as a possible follow-up for #7568.
- Prod mode: identical counts.

### hydrate over the server message size limit (#7551, #7605)
- PASS toast "Hydration payload (1100502 characters) exceeds the server limit (1000000 characters).
  Reduce browser storage data and reload." appears at once, has a close button, is still visible
  after 30 s; exactly 1 websocket open in 30 s; `is_hydrated` stays false; console shows the same
  message once as `console.error`; the dev server log echoes it via the vite client console relay.
  [0.10.0: no toast, 1350 websocket opens in 30 s (tight reconnect loop)]
- PASS removing the item and reloading hydrates again; 500 kB value hydrates fine.
- Screenshots: `shots/new-dev-bloat-toast*.png`, `shots/prev-dev-bloat-toast.png`.

### background task re-entering an expired session (#7585)
Server: `REFLEX_REDIS_TOKEN_EXPIRATION=3 REFLEX_STATE_MANAGER_MODE=memory`. Page `/expire`: type
`keepme` into the LocalStorage input, click `inc` twice, click `slow-8`, wait.
- PASS after the task finishes the browser no longer shows stale `count=2`; it shows `count=0`
  matching the server; route stays `/expire`; `localStorage['expire-note']` still `keepme`.
  [0.10.0: browser keeps stale `count=2`, `loads=1`, token]
- PASS next event (`inc`) applies (`count=1`) and runs the page `on_load` (`loads=1`), and the
  router/`client_token` is restored.
- ANOMALY (new behaviour side effect): between the background rehydrate and the next event the page
  renders `State.router.session.client_token` as an empty string and `loads=0`, with
  `is_hydrated=true`. Screenshot `shots/new-dev-expire-after-bg.png`.
- ANOMALY (both versions, surfaces earlier on 0.10.1a1): after the rehydrate the LocalStorage var
  `note` renders its default (`note=`) although `localStorage` still holds `keepme`; the server-side
  state keeps `note=''` even after the next event (which runs `on_load`) and only a full reload
  re-sends the stored value. On 0.10.0 the same divergence appears right after the next event
  (foreground rehydrate path). The hydrate snapshot carries `is_hydrated=false` so the client does
  not overwrite storage, but nothing re-sends the stored values to the new tree.
- The last check (`expire_no_rehydrate_when_tree_kept_alive`) is a test-design error: activity
  stopped 5 s before the task ended, so the 3 s expiry legitimately fired; disregard it.

### other observations
- Dev server (0.10.1a1): on the very first request while vite was doing its initial
  `(ssr) program reload` of `utils/context.jsx`, SSR threw `TypeError: Cannot read properties of null
  (reading '1') at DefaultOverlayComponents (.web/app_components/reflex/app.jsx:18)` (the
  `useContext(EventLoopContext)[1]` line) and the request returned HTTP 500; the next request was 200
  and it never recurred. Log: `logs/dev-shared.log` first run (the log was overwritten by the
  restart; the excerpt is reproduced in the structured findings). Looks like a startup race, not
  storage related.
- The dev reloader watches every top-level directory of the app dir (it listed `shots/`, `logs/`,
  `scripts/` as reload paths); writing a screenshot PNG into the app dir triggered
  "Changes detected, reloading workers", which re-ran hydration and `on_load` in open tabs. Moved
  outputs outside the app dir (`app/` subdir) to avoid it.
- Prod mode logs a console error `Failed to load resource: 404` for `/favicon.ico` because the app
  has no favicon in `assets/`; dev mode does not. Benign.
- `DeprecationWarning: RouterData.page ... Use RouterData.url` is from the test app's own
  `self.router.page.path`, not the framework.
- Console on every scenario otherwise clean (only "Disconnect websocket on page navigation" logs).
