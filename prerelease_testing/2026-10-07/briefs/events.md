# Cluster `events` — finish event-loop/Var leads on 0.10.0a2 with 0.9.12 baselines

Ports: frontend 3460-3479, backend 8460-8479. Work dir: $SB/apps/events/. DEST: /home/user/reflex/prerelease_testing/2026-10-07/events/
Venv: $SB/envs/alpha2; baselines $SB/envs/stable, $SB/envs/alpha.

Read first: $SB/CAMPAIGN_STATE.md, /home/user/reflex/prerelease_testing/2026-10-06/FINDINGS.md "Partial clusters → events_vars" and the "Side lead", /home/user/reflex/prerelease_testing/2026-10-06/briefs/events_vars.md,
/home/user/reflex/prerelease_testing/2026-10-06/events_vars/partial/ (src/evapp, driver/, probes/, out/*/..._report.json — reuse; copy out).

## Do
1. Re-run the full suite (run_suite.py groups sup,nested,thr,vars,typelog,api) on alpha2 dev + prod and on 0.9.12 dev; produce
   a three-column table. Then dig into each not-ok on alpha2:
   - `sup.cancelled_unyielded_mutation`: a superseded (cancelled) handler's mutation after its last yield still becomes visible
     ("aunflushed") — is that a real leak of cancelled work into state? Compare 0.9.12. Minimal repro.
   - `nested.handler_returns_nested_list` / `handler_yields_nested_list`: `TypeError: Your handler ...` — is returning
     `[A, [B, [C]], D]` from a handler supported (docs?) and does 0.9.12 accept it? #7319 flattens CLIENT lists; decide.
   - `temporal.offline_disconnect`: the test never closed the websocket; redo it by SIGSTOP/SIGCONT-ing the backend (or a TCP
     proxy you can pause) so the socket really drops, then check temporal events are dropped and normal ones delivered in order.
   - `api.bg_get_state_get_var_value_sibling`, `api.dataclass_nested_inplace_mutation`: finish them (detail was incomplete).
   - the probe cross-contamination note ("one failing __init__ substate breaks every later root instantiation in the process").
2. Side lead from the sqlmodel verifier: when a chained handler raises (handler A returns State.B, B raises), A's partial delta
   arrives only with the NEXT event instead of with the error; the same failure in the initial on_load delivers immediately.
   Build a minimal repro (dev + prod, alpha2 vs 0.9.12), capture websocket frames with timestamps.
3. #7456 `BackendVarFormatError`: covered by reverify_core; skip. #7465 private attributes inside event handlers
   (`self.__scratch = ...` in a mixin handler; a dunder class attribute used as a constant in a handler) — quick check in
   both dev and prod that handlers still work and vars don't react to them.
4. Anomalies to classify as pre-existing with evidence: UTF-16 string slicing, throttle without trailing call.
Copy artifacts to DEST as you go.
