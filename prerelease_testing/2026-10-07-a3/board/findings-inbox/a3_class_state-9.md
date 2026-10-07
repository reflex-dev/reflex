ITEM: a3_class_state
KIND: new
REF: N-005
TITLE: ComponentState + named browser-storage var + `cls.x = initial` (the a3 changelog's own example) gives every instance the same browser key; after a reload one instance shows another's value
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: unknown
REPRO: $P/reverify_hydration/src/csbox (Box(rx.ComponentState): pref: str = rx.LocalStorage("light", name="box_pref"); instances
  tag=none (no assignment), tag=plain (`cls.pref = "dark"`), tag=storage (`cls.pref = rx.LocalStorage(initial, name=f"box_pref_{tag}")`)),
  RVH_VENV=a3 reflex run (dev 3103/8103 or prod+redis 3106); driver $P/reverify_hydration/drivers/csbox_check.py: click "choose" on all
  three, reload the SAME tab -> a3 shows none="user-plain" (it chose "user-none"), plain="user-plain", storage="user-storage";
  localStorage has a single box_pref. The a3 CHANGELOG/docs present `cls.theme = initial` in get_component on a named storage var as the
  pattern, but a ComponentState is used for several instances, which then overwrite each other in the browser.
  0.9.12: all three share box_pref (worse: plain/storage render a static "dark"); a2: plain was not storage at all (N-005), so the
  instances did not collide. Docs should say to give each instance its own name (rx.LocalStorage(initial, name=f"...{id}")), which works.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/out/e2e/csbox-{a3-dev,a3-prod-redis,alpha2-dev,stable-dev}.json,
  logs/adv/adv7495.a3.txt (storage_cs_multi_instances_same_key: 3 instances -> same 'box_pref' entry)
ROOT_CAUSE_GUESS: design: _with_value keeps the declared name; docs (docs/vars/base_vars.md, CHANGELOG 0.10.0a3 #7495 entry) lack the caveat
