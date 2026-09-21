# rv_state_fixes — Phase 7 re-verification of reflex 0.9.12a2

Scope: FINDING-001 (state metaclass), FINDING-003 (uncached-var delta memo), #7230 (router
mutation guards, new in a2), and the router / event-loop regression sweep.

Everything below ran from published PyPI packages / the published reflex-enterprise wheel only.
Nothing was installed or run from `/home/user/reflex`, `/home/user/reflex-enterprise` or any other
checkout. Ports used: frontend 3100-3104, backend 8100-8104, redis 8119 (all inside my reserved
range). All servers and redis were stopped at the end (`ports.py` clean).

## Resolved versions

`uv pip freeze --python $SB/envs/<env>/bin/python | grep -i reflex`:

```
# $SB/envs/a2 (the tree under test, Python 3.11.15)
reflex==0.9.12a2  reflex-base==0.9.12a2
reflex-components-code==0.9.6a1  -core==0.9.10a1  -dataeditor==0.9.3a1  -gridjs==0.9.2a1
-markdown==0.9.4a1  -plotly==0.9.7a1  -radix==0.9.10a1  -recharts==0.9.4a1  -sonner==0.9.4a1
-lucide==1.0.4  -moment==0.9.4  -react-player==0.9.2  reflex-hosting-cli==0.1.72

# $SB/envs/enta2 = the same + reflex-enterprise 0.9.6a1 from
#   $SB/wheels/reflex_enterprise-0.9.6a1-py3-none-any.whl  (installed as a file:// URL)
# $SB/envs/shared = reflex 0.9.12a1 + the same component alphas   (the "a1" column)
# $SB/envs/prev   = reflex 0.9.11.post1 + its stable components   (the "prev" column)
```

## Result table

| # | check | prev (0.9.11.post1) | a1 (0.9.12a1) | a2 (0.9.12a2) | verdict |
| --- | --- | --- | --- | --- | --- |
| 1a | `metaclass_probe.py` (3 cases) | 3 OK | **2 FAIL** (metaclass conflict) | **3 OK** | PASS |
| 1b | `type(rx.State)` | `reflex_base.vars.base.BaseStateMeta` | `reflex.istate.validation._StateMeta` | `reflex_base.vars.base.BaseStateMeta` | PASS |
| 1c | `rx.State._reflex_state_root is reflex.state.BaseState` | attr absent | attr absent | **True** | PASS |
| 1d | reserved name through a `BaseStateMeta`-derived metaclass | accepted (pre-#7136) | unreachable (metaclass conflict first) | `StateValueError` | PASS |
| 1e | enterprise import sweep (`ent_import_probe.py`, 23 modules + 13 attrs) | 23/23 | 1 FAIL (`auth.oidc.state`) | **BAD = 0**, no shim | PASS |
| 2a | `pure_delta_memo.py` steps 3/4 | True / True | **False / False** | **True / True** | PASS |
| 2b | `/filtered` browser repro, dev + in-memory | secret-1 / secret-3 | secret-0 / secret-2 | **secret-1 / secret-3** | PASS |
| 2c | `/filtered` browser repro, dev + redis (1 worker) | secret-1 / secret-3 (campaign) | stale (campaign) | **secret-1 / secret-3** | PASS |
| 2d | #6946 savings intact (`/uncached`) | 26 059 B in / 27 frames | 15 274 B / 24 frames | **15 274 B / 24 frames** | PASS |
| 3a | `s_supersede.py`, 8 shapes | see campaign | 8/8 | **8/8, byte-identical output** | PASS |
| 3b | `s_recursion.py` 3000-iteration self-chain | — | 0 RecursionError | **0 RecursionError**, 12.1 s | PASS |
| 4a | #7230 background write through `self.router`, root state | guarded | **BYPASSED** | guarded | PASS |
| 4b | #7230 same from a substate | guarded (but write not delivered) | **BYPASSED** | guarded **and** delivered | PASS |
| 4c | plain handler router read/write | works | works | works | PASS |
| 4d | `ReadOnlyStateProxy` (`rx.get_state`) rejects router writes | rejected | **BYPASSED** | rejected | PASS |
| 4e | router reads in computed vars / `on_load` / nav | works | works | works | PASS |
| 5 | routerlab 24-step matrix vs campaign `logs/matrix_dev.txt` | — | reference | **byte-for-byte identical** | PASS |

Four channels captured on every browser run (server log, console incl. warnings, failed/4xx-5xx
requests, rendered page + screenshots). **Zero** page errors, zero non-benign console messages and
zero failed requests across every a2 run. The only `[ERROR]` lines in the a2 server logs are
`Unexpected exit from worker-1` emitted at the tail when I SIGTERM'd the worker to shut down.

## 1. FINDING-001 / #7211 — state metaclass

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
D=$SB/reverify/rv_state_fixes
cp <campaign>/orch_probes/metaclass_probe.py $D/probes/
cd $D/probes
$SB/envs/a2/bin/python     metaclass_probe.py     # 3 OK
$SB/envs/shared/bin/python metaclass_probe.py     # 2 FAIL
$SB/envs/prev/bin/python   metaclass_probe.py     # 3 OK
$SB/envs/a2/bin/python     extra_meta_probe.py    # this dir: probes/extra_meta_probe.py
# enterprise: assert relaxed to a print, nothing else changed
$SB/envs/enta2/bin/python  ent_import_probe.py
$SB/envs/enta2/bin/python -c "import reflex_enterprise.auth.oidc.state; print('ok')"
```

a2 output:

```
reflex 0.9.12a2 | type(rx.State) = reflex_base.vars.base.BaseStateMeta | BaseStateMeta is type(rx.State): True
OK   metaclass derived from BaseStateMeta: ...
OK   metaclass derived from type(rx.State): ...
OK   mixin=True with BaseStateMeta-derived metaclass
```

`extra_meta_probe.py` on a2: `_reflex_state_root` is `reflex.state.BaseState`; `_get_was_touched`,
`router`, `substates`, `dirty_vars` are all still rejected with `StateValueError` — including when
the class is declared **through** a `BaseStateMeta`-derived metaclass, so #7136's validation
survived the move into `BaseStateMeta.__new__` (`reflex_base/vars/base.py:4156-4184`,
`new_cls._reflex_state_root = new_cls` at 4293). A `mixin=True` class built with a derived
metaclass is usable as a base again.

Enterprise (`envs/enta2`, reflex-enterprise 0.9.6a1 from the offline wheel): all 23 modules and all
13 `rxe` attributes import, **BAD = 0**, and `import reflex_enterprise.auth.oidc.state` succeeds on
its own. No shim is involved: `oidc_meta_shim.py` is not present in the venv, not on `sys.path`,
and not imported by the probe (`grep -rl oidc_meta_shim $SB/envs/enta2/` → only `_virtualenv.pth`,
which is virtualenv's own file; no `sitecustomize`/`usercustomize`).

Note for the record: reflex-enterprise 0.9.6a1 *also* fixed its side —
`reflex_enterprise/auth/oidc/state.py:72` now does `_StateMetaclass = type(rx.State)` at runtime
instead of hard-wiring `BaseStateMeta`. So the enterprise import would pass even without the reflex
fix. The framework-only probe (1a) is the evidence that the reflex fix itself works for any other
downstream metaclass.

## 2. FINDING-003 / #7212 — uncached-var delta memo

```bash
cp <campaign>/ent_mcp_oidc/verification/2026-09-19-adversarial/pure_delta_memo.py $D/probes/
cd $D/probes
for e in a2 shared prev; do $SB/envs/$e/bin/python pure_delta_memo.py; done   # out/pure_delta_memo.out
```

a2: step3 = True, step4 = True (`shared_label` is delivered as soon as the downstream `get_delta`
filter stops dropping it). a1: False / False. prev: True / True.

Browser repro (the campaign's `event_loop` app and driver, unmodified):

```bash
mkdir -p $D/elapp && cd $D/elapp
REFLEX_TELEMETRY_ENABLED=false $SB/envs/a2/bin/reflex init --template blank
cp <campaign>/event_loop/elapp/elapp/elapp.py $D/elapp/elapp/elapp.py
cp <campaign>/event_loop/scripts/*.py $D/scripts/
REFLEX_TELEMETRY_ENABLED=false $SB/envs/a2/bin/reflex run \
  --frontend-port 3100 --backend-port 8100 --loglevel debug > $D/logs/dev_a2.log 2>&1 &
cd $D/scripts && export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 PYTHONPATH=.
$SB/envs/driver/bin/python s_filtered.py  http://localhost:3100 $D/out/dev_a2
$SB/envs/driver/bin/python s_uncached.py  http://localhost:3100 $D/out/dev_a2
$SB/envs/driver/bin/python s_supersede.py http://localhost:3100 $D/out/dev_a2
$SB/envs/driver/bin/python s_recursion.py http://localhost:3100 $D/out/dev_a2
# then the same app + `REFLEX_REDIS_URL=redis://localhost:8119` (redis-server --port 8119 --save '')
$SB/envs/driver/bin/python s_filtered.py  http://localhost:3100 $D/out/dev_a2_redis
```

dev/in-memory (`out/filtered_a2_dev.txt`) and dev+redis (`out/filtered_a2_redis.txt`) are identical
and correct:

| step | a1 (campaign) | a2 memory | a2 redis |
| --- | --- | --- | --- |
| load | secret-0 | secret-0 | secret-0 |
| bump while hidden | secret-0 | secret-0 | secret-0 |
| **show** | secret-0 (stale) | **secret-1** | **secret-1** |
| bump (n=2) | secret-2 | secret-2 | secret-2 |
| hide, bump (n=3), show | secret-2 (stale) | **secret-3** | **secret-3** |

The delta right after `show` is `{fl: ['secret_rx_state_', 'visible_rx_state_']}` on a2 (a1 sent
`{fl: ['visible_rx_state_']}`). Zero console messages, zero page errors, zero failed requests in
both transports.

**#6946's savings are intact.** `analyze.py` over the a2 `/uncached` frame dump gives
**15 274 inbound bytes, 24 delta frames (14 770 B)** — the exact numbers the campaign recorded on
a1, against 26 059 B / 27 frames on 0.9.11.post1. Diffing the per-frame key sequence a1 vs a2
(`out/uncached_a2.analyze.txt`) shows only the substate key *ordering* inside the three 3 318-byte
hydrate frames (same keys, same byte count) — process-to-process dict ordering, not a behaviour
change. `do_nothing` still produces no frame; the unrelated `nonce` bump is still a 98 B delta.

## 3. #7168 supersedes / #7145 recursion

`out/dev_a2_supersede.stdout.txt` is **byte-identical** to the campaign's
`event_loop/out/supersede.txt` — all 8 shapes, including the three #7041/#7168 fixes
(shared superseding child cancelled across root chains; restarted poll loop yields 8 ticks not 12;
stale chain's invocation dropped). `out/dev_a2_recursion.stdout.txt`: the 3000-iteration `on_load`
self-chain completes in 12.1 s, the superseding-root loop survives client-side nav away/back,
restart and hard reload; `grep -cE "RecursionError|Exception in callback|Traceback"` over
`logs/dev_a2.log` = **0**.

## 4. #7230 — router mutation guards (new in a2, not covered by the campaign)

My own app: `app/r7230/r7230.py` (init'd with `reflex init --template blank`, then the module file
replaced), driven by `scripts/s_r7230.py`. Run on a2 dev/in-memory (3101/8101), a2 dev+redis
(3101/8101 with `REFLEX_REDIS_URL=redis://localhost:8119`), a1 (3103/8103) and 0.9.11.post1
(3104/8104) — the same source file imports and runs unchanged on all three versions.

Exception types and delta keys observed **on a2** (identical in memory and redis):

| shape | a2 result |
| --- | --- |
| bg, outside `async with self`: `self.ticks = 1` | `reflex_base.utils.exceptions.ImmutableStateError: Background task StateProxy is immutable outside of a context manager.` |
| bg, outside: `self.router.page.params["bg"] = ...` | **same `ImmutableStateError`** |
| bg, outside: `self.router.headers.raw_headers[...] = ...` | **same `ImmutableStateError`** |
| bg, outside: `self.router.url = ...` | `dataclasses.FrozenInstanceError: cannot assign to field 'url'` (RouterData is a frozen dataclass — rejected on every version) |
| bg, **inside** `async with self`: `self.router.page.params[...] = ...` | allowed; delta `{'reflex___state____state': ['rx_router_page_rx_state_'], '<...>__root_s': ['route_view_rx_state_', ...]}` — the router field dirties on the **root** state, the dependent computed var updates, and the value round-trips (page re-renders with the new params) |
| bg, inside: `self.router.headers.raw_headers[...] = ...` | `TypeError: '_FrozenDictStrStr' object does not support item assignment` (headers are immutable by type; same on prev) |
| reference captured inside, written after the block | `ImmutableStateError` |
| `async with params:` on a captured container | allowed, writes through (`{'a','b','nested'}`), and dirties `rx_router_page` |
| substate background task, all of the above | same results; delta carries `rx_router_page` on the root plus the substate's own keys |
| `ro = await rx.get_state(token, RootS)` → `ro.router.page.params[...] = ...` | `ImmutableStateError` |
| `ro.router.headers.raw_headers[...] = ...` | `ImmutableStateError` |
| `ro.ticks = 99` | `NotImplementedError: This is a read-only state proxy.` |
| `async with ro.router.page.params:` | `ImmutableStateError: This is a read-only state proxy.` |
| plain (foreground) handler, root and substate | reads and writes router params normally, delta as expected |
| computed var reading `router.route_id` / `url.path` / `page.params`, `on_load` reading `url.path` and `headers.raw_headers`, client-side nav, direct load with query | all correct on `/` and `/other?q=…` |

**This is a regression fix, not a new hardening.** The same app on the two baselines:

| shape | prev 0.9.11.post1 | a1 0.9.12a1 | a2 0.9.12a2 |
| --- | --- | --- | --- |
| bg outside → `router.page.params[...]` | `ImmutableStateError` | **ALLOWED** | `ImmutableStateError` |
| bg outside from a substate | `ImmutableStateError` | **ALLOWED** | `ImmutableStateError` |
| escaped reference written after the block | `ImmutableStateError` | **ALLOWED** | `ImmutableStateError` |
| `ReadOnlyStateProxy` router write | `ImmutableStateError` | **ALLOWED** | `ImmutableStateError` |
| `async with ro_params:` (read-only) | `ImmutableStateError` | **ALLOWED** | `ImmutableStateError` |

So 0.9.12a1 (the router split, #7068) silently dropped the background-task lock and the read-only
proxy for every nested write through `self.router`; a2 restores 0.9.11.post1's behaviour. a2 is
also *better* than prev in one place: a substate's in-lock router write is delivered to the client
on a2 (`rx_router_page` + the dependent computed var) whereas on prev it produced no delta at all
and the page kept the old params. Evidence: `out/r7230_a2.stdout.txt`,
`out/r7230_a2_redis.stdout.txt`, `out/r7230_a1.stdout.txt`, `out/r7230_prev.stdout.txt`,
`shots/a2_r7230_after.png`, `shots/a1_r7230_after.png`.

One non-guard difference worth knowing: on prev, `self.router.url = ...` from a background task
raises `ImmutableStateError` (the whole `router` was one mutable-proxied field), while on a1/a2 it
raises `dataclasses.FrozenInstanceError` because the composed `RouterData` is frozen. Either way
the assignment is rejected, and it is rejected inside the lock too — assigning `router.url` was
never a supported write path.

## 5. Router regression sweep — routerlab 24-step matrix

```bash
mkdir -p $D/routerlab && tar -C <campaign>/router_vars/routerlab -cf - . | tar -C $D/routerlab -xf -
cd $D/routerlab && REFLEX_TELEMETRY_ENABLED=false $SB/envs/a2/bin/reflex run \
  --frontend-port 3102 --backend-port 8102 --loglevel debug > $D/logs/dev_routerlab_a2.log 2>&1 &
cd $D/scripts && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drive_router.py http://localhost:3102 $D/out/routerlab_a2 \
  > $D/logs/drive_router_a2.log 2>&1
$SB/envs/driver/bin/python analyze_frames.py $D/out/routerlab_a2/ws_frames.txt > $D/out/matrix_a2.txt
diff <campaign>/router_vars/logs/matrix_dev.txt $D/out/matrix_a2.txt    # empty
```

`diff` is **empty** (`out/matrix_diff.txt`, 0 lines): all 24 steps, every sent event, every delta's
byte size, every per-state key list and every router-key set are byte-for-byte what the campaign
recorded on a1. 29 console messages, all benign; no page errors; no >=400 responses.

The rendered snapshots also match: comparing the 24 `snapshot` blocks of my `records.json` against
the campaign's, the only differences are the per-run `client_token` and socket.io `session_id`
(`out/routerlab_snapshot_diff` analysis in `out/routerlab_diff.txt`) — every computed var,
route id, param dict, fragment, memo and ComponentState value is identical.

**Explained discrepancy (not a framework difference):** the campaign's
`router_vars/out_dev/records.json` has an empty `deltas` list for 17 of the 24 steps, while its own
`logs/matrix_dev.txt` — derived from `out_dev/ws_frames.txt` of the *same* run — has them, with
exactly the byte counts my a2 run produced. The campaign's `logs/drive_dev.log` likewise shows no
`delta …B router_keys=` lines for those steps. So the in-process per-step capture in that run
under-recorded; the websocket dump is the complete record, and it agrees with a2 exactly. I
compared against `matrix_dev.txt` for the verdict and note the `records.json` gap here so nobody
reads it as a behaviour change.

## Benign / known things observed, not reported as findings

- `DeprecationWarning: @rx.memo on memo_toast_button without explicit annotations` from the
  campaign's `elapp` — the app's own code, unchanged since the campaign.
- `[ERROR] Unexpected exit from worker-1` at the tail of every server log: my own SIGTERM.
- `[c1][log] Disconnect websocket on page navigation` console line during nav-heavy scripts.
- `'_FrozenDictStrStr' object does not support item assignment` when writing
  `router.headers.raw_headers` inside a lock: headers are intentionally immutable, same on prev.

## Cleanup

All five app servers (3100-3104 / 8100-8104) and the redis instance on 8119 were stopped; a final
`uv run --no-project python $SB/bin/ports.py` shows nothing of mine listening.
