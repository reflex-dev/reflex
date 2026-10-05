# rv_state_fixes — FINDING-001 (metaclass), FINDING-003 (delta memo), #7230 (router mutation guards), router/event-loop regression sweep
Ports: frontend 3100-3119 / backend 8100-8119 (redis: 8119). Scratch: $SB/reverify/rv_state_fixes/. Notes dir: reverify-0.9.12a2/rv_state_fixes/.

Checks (all on `$SB/envs/a2` unless stated; record a1 (`envs/shared`) and 0.9.11.post1 (`envs/prev`) columns where noted):
1. FINDING-001 / #7211 — `orch_probes/metaclass_probe.py`: a2 must print OK for all three cases and
   `type(rx.State) = reflex_base.vars.base.BaseStateMeta`; a1 prints 2 FAIL (record); prev 3 OK. Then with `envs/enta2`
   (reflex-enterprise 0.9.6a1): `orch_probes/ent_import_probe.py` (relax its venv assert) → all modules and attrs OK,
   BAD = 0, `import reflex_enterprise.auth.oidc.state` works with NO shim (`ent_mcp_oidc/scripts2/oidc_meta_shim.py`
   must not be used anywhere). Also check `rx.State._reflex_state_root is reflex.state.BaseState` and that a reserved
   name declared through a `BaseStateMeta`-derived metaclass still raises `StateValueError`.
2. FINDING-003 / #7212 — `ent_mcp_oidc/verification/2026-09-19-adversarial/pure_delta_memo.py` (copy, drop the
   `/envs/` assert): a2 steps 3/4 True; a1 False; prev True. Then the browser repro: `event_loop/elapp` page `/filtered`
   driven by `event_loop/scripts/s_filtered.py` (+ `scripts/wsdrive.py`) on a2 in dev/memory AND dev + redis (single
   worker) → page shows `secret-1` right after `show` and `secret-3` after round 2, zero console/page/network errors.
   Confirm #6946's savings are intact on a2 with the `/uncached` probe (`event_loop/scripts/s_uncached*.py`, see
   NOTES.md): same delta frame count / key sequence as a1 (24 frames, ~15.3 KB inbound; 0.9.11.post1 ~26 KB).
3. #7168 supersedes and #7145 re-chain: re-run `event_loop/scripts/s_supersede.py` (all shapes) and the recursion
   probe on a2 dev/memory — expect the same 8/8 supersession shapes and zero RecursionError as the campaign recorded.
4. #7230 (NEW in a2, not covered by the campaign) — "nested writes through `self.router` now obey the calling
   StateProxy / ReadOnlyStateProxy mutation guard". Explore as a user, dev/memory and dev/redis, in a small app of
   your own: (a) a `@rx.event(background=True)` handler that assigns through `self.router` (e.g. `self.router.url =
   ...` or a nested field) OUTSIDE `async with self` must raise the same `ImmutableStateError` as a direct field
   write, and INSIDE `async with self` must be allowed and emit the correct `rx_router_*` delta; (b) the same from a
   substate; (c) a plain event handler still reads/writes normally; (d) `get_state()` proxies (`ReadOnlyStateProxy`)
   reject router writes; (e) nothing regressed for ordinary router reads in computed vars / `on_load`. Report the
   exact exception types and delta keys; any crash, hang or console error is a finding.
5. Router regression sweep: re-run the campaign's `router_vars/routerlab` 24-step matrix
   (`router_vars/scripts/drive_router.py`) on a2 dev; compare the per-step router-key sets and frame bytes with the
   campaign's `router_vars/out_dev/records.json` and `logs/matrix_dev.txt` — identical is PASS, any difference is an
   anomaly to explain (a2 changed the delta-recording path and #7230 the router proxy).
Write the pass/fail table for these checks in your NOTES.md and return it in the structured result.
