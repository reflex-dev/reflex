# rv_render_state — 0.9.12a2 re-verification (render_ctx_statemgr + memo_aschild sweep)

Phase 7 re-verification of the `render_ctx_statemgr` and `memo_aschild` surfaces against the published
**reflex 0.9.12a2 / reflex-base 0.9.12a2** train, with the 0.9.12a1 alpha (`envs/shared`) and 0.9.11.post1
(`envs/prev`) as baselines. Everything here was installed from PyPI by the orchestrator; nothing was installed
from, or run with the cwd inside, any checkout.

**Verdict for this cluster: no regression. 16 pass, 0 fail, 3 anomalies (all explained, none release-blocking),
1 skipped.** The two fixes that touch this surface — #7216 (uncached-var delta recording) and #7218 (app wraps
below the sticky badge) — are both confirmed working end to end, each with an `envs/shared` A/B that shows the
0.9.12a1 failure and the 0.9.12a2 pass. The three pre-existing findings the brief names (FINDING-023, -024,
-025) and FINDING-008 are unchanged, field for field.

## Environments

```
$ uv pip freeze --python $SB/envs/a2/bin/python | grep -i reflex
reflex==0.9.12a2
reflex-base==0.9.12a2
reflex-components-code==0.9.6a1
reflex-components-core==0.9.10a1
reflex-components-dataeditor==0.9.3a1
reflex-components-gridjs==0.9.2a1
reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.4a1
reflex-components-moment==0.9.4
reflex-components-plotly==0.9.7a1
reflex-components-radix==0.9.10a1
reflex-components-react-player==0.9.2
reflex-components-recharts==0.9.4a1
reflex-components-sonner==0.9.4a1
reflex-hosting-cli==0.1.72

$SB/envs/shared : reflex==0.9.12a1 + the same component alphas   (the "a1" column)
$SB/envs/prev   : reflex==0.9.11.post1 + the matching stables    (the "prev" column)
$SB/envs/driver : playwright 1.63, httpx, websockets; chromium at /opt/pw-browsers/chromium
```

Redis 7.0 on `localhost:8199` (`redis-server --port 8199 --save ''`), shut down at the end.
Ports used, all inside the reserved range: frontend 3180-3192, backend 8180-8192, redis 8199.
`REFLEX_TELEMETRY_ENABLED=false` on every server; `NO_PROXY=localhost,127.0.0.1` on every client only.
All processes were killed by pid at the end; `ports.py 3180..3199 8180..8199` reports nothing listening.

## Apps

| dir | provenance |
|---|---|
| `renderapp/`, `renderapp_a1/`, `renderapp_prev/`, `diskapp/` | verbatim copies of `render_ctx_statemgr/{renderapp,diskapp}` |
| `memoaschild/` | verbatim copy of `memo_aschild/memoaschild` (one change, noted below: `show_built_with_reflex`) |
| `apps/deltaapp/` | **new here** — state-manager × delta matrix probe (uncached vars incl. a withheld one, substates, background task with `async with self`, event chain, `rx._x.client_state`) |
| `apps/wrapapp/` | **new here** — app-wrap nesting probe: custom wraps at priority +5, 0, -2, -3 plus the real `rx.data_editor` `(-1, "DataEditorPortal")` wrap and the sonner toaster, run in prod with the default badge |

`renderapp` needed no changes. `memoaschild` ships `show_built_with_reflex=False` in its own `rxconfig.py`,
so the app-wrap-with-badge half of check 5 required flipping that to `True` for one extra prod build
(`logs/memo_prod_badge_a2.log`); the 52-check driver runs were done on the app as the campaign left it.

## Rerun commands

```bash
SB=/tmp/claude-0/.../scratchpad ; W=$SB/reverify/rv_render_state
export REFLEX_TELEMETRY_ENABLED=false
redis-server --port 8199 --save '' &

# 1. render-count suite, a2 dev
cd $W/renderapp   && $SB/envs/a2/bin/reflex run --frontend-port 3180 --backend-port 8180
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/drive_render.py    http://localhost:3180 $W/out a2_dev
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/initial_renders.py http://localhost:3180 6 a2_dev
$SB/envs/driver/bin/python $W/scripts/cmp_render.py <campaign>/out/new_dev_result.json $W/out/a2_dev_result.json a1 a2

#    same on the a1 and prev baselines (separate app dirs so .web is not shared)
cd $W/renderapp_a1   && $SB/envs/shared/bin/reflex run --frontend-port 3182 --backend-port 8182
cd $W/renderapp_prev && $SB/envs/prev/bin/reflex   run --frontend-port 3192 --backend-port 8192

# 1b. prod replay
cd $W/renderapp && $SB/envs/a2/bin/reflex run --env prod --frontend-port 3189 --backend-port 3189
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/drive_render.py http://localhost:3189 $W/out a2_prod

# 2. StateManagerDisk
cd $W/diskapp && REFLEX_STATE_MANAGER_MODE=disk $SB/envs/a2/bin/reflex run --frontend-port 3190 --backend-port 8190
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/drive_disk2.py \
    http://localhost:3190 http://localhost:8190 $W/out a2_disk $W/diskapp/diskapp/diskapp.py
#    shutdown flush (debounce long enough that only a flush can explain the write)
cd $W/diskapp && REFLEX_STATE_MANAGER_MODE=disk REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS=30 \
    $SB/envs/a2/bin/reflex run --frontend-port 3190 --backend-port 8190
curl -s --noproxy '*' "http://localhost:8190/api/set_fresh?token=probe-0002&value=FLUSH-ON-SHUTDOWN-2"
ls -l --time-style=+%H:%M:%S $W/diskapp/.states/     # empty
kill -TERM <backend pids from ports.py 8190>
ls -l --time-style=+%H:%M:%S $W/diskapp/.states/     # written at the SIGTERM second

# 3. FINDING-023 latch
cd $W/renderapp && $SB/envs/a2/bin/reflex run --frontend-port 3191 --backend-port 8191   # clean compile, then kill
touch $W/renderapp/.web/nocompile
cd $W/renderapp && RENDERAPP_EXTRA_STATE=1 $SB/envs/a2/bin/reflex run --frontend-port 3191 --backend-port 8191
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/drive_mismatch.py http://localhost:3191 $W/out a2_mismatch

# 4. state managers x deltas
cd $W/deltaapp && $SB/envs/a2/bin/reflex run --frontend-port 3181 --backend-port 8181                       # dev/memory
cd $W/deltaapp && REFLEX_REDIS_URL=redis://localhost:8199 $SB/envs/a2/bin/reflex run --frontend-port 3181 --backend-port 8181   # dev/redis
cd $W/deltaapp && REFLEX_REDIS_URL=redis://localhost:8199 GRANIAN_WORKERS=2 \
    $SB/envs/a2/bin/reflex run --env prod --frontend-port 3183 --backend-port 3183                          # prod/redis, 2 workers
cd $W/deltaapp_a1 && $SB/envs/shared/bin/reflex run --frontend-port 3182 --backend-port 8182                # a1 baseline
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/drive_delta.py http://localhost:<port> $W/out <label>

# 5. memo_aschild + app wraps
cd $W/memoaschild && $SB/envs/a2/bin/reflex run --frontend-port 3185 --backend-port 8185
cd $W/memoaschild && $SB/envs/a2/bin/reflex run --env prod --frontend-port 3186 --backend-port 3186
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/mscripts/drive.py http://localhost:<port> $W/shots/<label>
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/memo_wraps_probe.py http://localhost:3186 $W/out a2_memoprod_badge
cd $W/wrapapp    && $SB/envs/a2/bin/reflex     run --env prod --frontend-port 3187 --backend-port 3187
cd $W/wrapapp_a1 && $SB/envs/shared/bin/reflex run --env prod --frontend-port 3188 --backend-port 3188
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/drive_wraps.py http://localhost:<port> $W/out <label>
```

## Results

| # | check | a2 | a1 | prev | evidence |
|---|---|---|---|---|---|
| 1.1 | renderapp dev: per-substate isolation — a delta touching only SubA/SubB re-renders only A/B/dual; C–H, colormode, evloop, componentstate, foreach untouched | **pass** | same | same | `out/a2_dev_result.json` `marks.after_load_onload` |
| 1.2 | renderapp dev: every event-driven scenario's render delta identical to the campaign's a1 recording (`events[]` list compares equal) | **pass** | — | — | `cmp_render.py` → `events: SAME` |
| 1.3 | renderapp dev: initial `on_load` A/B/dual count equals the campaign's a1 `2/2/2` | **anomaly** | 2.7 | 3.0 | `logs/initial_{a2,a1,prev}_dev.log` — bimodal on all three versions, see A-1 |
| 1.4 | renderapp dev: zero console errors, zero page errors, zero failed requests, ws 129 recv / 54 sent | **pass** | identical | — | `out/a2_dev_result.json` |
| 1.5 | renderapp prod replay: every render mark and every value identical to the campaign's a1 prod recording; counts exactly half of dev | **pass** | identical | — | `cmp_render.py` new_prod vs a2_prod → all `SAME`; 127/54 frames |
| 2.1 | diskapp D1: five ws bumps land on disk after the 2 s debounce (`counter: 5`) | **pass** | same | — | `out/a2_disk_result.json` |
| 2.2 | diskapp D2 (#7159): two `set_state` calls with **different** instances in one window — queue stays length 1, disk gets `second-queued`/202 | **pass** | same | — | `out/a2_disk_result.json` |
| 2.3 | diskapp D3: a state never obtained from `get_state` is persisted (`fresh-persisted`/999) | **pass** | same | — | `out/a2_disk_result.json` |
| 2.4 | diskapp D4: `modify_state(BaseStateToken(...))` from an API route pushes live **and** persists; survives reload | **pass** | same | — | `out/a2_disk_result.json` |
| 2.5 | diskapp D6/D7: 20 rapid sets → `rapid-20`/20; state survives a hot reload | **pass** | same | — | `out/a2_disk_result.json` |
| 2.6 | diskapp: shutdown flush — 30 s debounce, `.states/` empty, SIGTERM at 22:19:48 → 5 pickles written at 22:19:48 | **pass** | same | — | `logs/disk_debounce30_a2.log`, timestamps in this file |
| 2.7 | FINDING-025 `.states/` wiped at startup — unchanged (pre-existing, not re-reported) | **pass** (unchanged) | — | same | `.states/` empty at D0 and again after the debounce-30 restart |
| 2.8 | FINDING-024 `modify_state("<bare client token>")` → bare HTTP 500 — unchanged (pre-existing) | **pass** (unchanged) | same | same | `out/a2_disk_result.json` step `D5_legacy_bare_token_modify_state` |
| 3 | FINDING-023 latch: unknown-substate delta kills the frontend one-way — unchanged (note only) | **pass** (unchanged) | identical | identical | `out/a2_mismatch_result.json` |
| 4.1 | deltaapp dev/memory: withheld `@rx.var(cache=False)` is re-delivered when the filter stops dropping it (#7216) | **pass** | **FAIL** | — | `out/a2_devmem_delta_result.json` vs `out/a1_devmem_delta_result.json` |
| 4.2 | deltaapp dev/redis (single worker): identical value sequence, no pickling error, redis holds 4 keys | **pass** | — | — | `out/a2_devredis_delta_result.json` |
| 4.3 | deltaapp prod/redis, `GRANIAN_WORKERS=2`: identical value sequence to dev; survives reload | **pass** | — | — | `out/a2_prodredis2w_delta_result.json` |
| 4.4 | deltaapp: substate deltas, event chain, background task with `async with self`, `rx._x.client_state` — same results under all three managers | **pass** | same | — | the three `*_delta_result.json` |
| 5.1 | memo_aschild dev on a2: 49/52, same three known failures as the campaign | **pass** | 49/52 | 49/52 | `logs/memo_drive_dev_a2.log` |
| 5.2 | memo_aschild prod on a2: 49/52, same three known failures | **pass** | 49/52 | — | `logs/memo_drive_prod_a2.log` |
| 5.3 | FINDING-008 dropdown trigger swallows `on_click` — unchanged (pre-existing) | **pass** (unchanged) | same | same | `FAIL triggers: dropdown trigger on_click runs :: 3->3` in both logs |
| 5.4 | #7218 app wraps below the badge: custom wraps at −2 and −3 **and** the `rx.data_editor` `#portal` (−1) all present in prod alongside the badge | **pass** | **FAIL** | — | `out/a2_prod_wraps.json` vs `out/a1_prod_wraps.json` |
| 5.5 | memo_aschild prod with the badge on: 3 memo uploads render, toaster overlay present, toast fires, badge present, no page errors | **pass** | — | — | `out/a2_memoprod_badge_memo_wraps.json` |
| 5.6 | #6708 svg memo, #7122 shared chains, #7176 memo app-wraps, #7133 `force_match`, #7130 fallback SVG | **pass** | same | — | `logs/memo_drive_{dev,prod}_a2.log` |
| 6 | #6180 stable ThemeProvider/EventLoopProvider values | **skipped** | — | — | the campaign already recorded that this app cannot measure it (0 extra renders on both versions) |

### The two fixes, as A/B tables

**#7216 — a withheld `@rx.var(cache=False)` is re-sent (FINDING-003).** `apps/deltaapp` patches
`Root.get_delta` after class creation to drop `uncached_n` from the delta whenever `visible` is false — the
reflex-enterprise auth-filter shape. Same app, same script, same machine:

| step | a2 `v_unc` | a1 `v_unc` |
|---|---|---|
| after_load (hidden) | `U0` | `U0` |
| bump ×3 (hidden) | `U0` | `U0` |
| **show** | **`U3`** | **`U0`** ← stale, never re-sent |
| bump (visible) | `U4` | `U4` |
| hide, bump (hidden) | `U4` | `U4` |
| **show again** | **`U5`** | **`U4`** ← stale again |

The cached companion (`cached_n`) tracks correctly on both versions throughout, which isolates the defect to
the uncached-var "already sent" memo. a2 gives the same six values under dev/memory, dev/redis and
prod/redis-with-2-workers.

**#7218 — app wraps below the sticky badge (FINDING-012).** `apps/wrapapp` registers custom wraps at
priorities +5, 0, −2, −3 next to `rx.data_editor`'s real `(−1, "DataEditorPortal")` wrap, built with
`reflex run --env prod` and the default `show_built_with_reflex=True`:

| wrap (priority) | a2 prod | a1 prod |
|---|---|---|
| `hi` (+5) | present | present |
| `zero_ish` (0) | present | present |
| `lo` (−2) | **present** | **missing** |
| `lo3` (−3) | **present** | **missing** |
| `#portal` — `rx.data_editor` (−1) | **present** | **missing** |
| sticky badge | present | present |
| sonner toaster + toast fires | yes | yes |

So the fix is not portal-specific: every wrap below the badge now renders, and the badge itself still renders.

## Anomalies

### A-1 (measurement correction, not a defect) — the "#6181 halves the `on_load` render count" row does not reproduce on any version

The campaign's `render_ctx_statemgr` table records the initial `page load + on_load touching SubA and SubB`
as `A/B/dual = 2/2/2` on 0.9.12a1 against `4/4/4` on 0.9.11.post1, and calls it "the only measurable win in
this app". My first `drive_render.py` run on a2 read `4/4/4`, which looks like the win being lost. It is not:
the count is bimodal on every version. Six fresh contexts each (`scripts/initial_renders.py`, same machine,
back to back):

| version | A (6 samples) | mean |
|---|---|---|
| 0.9.12a2 | `[2, 4, 4, 4, 2, 2]` | 3.0 |
| 0.9.12a1 | `[4, 4, 2, 2, 2, 2]` | 2.7 |
| 0.9.11.post1 | `[4, 4, 2, 4, 2, 2]` | 3.0 |

`C`–`H`, `PAGE` read exactly `2` in all 18 runs. The `2` vs `4` is whether the hydrate delta and the `on_load`
delta land in one React commit or two (dev StrictMode doubles each commit); it is a race with vite's dev
server, not a property of the release. What #6181 actually guarantees — and what holds on a2 — is that the
second commit re-renders **only** the two substates the `on_load` touched. Every event-driven scenario
(`events[]` in the result JSON: 5×bump = 10 on A and 0 elsewhere, the 5 s storm = 100 on B, colour-mode ×4 = 8
on the colormode probe and 0 elsewhere, the 300-row rebuild) compares equal between a1 and a2, and the prod
replay is identical mark for mark. Recommendation: soften that one table row in the campaign notes to
"unchanged / not measurable in this app"; nothing to fix in the framework.

Secondary detail from the same comparison, in a2's favour and equally timing-dependent: at the `after_reload`
snapshot the a1 recording has every probe at `4` and `foreach_row` at `1200`, while a2 read `2` and `600`
(one full-tree commit instead of two).

### A-2 (pre-existing, all three versions) — `get_delta` cannot be overridden by declaring it on a State subclass

Writing the documented downstream pattern the obvious way fails at class-creation time:

```python
class S(rx.State):
    def get_delta(self):
        return super().get_delta()
# EventHandlerShadowsBuiltInStateMethodError: The event handler name `get_delta`
# shadows a builtin State method; use a different name instead
```

`scripts/getdelta_probe.py` run against all three venvs: **identical on 0.9.12a2, 0.9.12a1 and 0.9.11.post1**,
and identical for a plain mixin base that declares it. Assigning `S.get_delta = fn` after the class body works
on all three (and `reflex/state.py:307` says in so many words that "downstream packages patch those"), so
reflex-enterprise is unaffected — `reflex_enterprise/auth/oidc/state.py:2542` reaches it another way. Not a
regression and not new, but worth one line of documentation next to the `get_delta` extension point, since the
error message names "event handler" for something the user wrote as an override. `deltaapp` uses the post-hoc
assignment for exactly this reason.

### A-3 (benign, app's own fault) — `GET /favicon.ico` 404 in prod

`renderapp`, `deltaapp` and `wrapapp` were hand-written rather than produced by `reflex init` and have no
`assets/` directory, so prod logs one `Failed to load resource: … 404` console error. The campaign recorded
the same for `renderapp`; `failed_requests` and `bad_responses` are empty in every run.

## Known-pre-existing, confirmed unchanged (not re-reported)

* **FINDING-023** — a delta naming a substate the compiled frontend has no dispatcher for latches the page dead.
  `out/a2_mismatch_result.json` on a2: `A_after_load "0"`, `A_after_clicks "0"`, `C_after_clicks "0"`,
  `sent_frames_from_clicks 0`, `events_reach_backend false`, `after_reload_sent_frames 0`, `recv_frames 14`,
  `page_errors []`, and the same two `Cannot process state update: no dispatch function for substate(s)
  "…____backend_only_state"` console errors — field for field the campaign's a1 and prev recordings.
* **FINDING-024** — `GET /api/poke?token=$T&value=x&legacy=1` → bare `Internal Server Error` 500 while the
  control without `legacy=1` returns 200. Step `D5` of `out/a2_disk_result.json`.
* **FINDING-025** — `.states/` empty at every `reflex run` startup, twice in this session: at `D0` (after the
  previous run had left pickles) and again after the debounce-30 restart wiped the six pickles from the
  `drive_disk2.py` run.
* **FINDING-008** — `rx.dropdown_menu.trigger` swallows the child button's `on_click` (`3->3`) while dialog,
  popover, tooltip and hover_card all run it. Same line in the a2 dev log and the a2 prod log as in the
  campaign's a1 and prev logs.
* The two `forms/#6850` "own class_name / own style" FAILs in `mscripts/drive.py` are the driver asserting on
  the inner `<input>` instead of the TextFieldRoot `<div>` — the campaign's own NOTES flag this caveat, and its
  a1 prod log and prev log carry exactly the same two FAILs. Not a behaviour difference.

## Files here

```
NOTES.md                    this file
apps/deltaapp/              new: state-manager x delta matrix probe app
apps/wrapapp/               new: app-wrap nesting probe app (#7218)
scripts/drive_delta.py      delta/value driver (ws frame keys, console, network)
scripts/drive_wraps.py      app-wrap DOM probe
scripts/memo_wraps_probe.py badge + toaster + upload coexistence probe on memo_aschild /memoapp
scripts/cmp_render.py       diff two drive_render.py result JSONs
scripts/getdelta_probe.py   get_delta override matrix across three venvs (A-2)
out/*.json                  every driver result JSON (a2, and the a1 baselines)
logs/*.log                  trimmed server logs and driver stdout
shots/                      screenshots; memo_dev_a2/ and memo_prod_a2/ are the 52-check driver's own
```
