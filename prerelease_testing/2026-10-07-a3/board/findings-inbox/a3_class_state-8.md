ITEM: a3_class_state
KIND: new
REF: N-005
TITLE: The N-005 fix covers only str values: assigning None to an Optional[str] browser-storage var (or a non-str to a Union var) still silently drops browser storage
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: yes
REGRESSION_VS_0.10.0a2: no
REPRO: class St(rx.State): opt: Optional[str] = rx.LocalStorage("d", name="k_opt")
  St.opt = None   # accepted silently
  -> reflex.compiler.utils._compile_client_storage_recursive(St) has no entry for opt; St._is_client_storage("opt") is False (or stays
  True if it was looked up before: it is lru_cached, so backend and compiled frontend can disagree); a later `St.opt = "x"` does not bring
  storage back. Same with `v: Union[str, int] = rx.LocalStorage(...)` and `St.v = 5`. E2E: a3_class_state/apps/clse2e (dev 3108/8108):
  after `change`, localStorage has k_sync/k_ann, sessionStorage k_ss, cookie k_ck_opt, but NO k_opt; a new tab shows "" for opt.
  Identical on a2 (gap not covered by #7495); 0.9.12 ignores the assignment and keeps storage. The docs only promise storage for "a plain
  string" (base_vars.md), so this is an undocumented silent edge rather than a broken promise.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/logs/adv/adv7495.a3.txt (storage_optional_none, storage_union_annotation_nonstr),
  out/e2e/clse2e-a3-dev.json, out/e2e/clse2e-alpha2-dev.json
ROOT_CAUSE_GUESS: reflex/istate/storage.py ClientStorageBase._with_value only wraps str; reflex_base/vars/base.py _keep_client_storage
  (4753) returns non-str values unchanged and _accepts_default accepts None for Optional[str]. Fix: reject (TypeError) a non-str value for
  a storage default, or keep the storage classification separately from the default value.
