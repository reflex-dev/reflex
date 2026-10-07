ITEM: a3_class_state
KIND: reverify
REF: N-005
TITLE: Plain default assigned to a str-annotated LocalStorage/SessionStorage/Cookie var (incl. ComponentState `cls.value = initial`) now keeps browser storage, name and options
SEVERITY: medium
STATUS: fixed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; P=/home/user/reflex/prerelease_testing/2026-10-07;
  cd $P/reverify_core/verification/n005-storage-assign/scripts  (copy to a neutral dir first)
  $SB/envs/a3/bin/python storage_assign_matrix.py a3   -> every str-annotated plain value / plain-returning factory: is_client_storage=True, compiled name k1 kept (a2: False / None)
  e2e (dev 3101/8101 and prod+redis 3104, 9 granian workers): copy $P/reverify_core/core_a2, `reflex run`, then
  NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $P/reverify_core/drivers/drive_core.py http://localhost:3101 out core-a3-dev home,cs,storage,dunder
  -> 1_browser_storage has ls_plain_key, lscs_key and cookie ck_key; a new tab shows the changed values (a2: none of the three written).
  Also n005 app (drive_stor.py): 8/8 persisted in a new tab, dev and prod+redis (a2: k_plain, k_facplain, k_ck_plain, k_cs lost);
  csbox (reverify_hydration): `plain` instance persists. Extra app apps/clse2e: sync=True still syncs across tabs after
  `St.sync = "assigned"`; cookie keeps SameSite=Strict + max_age 3600; a storage-ANNOTATED var now accepts a plain value (a2: TypeError at import).
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/logs/py/a3/storage_assign_matrix.txt, logs/py/a3/cs_storage_default_probe.txt,
  logs/py/a3/derive_g_assign.dev.txt, out/e2e/core-a3-dev.json, out/e2e/core-a3-prod-redis.json, out/e2e/stor-a3-{dev,prod-redis}.json,
  out/e2e/csbox-a3-{dev,prod-redis}.json, out/e2e/clse2e-a3-dev.json (+ alpha2 controls: logs/py/alpha2/*, out/e2e/core-alpha2-dev.json)
ROOT_CAUSE_GUESS: fixed by reflex_base/vars/base.py:4753 _keep_client_storage + reflex/istate/storage.py ClientStorageBase._with_value.
  Remaining gaps (separate findings): non-str values (None on Optional[str]) still drop storage (a3_class_state-8); instances of a
  ComponentState share the declared key (a3_class_state-9); str-annotated declared factory = #7498 (known).
