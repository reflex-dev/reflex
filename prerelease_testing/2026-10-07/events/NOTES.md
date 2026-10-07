# Cluster `events` — event loop / Var leads on reflex 0.10.0a2 (2026-10-07)

Resumed cluster (the first agent ran the a2 dev+prod suites at 07:4x UTC, then stopped at a spend limit;
everything else below was done 11:30–13:00 UTC). Brief: `../briefs/events.md`. Item board: `../board/items/events.md`.

Versions: **reflex 0.10.0a2** (+ the a2 train sub-packages) in the shared venv `$SB/envs/alpha2`;
baselines **0.9.12** (`$SB/envs/stable`) and **0.10.0a1** (`$SB/envs/alpha`). All three shared venvs already
contain `greenlet` (orchestrator, N-001); this cluster created **no venvs of its own** and installed nothing.
Python 3.12, Chromium 141 headless via Playwright 1.63 (`$SB/envs/driver`), Node 22 / bun 1.4.2, redis-server 7.

## Layout

| path | what |
|---|---|
| `src/evapp/` | the cluster app (one app, pages `/sup /deco /nested /throttle /vars /typelog /api /bind /priv`). 0.10-only features are guarded by `IS_ALPHA` so the same source compiles on 0.9.12 |
| `src/mini/` | minimal repros: chained/direct/async/generator/background handlers that raise, an `on_load` that raises, two `supersedes=True` handlers, and three prerender pages for an emoji string (`/emoji-plain`, `/emoji-len`, `/emoji-rev`) |
| `driver/harness.py` | Playwright harness: console/pageerror/requestfailed/4xx-5xx/websocket-frame capture, screenshots |
| `driver/run_suite.py` + `driver/tests_*.py` | the evapp suite (groups `sup,nested,thr,thr:PROXY,vars,typelog,api,bind,priv`) |
| `driver/drive_mini.py` | the mini driver (cases `a_returns_b_raises a_yields_b_raises direct_raises async_raises gen_yield_then_raise bg_raise_inside bg_raise_after onload_initial onload_via_nav sup_cancel sup_split emoji`) |
| `tools/tcpproxy.py` | pausable TCP proxy between browser and backend (`api_url` points at it) so a test can really drop the websocket (`echo down > pids/<label>.proxystate`) |
| `tools/make_table2.py`, `tools/mini_summary.py` | report -> markdown table / per-case summary |
| `bin/start.sh stop.sh wait_up.sh suite.sh ports.sh copy_*.sh` | server lifecycle + suite runner (see "Rerun") |
| `probes/` | backend-only probes: `priv/` (#7465), `initfail/` (failing substate `__init__`), `stateapi/` (23 state-API edge cases), `slicefuzz/` (6890 slice forms vs Python) |
| `out/` | every report JSON, suite transcript, screenshots, gzipped websocket frames; `out/suite_table.md` is the cross-version table |
| `logs/` | server logs of every run (`EVLOG`/`MINI` marker lines are the app's own) |
| `prev_out/` | 10-06 results reused as baselines (0.9.12 nested group, 0.10.0a1 dev full suite) |

## Rerun

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad   # your scratch root
W=$SB/apps/events2                     # copy this directory (src driver tools bin probes) there
# ports: evapp dev FE 3460 / BE 8460 / proxy 8462; evapp prod 8465 (FE=BE) / proxy 8466
#        mini  dev FE 3470 / BE 8470 / proxy 8472; mini  prod 8475 / proxy 8476; redis 8479
bash $W/bin/start.sh alpha2 dev  a2_dev  evapp          # copies src/evapp to run/a2_dev, starts proxy + `reflex run`
bash $W/bin/wait_up.sh http://localhost:3460/           # polls up to 6 min
bash $W/bin/suite.sh a2_dev http://localhost:3460 8460  # all groups -> out/a2_dev/a2_dev_{suite.txt,report.json,wsframes.json}
bash $W/bin/stop.sh a2_dev                              # kills the process group + proxy, lists leftover listeners

bash $W/bin/start.sh alpha2 prod a2_prod evapp && bash $W/bin/wait_up.sh http://localhost:8465/
bash $W/bin/suite.sh a2_prod http://localhost:8465 8465 && bash $W/bin/stop.sh a2_prod
# 0.9.12: same with venv `stable` (labels s_dev / s_prod). Run the `nested` group in its OWN invocation on
# 0.9.12 (`bash $W/bin/suite.sh s_dev_nested http://localhost:3460 8460 nested`): its event storm crashes the
# Playwright driver, every later case then fails with "Connection closed".

# mini app (minimal repros), dev / prod / redis:
bash $W/bin/start.sh alpha2 dev mini_a2_dev mini && bash $W/bin/wait_up.sh http://localhost:3470/
cd $W/driver && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drive_mini.py http://localhost:3470 $W/out/mini_a2_dev mini_a2_dev [case,case]
$SB/envs/driver/bin/python $W/tools/mini_summary.py $W/out/mini_a2_dev/mini_a2_dev_report.json
bash $W/bin/stop.sh mini_a2_dev
# prod: `start.sh <venv> prod <label> mini`, base http://localhost:8475
# redis: redis-server --port 8479 --save '' --appendonly no &   then `start.sh <venv> dev <label> mini redis`
#        (sets REFLEX_REDIS_URL=redis://localhost:8479; /_health reports "redis":true)

# probes (backend only, run from the probe dir, never from the checkout):
cd $W/probes/stateapi && bash run_probe.sh alpha2 dev > out_alpha2_dev.jsonl   # and prod / alpha / stable
cd $W/probes/priv && $SB/envs/alpha2/bin/python priv_probe.py alpha2 dev
cd $W/probes/initfail && $SB/envs/alpha2/bin/python initfail_probe.py alpha2 dev valueerror   # undeclared|dunder|valueerror
cd $W/probes/slicefuzz && $SB/envs/alpha2/bin/python slice_fuzz.py alpha2                     # writes+runs fuzz.js (node)
# table:
$SB/envs/driver/bin/python $W/tools/make_table2.py "a2 dev=$W/out/a2_dev/a2_dev_report.json" ...
```
Every app/probe asserts the venv it imports reflex from. Never run them with `/home/user/reflex` as cwd.
Do not export `NO_PROXY` into the server's environment (only into the driver's).

## Cross-version suite table (`out/suite_table.md`)

Columns: a2 dev/prod and 0.9.12 dev/prod run today (11:46–12:16 UTC for 0.9.12; 07:4x UTC for a2);
0.9.12's `nested.*` column is the 10-06 per-case run (`prev_out/stable_dev/stable_dev_nested_report.json`) —
today's rerun reproduced the same storm (`match_list_branch` 244,718 and `deep50_nested_match` 729,087 websocket
frames sent, then the Playwright driver died, `out/s_dev_nested/s_dev_nested_suite.txt`). a1 dev is the 10-06 run.

| check | a2 dev | a2 prod | 0.9.12 dev | 0.9.12 prod | a1 dev (10-06) |
|---|---|---|---|---|---|
| sup.slow_rapid_clicks / background_plus_supersedes / bg_cancel_while_holding_lock / chained_child_cancelled / component_state_* | pass | pass | pass | pass | pass |
| sup.cancelled_unyielded_mutation | anomaly | anomaly | anomaly | anomaly | anomaly |
| sup.cpu_bound_non_yielding / sync_generator_blocking_sleep | info | info | info | info | info |
| deco.late_marker_before_first_use, functools_wraps_inner/outer, mixin_background_two_substates, pkg_redecorated_early/late | pass | pass | pass | pass | pass |
| deco.late_marker_after_is_background_read | fail | fail | pass | pass | fail |
| nested.match_list_branch, deep50_nested_match, backend_failure_mid_nested_list, malformed_event_mid_nested_list, call_script_throws_mid_nested_list, run_script_mid_nested_list | pass | pass | fail (event storm) | - | pass |
| nested.backend_failure_mid_list_flat, handler_returns_flat_with_failing, call_script_callback_list | pass | pass | pass | - | pass |
| nested.handler_returns_nested_list / handler_yields_nested_list | fail | fail | fail | - | fail |
| nested.prevent_default_inside_nested_list / issue7319_ctrl_b_shortcut | pass | pass | - | - | pass |
| throttle.throttle200_supersedes_typing / debounce300_supersedes_typing | pass | pass | pass | pass | pass |
| throttle.leading_edge_drops_final_value | anomaly | anomaly | anomaly | anomaly | anomaly |
| temporal.sigstop_3s_socket_still_open | pass | pass | pass | pass | pass |
| temporal.proxy_drop_socket_closed (real disconnect) | pass | pass | pass | pass | - (old test: fail, socket never closed) |
| vars.* (7 Var states, 20 checks each) | pass | pass | fail (`items[-1::-1]` empty, #7326) | fail (same) | pass |
| vars.*.utf16_vs_codepoints | anomaly | anomaly | anomaly | anomaly | anomaly |
| vars.deep_equals_state_client_computed_cond_match | pass | pass | n/a (0.10 feature) | n/a | pass |
| t_vars [console]: React #418 hydration error | - | anomaly | - | anomaly | - |
| typelog.counts | info | info | info | info | info |
| api.bg_get_state_get_var_value_sibling, raw_setvar_events, reset_client_storage_substates, dataclass_nested_inplace_mutation | pass | pass | pass | pass | pass |
| api.undeclared_attribute_assignment | info (raises) | info (silently set) | info (raises) | info (raises) | info (raises) |
| bind.instance_access_and_inheritance | info | info | info (differs) | info (differs) | info |
| bind.foreach_args_0_to_5_and_lambdas | pass | pass | pass | pass | pass |
| priv.dunder_attrs_in_handlers (#7465) | pass | pass | fail (SetUndefinedStateVarError) | fail (same) | - |

Full per-row table: `out/suite_table.md`. Per-check details: `out/<label>/<label>_suite.txt` / `_report.json`.

## What each lead turned out to be

### 1. `sup.cancelled_unyielded_mutation` — real, pre-existing, and state-manager dependent
Minimal repro `src/mini` (`SupMini.work` / `work_split`, cases `sup_cancel`, `sup_split`).
A `@rx.event(supersedes=True)` handler appends `a:start`, `yield`s, appends `a:after-yield`, then sleeps;
a second click supersedes (cancels) it during the sleep.
- **Default (disk) state manager, dev and prod, a2 = a1 = 0.9.12:** the cancelled call's post-yield mutation is
  committed: it is sent inside the superseding call's first delta and survives a reload
  (`out/mini_a2_dev`, `sup.cancelled_mutation_after_last_yield` final `a:start,a:after-yield,b:start,b:after-yield,b:end`).
  `work_split` proves it is the dirty-var set, not just the shared list: the superseding call (label b) never
  touches `log`, yet its delta is `{"other":"b-ran","log":["a:start","a:after-yield"]}` and a reload still shows
  `a:start,a:after-yield`.
- **Redis state manager, a2 = 0.9.12:** the opposite — the whole cancelled event is discarded, *including the
  `a:start` its first `yield` already delivered to the browser*. The browser keeps showing `a:start` until a reload
  shows `""` (`out/mini_a2_dev_redis`, `out/mini_s_dev_redis`, `sup.split_cancelled_mutation_surfaces`:
  `after_b.log="a:start"`, `after_reload.log=""`).
- Verdict: not a 0.10 regression. Semantics of a cancelled superseded handler are undefined in the docs and differ
  between state managers (issue E-2/E-3 below).

### 2. `nested.handler_returns_nested_list` / `handler_yields_nested_list` — unsupported, identical on all versions
A backend handler returning `[A, [B, [C]], D]` (or yielding `[Y1, [Y2]]`) raises
`TypeError: Your handler NestState.ret_nested must only return/yield: None, Events or other EventHandlers referenced by their class ... Returned events of types <class 'reflex_base.event.EventSpec'>, <class 'list'>, <class 'reflex_base.event.EventSpec'>.`
from `base_state_processor.py:_check_valid_yield` on a2 dev+prod and a1; 0.9.12 raises the identical message
(`prev_out/stable_dev_nested.txt`). The chaining docs (`docs/events/chaining_events.md`, `yield_events.md`) only
show single events; flat lists work everywhere (`handler_returns_flat_with_failing` pass). #7319 flattens *client*
(component trigger) lists only, which all pass on a2 and storm on 0.9.12. The 10-06 note "0.9.12 fails differently"
is wrong: it is the same TypeError. The test expectation was wrong; no finding.

### 3. temporal events across a real disconnect — pass on all versions
The 10-06 `temporal.offline_disconnect` never closed the socket (Playwright `set_offline` does not drop an open
websocket). Redone with the pausable proxy (`tests_thr.py:t_temporal_proxy_drop`): the browser's websocket closes
0.1 s after the proxy goes down, two `temporal=True` and two normal clicks are made while down, the proxy comes
back: hits are exactly `N3,N4` in order (temporal dropped, normal queued and delivered 0.45–0.54 s after
reconnect), and a fresh temporal click after reconnect is delivered (`N3,N4,T1`). Identical on a2 dev/prod and
0.9.12 dev/prod. A 3 s SIGSTOP of the backend does *not* disconnect (ping interval 25 s), so temporal events are
delivered late in that case (`T1,N1,T2,N2`) — expected. Console errors during the drop are the intentional
`WebSocket ... ERR_CONNECTION_RESET` reconnect attempts.

### 4. `api.bg_get_state_get_var_value_sibling` and `api.dataclass_nested_inplace_mutation` — pass
Both pass on a2 dev+prod and 0.9.12 dev+prod (the 10-06 a1 "fail" was an incomplete run; the a1 full run passed).
In a background task `await self.get_var_value(Sibling.x)` *outside* `async with self` raises
`ImmutableStateError` on every version (inside the lock: `in=10 in2=11`, sibling UI updates to 11). Dataclass var
with nested list mutated in place twice: `[0,1]` / `[[1,7,7]]`, `get_value()` and `dict()` both return the `Box`
dataclass, a second session still sees the defaults.

### 5. "one failing `__init__` substate breaks every later root instantiation" — by design, all versions
`probes/initfail/out_all.jsonl` (3 venvs x dev/prod x 3 kinds): a substate whose `__init__` raises makes every
`State()` construction raise afterwards, because the root eagerly builds the whole substate tree. Same on 0.9.12,
a1, a2. Only difference: an undeclared `self._init_ran = True` in `__init__` raises
`SetUndefinedStateVarError` in 0.9.12 dev+prod and 0.10 dev, but not in 0.10 prod (documented #7312 change);
a mangled `self.__init_ran` never raises (#7465). Not a cross-contamination bug.

### 6. Side lead: a raising handler's state changes arrive with the NEXT event — real, pre-existing
`src/mini` + `drive_mini.py` (cases `a_returns_b_raises a_yields_b_raises direct_raises async_raises gen_yield_then_raise onload_*`).
Websocket frames (seconds after the click; the "next event" is a `ping` click 3 s later):

| case (disk state manager) | a2 dev | a2 prod | a1 prod | 0.9.12 dev | 0.9.12 prod |
|---|---|---|---|---|---|
| A sets `status`, returns B; B appends `B-partial` and raises: `status` delta | +0.055 | +0.057 | +0.045 | +0.041 | +0.059 |
| ... error toast | +0.055 | +0.058 | +0.058 | +0.045 | +0.062 |
| ... `B-partial` delta | +3.21 (with ping) | +3.21 (with ping) | +3.15 (with ping) | +3.16 (with ping) | +3.17 (with ping) |
| handler sets `status` then raises (sync or async): toast | +0.079 | +0.046 | +0.060 | +0.048 | +0.051 |
| ... `status` delta | +3.31 (with ping) | +3.09 (with ping) | +3.23 (with ping) | +3.15 (with ping) | +3.16 (with ping) |
| `on_load` sets `load_note` then raises (initial load and client nav) | delivered with `is_hydrated:true` (+0.06–0.5 s) | same | same | same | same |

So it is not specific to chaining: **any foreground handler that raises leaves its mutations in the state
(persisted — a reload shows them) but sends no delta**; the browser shows the toast with stale values until some
unrelated event flushes the dirty vars (`out/mini_a2_dev_reload`). `on_load` "works" only because the hydrate
chain's final `is_hydrated=True` delta flushes everything. Background tasks are consistent (changes delivered with
the error; `bg_raise_inside`, `bg_raise_after`, `out/mini_*_bg`).
**Under Redis** (a2 = 0.9.12, `out/mini_a2_dev_redis`, `out/mini_s_dev_redis`, `out/*_redis_bg`) the failed
event's changes are instead dropped: never delivered, not persisted — but changes the event *already delivered*
are dropped too: `gen_yield_then_raise` shows `status=gen-flushed` (yielded) in the browser, reload shows `idle`;
`bg_raise_inside` (raise inside `async with self`) shows `bg-inside-partial`, reload shows `idle`; `on_load`
partial is never shown. Same on 0.9.12 → pre-existing, not a regression (issues E-1, E-2).

### 7. #7465 private attributes in handlers — fixed, dev and prod
`/priv` (evapp) + `probes/priv`. On a2 dev and prod: a mixin handler assigning `self.__scratch` (mangled
`_PrivMixin__scratch`) works for both consumers independently (`scratch=SA limit=2`, `scratch=SB limit=2`;
read-back `read=SA`/`read=SB`); a class dunder constant `__LIMIT = 3` caps the counter; `__version__ = "v1"` reads
back; `self.__last_seen = v` alone sends **zero** websocket frames and a computed var reading it via `getattr`
stays `view last=unset` (vars do not react, as documented); the explicit `__counter: rx.Field[int] = rx.field(0)`
is a real backend var (`_PrivF__counter` in `get_fields()`, dirty, computed view updates to 2); no backend
exceptions. 0.9.12 dev **and prod** raise `SetUndefinedStateVarError: The state variable '_PrivMixin__scratch' has
not been defined in 'PrivA'` for the mixin assignment; a1 raises it in dev only. Plain private attributes are
pickled with the state (`pickle_roundtrip_last_seen='P'`), i.e. they persist across events, on every version.

### 8. Pre-existing anomalies, classified
- **String Vars use UTF-16 code units** (JS semantics): `"a😀b".length()` renders `4` (Python 3) and `[::-1]`
  splits the surrogate pair (`b��a`). 0.9.12, a1, a2, dev and prod alike.
  **New detail:** in prod the prerendered HTML cannot carry lone surrogates, so the page HTML has `EF BF BD EF BF BD`
  where the client computes `\uDE00\uD83D`, and React throws **minified error #418 (text hydration mismatch)** —
  `src/mini` `/emoji-rev` (only that page; `/emoji-plain` and `/emoji-len` are clean) and evapp `/vars`, on a2,
  a1 and 0.9.12 prod; not in dev (no prerender). Issue E-4.
- **Throttle has no trailing call**: typing 20 chars at 30 ms with `throttle=200` delivers 3–4 leading-edge
  values; the final value never reaches the backend. Documented ("Throttled events are discarded. There is no
  eventual delivery ...", `docs/events/event_actions.md`). All versions. Not a finding.

### 9. Other observations
- `deco.late_marker_after_is_background_read` fails on a2/a1, passes on 0.9.12: setting
  `fn._reflex_background_task = True` after `State.handler.is_background` was read is ignored and the handler runs
  in the foreground with no warning. Documented in the a1 reflex-base changelog (#7370: "read once per handler, so
  mark the function before the handler is first used"). `probes/stateapi` shows the same for `supersedes`, and that
  the app's own telemetry walk (`_walk_state_features`) reads `is_background` too. Marking before first read
  (`late_marker_before_first_use`), `functools.wraps` wrappers in either order, mixins, and
  `rx.event(State.h.fn, background=True)` re-decoration all work.
- `bind.instance_access_and_inheritance`: in a background task, calling an inherited handler as a method
  (`self.bump_parent()`) *outside* `async with self` raises `ImmutableStateError` on 0.10 (a1, a2), while 0.9.12
  silently performed the write without the lock (`p_count` 3 vs 2 and `bg_outside=no-error`). Inside the lock,
  `type(self)` in the called handler is `StateProxy` on 0.10 (0.9.12: the state class). Safer, but not spelled
  out in the changelog beyond "EventHandler binds to the state that declares it" (issue E-5, low).
- `typelog.counts` (20 events each): dev on all versions logs the inner-type error of `bad_inner` (`list[int]`
  returning `["s1"]`) 20x, `bad_outer` 20x, the uncached var 21x per segment and the wrong inner assignment 20x;
  a2 **prod** logs only outer-type errors (`bad_outer` 20x, `nums="notalist"` 20x, inner 0x) while 0.9.12 prod still
  walks elements — the documented #7353 change. Values render unchanged.
- `api.undeclared_attribute_assignment`: a2 prod silently accepts `self.undeclared_attr = 42` (kept on the
  instance, read back `42` by the next event, not in `dict()` or any delta); dev and 0.9.12 dev+prod raise
  `SetUndefinedStateVarError` — documented #7312 breaking change.
- `api.raw_setvar_events`: raw `setvar` for a backend var / nonexistent var / computed var each raise
  `AttributeError: 'ApiSV' object has no attribute 'set__secret'` (etc.) and leave state untouched; setting
  `is_hydrated=False` via `setvar` keeps the page interactive. Same on all versions.
- `probes/stateapi` (23 checks): a2 dev/prod output is identical to a1; the differences from 0.9.12 are the
  documented 0.10 changes (shadowing now allowed, `is_hydrated` name allowed, handler binding, read-once markers).
- `probes/slicefuzz` (#7326): 6890 slice forms (literal / Var bounds / Var step / all-Var, list and string) match
  Python exactly on a2 and a1; 0.9.12: 204 mismatches + 3180 `RecursionError`s (`probes/slicefuzz/out_*.txt`).
- `vars.deep_equals_*` (#7208) pass in dev and prod; `HookProbe` (`Var._replace(_var_data=...)`, #7256) renders.

### Benign / known noise seen
favicon 404 in prod; intentional `WebSocket ... ERR_CONNECTION_RESET/ERR_SOCKET_NOT_CONNECTED` errors while the
proxy is down; `Warning: rx._x contains experimental features`; the implicit Radix Themes `DeprecationWarning`;
compile progress bar overshoots (`Compiling ... 20/19`, `30/29`) on 0.9.12 and a2 alike;
`[ERROR] Unexpected exit from worker-1` in dev logs (0.9.12 and a2) when `stop.sh` SIGTERMs the whole process
group; the frontend exception handler logs `TypeError: Cannot create property 'router_data' on number '5'` for the
deliberately malformed event (`rx.Var.create(5)` in an event list) on 0.10 (0.9.12 storms instead).

## Issues (all pre-existing; no a2-only regression found in this cluster)

**E-1 (medium, pre-existing): a handler that raises sends no delta; its changes appear only with the next event (disk/memory state manager).**
Repro: `src/mini`; `bash bin/start.sh alpha2 dev mini_a2_dev mini`; open `http://localhost:3470/`, click
"direct raise" (`ChainState.direct_raises`: `self.status = "direct-partial"; raise RuntimeError`). The error toast
appears, `status` stays `idle`. Click "ping": `status` becomes `direct-partial`. Driver:
`drive_mini.py http://localhost:3470 <out> <label> direct_raises,a_returns_b_raises,gen_yield_then_raise`.
Evidence: frame table in section 6; `out/mini_{a2_dev,a2_prod,a1_prod,s_dev,s_prod}/*_report.json`
(`first_recv_frame_with_marker.after_ping=true`).

**E-2 (medium, pre-existing): Redis state manager discards an event that fails or is superseded, including changes it already delivered to the browser.**
Repro: `redis-server --port 8479 --save '' --appendonly no &`; `bash bin/start.sh alpha2 dev r mini redis`;
click "gen yield then raise" (`status="gen-flushed"; yield; ...; raise`): the browser shows `gen-flushed`; reload:
`idle`. Also "split a" then "split b" within 1 s: browser shows `a:start`, reload shows nothing; "bg raise inside":
browser shows `bg-inside-partial`, reload shows `idle`. Driver cases `gen_yield_then_raise,sup_split,bg_raise_inside`.
Evidence: `out/mini_a2_dev_redis`, `out/mini_s_dev_redis`, `out/mini_*_redis_bg` (`client_server_diverged`).

**E-3 (low, pre-existing): a superseded (cancelled) handler's mutations after its last `yield` are committed and ride along with the superseding call's delta (disk/memory).**
Repro: mini "split a", wait 0.6 s, "split b": delta `{"other":"b-ran","log":["a:start","a:after-yield"]}`;
reload keeps `a:after-yield`. Evidence `out/mini_*/..._report.json` `sup.split_cancelled_mutation_surfaces`.
Opposite of E-2 under Redis.

**E-4 (low, pre-existing): string Var ops count UTF-16 code units; in prod a split surrogate pair causes React hydration error #418.**
Repro: mini `bash bin/start.sh alpha2 prod p mini`, open `http://localhost:8475/emoji-rev/` (renders
`EmojiState.emoji[::-1]` for `"a\U0001f600b"`): pageerror `Minified React error #418; ...args[]=text`; the HTML
contains `b\xef\xbf\xbd\xef\xbf\xbda`. `/emoji-len` renders `4`. Evidence `out/mini_*_prod` `prerender.emoji_hydration`,
evapp `out/a2_prod`/`out/s_prod` `t_vars [console]`.

**E-5 (low, behavior change since 0.10.0a1, not a regression in correctness): calling another handler as a method from a background task.**
`self.bump_parent()` outside `async with self` now raises `ImmutableStateError` (0.9.12 wrote without the lock);
inside the lock the called handler sees `type(self) is StateProxy`. evapp `/bind`, button "child.bg_call_parent";
`out/*/..._report.json` `bind.instance_access_and_inheritance.bind-bg-parent`.

## Not covered
- A 0.9.12 dev run of the `nested` group in one process (the 0.9.12 storm kills the Playwright driver after the 3rd
  case; the 10-06 per-case 0.9.12 results are used instead and today's partial rerun matches them).
- a1 prod of the evapp suite (a1 dev from 10-06 and a1 prod of the mini repros only).
- Redis in prod mode (the state-manager findings were run in dev with Redis; the disk-manager ones in dev and prod).
