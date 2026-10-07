CLUSTER: browser_cache_bundle/state_cache
SUMMARY: All three published trains completed the order dashboard in Chromium and WebKit, dev and production. There are 607 checkpoints across 13 browser executions:517pass/90fail. All failures are the pre-existing nested dictionary-view dirty-tracking path or stable's inherited-background path, which passes in both alphas. No new 0.10 regression established; complete logs, deltas and assertions retained.
ARTIFACTS: prerelease_testing/2026-10-07/browser_cache_bundle/state_cache/
TESTS:
- [pass] Dataclass/list mutation via index, aliases, iteration, sorted/slice/list copy, nested factories, dataclass conversion/replacement, sort/reverse/slice assignment.
- [pass] Synchronous cached/cache=False values, dependency chain Cart→Fulfillment→Review, cached reads before/after a write, public sibling get_state mutation.
- [pass] Independent contexts/defaults, late fresh session, reload and reset controls.
- [fail] values/items inventory reservation: no dirty delta, reload restores raw inventory while cached sum remains stale; all3trains/dev+prod/browsers. Indexed key and explicit reassignment controls pass.
- [pass] Alpha1/alpha2 inherited background updates of parent mutable values and backend-only notes; stable misses raw/cached updates and has propagated stale audit checks.
- [anomaly] WebKit dev unused modulepreload warnings, all trains; zero production browser anomalies. Stable nonfatal event-payload-transform warning. Alpha1 dev worker exit error during explicit cleanup after completed checks/flush.
- [pass] All7owned process groups and all20allocated ports empty in final external ps/lsof snapshot. Browser contexts/browser processes closed by driver finally. No framework or shared environment modifications.
REVERIFIED:
- None formally claimed in this subtask. The documented inherited-var-proxy improvement is supported by stable vs both alpha controls.
ISSUES:
- TITLE: Bulk inventory mutation through dictionary values/items leaves browser and cached total stale
  SEVERITY: medium
  REGRESSION: no
  REPRO: Follow NOTES clean replay, click dict_values in a fresh session (10/20→expected9/19), reload (raw9/19, cached30), then inventory_assign (cached28); dict_keys is passing direct-update control. Automated assertions cover the same workflow.
  EVIDENCE: runs/alpha2-dev-2/chromium-results.json.gz; corresponding stable-prod and alpha-dev/prod results; inventory-wire-excerpt.json; selected screenshots. Parent independently verifies and owns board submission.
NOT_COVERED: Redis, enterprise, deployment/default-hash reconnect and external cache=False data (other owners), load/RSS/timing, full Safari application UI (WebKit engine only). No claim of comprehensive state correctness or fixed Linux F007.
