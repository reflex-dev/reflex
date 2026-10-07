CLUSTER: events
SUMMARY: Event-loop and Var behaviour on 0.10.0a2 (evapp suite, 61 records per run, dev and prod) with 0.9.12 dev/prod and 0.10.0a1 baselines, plus a minimal `mini` app for the raising/superseded-handler leads under the disk and Redis managers. No a2-specific regression; a2 = a1 everywhere. Differences from 0.9.12 are documented 0.10 changes, the #7319/#7326/#7465 fixes, and one undocumented change (background task calling a handler method outside the lock now raises ImmutableStateError). Pre-existing issues with repros: raising foreground handler's delta deferred to the next event (medium), Redis discards failed/superseded events including already-delivered changes (medium), superseded post-yield changes leak into the next delta (low), UTF-16 string Var semantics + React #418 in prod (low).
ARTIFACTS: prerelease_testing/2026-10-07/events/ (NOTES.md with rerun commands, out/suite_table.md, src/evapp, src/mini, driver/, probes/, tools/tcpproxy.py, bin/, logs/, out/, prev_out/; 4.1 MB)
TESTS:
- [pass] suite a2 dev / a2 prod / 0.9.12 dev / 0.9.12 prod (+ a1 dev from 10-06): 61 records per run; a2 dev rerun matched every status; a2 = a1 in every row.
- [pass] supersedes: rapid clicks, background+supersedes, cancel while holding the lock, chained child cancelled, ComponentState instances independent and self-supersede.
- [anomaly] sup.cancelled_unyielded_mutation on every version (N-022); under Redis the whole cancelled event is dropped (N-021).
- [fail, documented] deco.late_marker_after_is_background_read fails on a2/a1 (passes on 0.9.12): #7370 "read once".
- [pass] nested client event lists (#7319): match branch, depth 50, backend failure mid-list, malformed event, call_script/run_script, prevent_default, ctrl+b; 0.9.12 storms the websocket (244,718 and 729,087 frames) and kills the driver.
- [pass, not a finding] handler returning/yielding a nested list: identical TypeError on every version (undocumented, flat lists work).
- [pass] temporal events across a real disconnect (pausable TCP proxy): correct on a2 dev/prod and 0.9.12 dev/prod.
- [pass] api.bg_get_state_get_var_value_sibling, api.dataclass_nested_inplace_mutation on all four runs.
- [pass, by design] failing substate __init__ breaks every later State() on all versions (eager substate tree).
- [anomaly] raising foreground handler: toast at +0.05 s, its changes only with the next event (+3.1–3.3 s); persisted; on_load and background tasks deliver immediately (N-020). Same on all versions.
- [pass] #7465 private attributes in mixins, dunder constants, rx.field() dunder, ComponentState, background tasks (lock guard), dev and prod; 0.9.12 raises SetUndefinedStateVarError, a1 only in dev.
- [anomaly] UTF-16 string Var semantics; React #418 in prod (N-023), all versions.
- [pass, documented] throttle has no trailing call.
- [pass] #7326 slice fuzz: 6890 forms match Python on a2/a1; 0.9.12 204 mismatches + 3180 RecursionErrors.
- [pass] state-API probe (23 checks) a2 = a1; typelog (#7353) and undeclared attribute in prod (#7312) as documented.
- [anomaly] bind: background task calling a handler method outside the lock → ImmutableStateError on 0.10 (0.9.12 wrote unlocked); type(self) is StateProxy inside (N-024).
- [pass] deep_equals (#7208), HookProbe _replace(_var_data=) (#7256), raw setvar rejection, reset with client-storage substates, rx.foreach handlers with 0–5 args and lambdas.
- [anomaly, benign, same on 0.9.12] favicon 404 in prod; websocket reset errors while the proxy is down; compile progress bar overshoot (20/19); "Unexpected exit from worker-1" when the process group is killed.
REVERIFIED:
- 10-06 events_vars leads: sup.cancelled_unyielded_mutation → N-022 (pre-existing); nested-list return/yield → not a lead; temporal.offline_disconnect → correct; api.* → pass; initfail → by design; chained-raise delta timing → N-020 (all raising foreground handlers, pre-existing).
- #7465, #7326, #7319 fixed on a2 dev and prod.
ISSUES:
- N-020 (MEDIUM, pre-existing) raising foreground handler's delta deferred to the next event.
- N-021 (MEDIUM, pre-existing) Redis discards failed/superseded events including already-delivered changes.
- N-022 (LOW), N-023 (LOW), N-024 (LOW, undocumented behaviour change since 0.9.12).
NOT_COVERED: single-process 0.9.12 run of the nested group; evapp on a1 in prod; Redis in prod. All processes stopped; 3460-3479 / 8460-8479 free.
