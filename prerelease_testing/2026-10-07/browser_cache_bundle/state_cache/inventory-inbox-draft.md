ITEM: browser_cache_bundle
KIND: new
REF: -
TITLE: Nested inventory mutation via dict values/items misses state dirtiness and leaves cached totals stale through reload
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Use state_cache/NOTES.md exact clean bootstrap and run_matrix command. App source: state_cache/app/order_dashboard/order_dashboard.py. In fresh session initial inventory tea10/mug20 and stock30; click dict_values once. Expected tea9/mug19/stock28; all remain10/20/30. Reload restores raw9/19 but cached sum stays30. Click inventory_assign to restore28. dict_items repeats. dict_keys and .get/index mutations send correct deltas.
EVIDENCE: state_cache/runs/{alpha2-dev-2,alpha-dev-1,stable-prod-1,alpha2-prod-1,alpha-prod-1}/*-results.json.gz; */*-frames.json.gz; alpha2-dev-2/inventory-wire-excerpt.json; selected screenshots; SUMMARY.json. Confirmed independently by parent; do not duplicate its inbox finding.
ROOT_CAUSE_GUESS: Published reflex/istate/proxy.py:639,910 wraps dict get/setdefault results but view results contain raw nested mutable dictionaries; changes bypass dirty marking. Mechanism inferred from source and wire/reload controls; no framework patch applied.
