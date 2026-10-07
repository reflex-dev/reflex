ITEM: verify_class_state
KIND: verify
REF: a3_class_state-8
TITLE: Assigning None to an Optional[str] (or a non-str to a Union) browser-storage var through the class silently drops browser storage (CONFIRMED, Python level and e2e)
SEVERITY: low
STATUS: confirmed
REGRESSION_VS_0.9.12: yes (technically: 0.9.12 ignored the assignment, so storage stayed)
REGRESSION_VS_0.10.0a2: no (identical on a2; residual gap of the N-005 fix, which covers str only)
REPRO: cd $SB/apps/verify_class_state && EXPECT_VENV=verify_class_state-a3 $SB/envs/verify_class_state-a3/bin/python -I run/probes/probe_v8_storage.py
  (probes copied from prerelease_testing/2026-10-07-a3/a3_class_state/verification/probes). St.opt = None (Optional[str] LocalStorage),
  St.uni = 5 (Union[str,int]), St.ck = None (Optional[str] Cookie): accepted silently; field default becomes None/int; compiled client
  storage keeps only the str-assigned control; a later St.opt = "y" stays a plain var; `del St.opt` twice restores storage.
  _is_client_storage stays True (lru_cache) for a var looked up before the assignment while the compiled map omits it.
  E2E a3 dev (verification/e2e89, ports 3605/8605, driver drive_v89.py): after "set both", localStorage has v_plain but no v_opt; a new tab
  shows opt "" while plain persists. No console errors.
  Realism: public code search finds 2 repos declaring Optional[str]/str|None storage vars, none assigning None via the class; the docs
  promise storage only for "a plain string". Plausible trigger: `cls.token = initial` in get_component with an optional prop.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/verification/out/f8_own_{a3,a2,s912}.txt, out/e2e89-a3-dev.json,
  screenshots/e2e89-a3-dev-after-{clicks,reload}.png; NOTES.md ## VERIFICATION
ROOT_CAUSE_GUESS: reflex 0.10.0a3 reflex/istate/storage.py 24-37 (ClientStorageBase._with_value wraps only str, line 34);
  reflex_base 0.10.0a3 reflex_base/vars/base.py _keep_client_storage 4753-4780 returns the value unchanged, _accepts_default 4725-4750
  accepts None for Optional[str], _assign_default replaces the storage default; reflex/state.py 1635-1656 _is_client_storage (lru_cached)
  classifies by field.default.
