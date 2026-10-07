ITEM: browser_cache_bundle
KIND: new
REF: -
TITLE: Mutating nested inventory through dict.values/items bypasses UI and cached-var invalidation
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Follow browser_cache_bundle/verify_inventory/NOTES.md (clean exact-PyPI bootstrap and scripts/run.py). Inventory starts tea10/coffee20, cached total30. Click Reserve via values: a normal public handler runs `for item in self.inventory.values(): item["stock"] -= 1`. Backend audit becomes9/19 but raw UI/cachedtotal remain10/20/30. Reload shows raw9/19 but cachedtotal30. Reassign current inventory fixes total28. Reset and repeat items; key iteration plus indexed nested mutation is the passing control.
EVIDENCE: browser_cache_bundle/verify_inventory/runs/{stable,alpha2}/results.json and full.json.gz; values-after-event.png, values-after-reload.png and indexed-control.png; logs/{stable,alpha2}-server.log.gz. Independently authored second fixture confirms the exploring agent's lead using a pure cached computed var, normal event handlers and separate backend audit. Wider state_cache matrix also reproduces on alpha1.
ROOT_CAUSE_GUESS: Published alpha2 reflex/istate/proxy.py:640 only wraps get/setdefault method return values; __getattr__ around910 returns native values/items views containing unwrapped nested dicts. __getitem__ around965 wraps indexed nested values, explaining the control.
SCOPE: Realistic bulk stock reservation, medium pre-existing correctness weakness. No claimed backend restart data loss, exploit, or new 0.10 regression. Indexed mutation or explicit field reassignment avoids it. No framework fix applied.
