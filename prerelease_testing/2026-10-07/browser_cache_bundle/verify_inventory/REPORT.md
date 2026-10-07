ITEM: browser_cache_bundle
KIND: verify
REF: inventory dictionary-view mutation lead from state_cache
TITLE: Native dictionary-view iteration mutates nested inventory without UI/cache invalidation
SEVERITY: medium
STATUS: still-broken
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: unknown
VERDICT: independently confirmed on stable0.9.12 and alpha2 0.10.0a2 in real Chromium dev apps
REPRO: Follow NOTES.md setup; scripts/run.py executes both versions. Click reserve-values or reserve-items: backend9/19 but UI10/20/30. Reload: raw9/19, cachedtotal30. Copy/reassignment heals28; key-indexed mutation updates immediately.
EVIDENCE: runs/alpha2/results.json, runs/stable/results.json; values-after-event.png/values-after-reload.png/indexed-control.png in both run dirs; full.json.gz websocket captures; logs/{stable,alpha2}-server.log.gz backend audits.
ROOT_CAUSE_GUESS: Published reflex/istate/proxy.py:640 includes only get/setdefault in __wrap_mutable_attrs__; __getattr__ at910 returns native values/items methods, while __getitem__ at965 wraps nested objects. Thus native view values bypass mutation dirty tracking.
LIMITS: Dev mode, Chromium only; alpha1/prod not independently covered. No claim of data loss across backend restart. Pure cached computed var, normal public events, independent authored fixture and negative/positive controls.
