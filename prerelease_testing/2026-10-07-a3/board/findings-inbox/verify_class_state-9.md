ITEM: verify_class_state
KIND: verify
REF: a3_class_state-9
TITLE: ComponentState instances of a NAMED storage var share one browser key; with `cls.x = initial` (a3 CHANGELOG example) they overwrite each other (NARROWED: inherent to named keys, docs caveat only)
SEVERITY: low
STATUS: narrowed
REGRESSION_VS_0.9.12: no (0.9.12: every instance already shares the named key; assigned instances render static text)
REGRESSION_VS_0.10.0a2: no (a2: assigned instances were not storage at all = N-005; a3 keeps the name exactly as #7495 promises)
REPRO: cd $SB/apps/verify_class_state && EXPECT_VENV=verify_class_state-<a3|a2|s912> $SB/envs/verify_class_state-<v>/bin/python -I run/probes/probe_v9_cs_keys.py
  a3: Box(pref: str = rx.LocalStorage("light", name="box_pref")) instances with no assignment and with cls.pref = initial both compile
  to key box_pref; cls.pref = rx.LocalStorage(initial, name=f"box_pref_{tag}") gets its own key; an UNNAMED storage var gets a
  per-instance key. 0.9.12: all instances box_pref. E2E a3 dev (verification/e2e89): three instances, choose a/b/c -> one
  v_box_pref=user-c; after reload a and b show "user-c".
  Why narrowed: the name is the browser key by definition, and instances that assign nothing collide identically on 0.9.12. Docs gap:
  the a3 CHANGELOG #7495 entry shows `cls.theme = initial` in get_component on rx.LocalStorage("light", name="theme") and base_vars.md says
  get_component configures defaults "independently for each component", with no note that a named key is shared by every instance
  (browser_storage.md warns only about Cookie names shared across states). Suggest: drop `name=` from the changelog example or add the
  caveat (omit name, or use name=f"...{id}").
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/verification/out/f9_own_{a3,a2,s912}.txt, out/e2e89-a3-dev.json; NOTES.md ## VERIFICATION
ROOT_CAUSE_GUESS: design: reflex/istate/storage.py 34-36 (_with_value copies **vars(self), including name); docs: CHANGELOG.md v0.10.0a3 #7495
  entry, docs/vars/base_vars.md "Changing Defaults".
