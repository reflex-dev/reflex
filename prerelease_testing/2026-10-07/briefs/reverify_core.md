# Cluster `reverify_core` — re-verify F-001/F-004/F-011/F-012/F-013/F-014/F-016/F-018 on 0.10.0a2 + probe the new descriptor rules

Ports: frontend 3100-3119, backend 8100-8119. Work dir: $SB/apps/reverify_core/. DEST: /home/user/reflex/prerelease_testing/2026-10-07/reverify_core/
Venv under test: $SB/envs/alpha2 (and $SB/envs/alpha2-ent for the enterprise part). Before/after: $SB/envs/alpha (0.10.0a1), $SB/envs/stable (0.9.12).

Read first: $SB/CAMPAIGN_STATE.md, then /home/user/reflex/prerelease_testing/2026-10-06/FINDINGS.md sections FINDING-001, 004, 011, 012, 013, 014, 016, 018, and
/home/user/reflex/prerelease_testing/2026-10-06/thirdparty/NOTES.md (incl. its VERIFICATION sections). COPY the scripts you re-run out of the repo into your work dir.

## Re-verify (each: same script on alpha2; record fixed / still broken / changed, with the exact output)
1. F-001 core semantics: /home/user/reflex/prerelease_testing/2026-10-06/thirdparty/verification/classattr/scripts/derive_a.py and the e2e app
   (`e2e_app` + `drive_classattr.py`, dev AND prod). The new train KEEPS the Field-on-class-access semantics but
   documents them (reflex CHANGELOG 0.10.0a2 misc entry for #7312) and adds #7456: formatting a backend var into a
   string (`f"{State._size}px"`) must now raise `BackendVarFormatError` (a `VarTypeError`) instead of silently
   embedding the repr; passing it as a child → `ChildrenTypeError`; as a prop → `TypeError: Unsupported type ... Field for LiteralVar`;
   `State._items.default_value()` is the documented way to bake the default in. Verify each of these statements
   literally, in dev and prod, and check that the error messages are actionable (name the var / suggest default_value()).
   Also #7465: a double-underscore attribute (`__counter = 0`, name-mangled, and a dunder like `__data_source_params_class__ = X`)
   is now a PLAIN class attribute (class access returns the value; `self.__counter = 1` from a mixin/base/underscore-named class
   no longer raises SetUndefinedStateVarError in dev; vars do NOT react to it) unless declared with `rx.field()`
   (`__counter: rx.Field[int] = rx.field(0)` → a real backend var). Probe all of those, including pickling/Redis round trips
   and a ComponentState.
2. F-001 enterprise half: copy /home/user/reflex-enterprise/demos/ag_grid out (the previous explorer's copy with its
   sqlite + alembic is at /home/user/reflex/prerelease_testing/2026-10-06/ent_demos/partial/ag_grid — reuse it), run with $SB/envs/alpha2-ent (CI=true), open `/model`,
   `/model-auth`, `/model-ssrm` and the infinite/SSRM pages, dev and prod: the `/abstract-wrapper-data` endpoint must
   return 200 and the grid must show rows (previously `AttributeError: 'Field' object has no attribute 'from_request'`
   at `reflex_enterprise/components/ag_grid/wrapper.py:153`). Drive sort/filter/paginate/edit/add through the model
   wrapper and compare the db. Reuse the previous drivers in /home/user/reflex/prerelease_testing/2026-10-06/ent_demos/partial (ag_model-*.py etc.).
3. F-004: derive_b.py / derive_b_reset.py with REFLEX_ENV_MODE=dev and prod, plus the e2e app: `cls._k = "sk"` must now
   update the field default (#7461), instances must read it, pickle/disk/redis round trips must keep it, instance writes
   and reset() must work in dev. Also the NEW #7461 features: `ComponentState.get_component` doing `cls.count = 10`
   per instance (two instances with different defaults; reset restores the LAST configured default); assigning a
   zero-arg callable → default factory (validated by calling once); assigning a Field or Var instance → must be
   rejected with a clear error; assigning a wrong-typed value → clear error; browser-storage vars keep their storage
   settings when a factory is assigned ("Browser storage vars keep their storage settings when a factory is assigned,
   and declared factories are honored when compiled and reset" — test LocalStorage + default_factory in dev and prod);
   "Defaults are no longer part of the saved-state schema": save state with the disk manager (or pickle) under one
   default, change the default in source, restart, confirm the saved state still loads (no schema-mismatch reset).
4. F-011 (/home/user/reflex/prerelease_testing/2026-10-06/pymatrix_install/apps/fwdref_app, `reflex compile --dry`), F-012 (derive_c.py), F-013 (derive_d/derive_d.py),
   F-014 (`reflex component --help`), F-016 (/home/user/reflex/prerelease_testing/2026-10-06/pymatrix_install/apps/typing_fixture with published ty + pyright on 3.12),
   F-018 (/home/user/reflex/prerelease_testing/2026-10-06/thirdparty/apps/tp_components /clerk page, dev): report each as fixed/still-broken.
5. Sanity on 3rd-party packages that were affected: reflex-dynoselect and reflex-clerk python probes
   (/home/user/reflex/prerelease_testing/2026-10-06/thirdparty/probes/clerk_probe.py, the /dynoselect page) — does #7465/#7461 change their behaviour?
Baseline anything surprising against $SB/envs/alpha and $SB/envs/stable. Copy artifacts to DEST as you go.
