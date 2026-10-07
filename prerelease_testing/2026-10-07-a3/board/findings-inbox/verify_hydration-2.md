ITEM: verify_hydration
KIND: verify
REF: A3-12
TITLE: CONFIRMED, pre-existing on a3, a2 and 0.9.12: sync=True LocalStorage written with different values by several tabs at once loops forever; also triggered with NO user action by one dev backend reload (every save) or a deploy/restart while >=4 tabs sit on pages whose on_load stamps a per-tab value
SEVERITY: medium
STATUS: confirmed
REGRESSION_VS_0.9.12: no (0.9.12 storms 2/2 in each setting)
REGRESSION_VS_0.10.0a2: no (a2 storms 2/2 in each setting; state.js byte-identical a2 -> a3)
REPRO: SB=<scratch>; V=$SB/apps/verify_hydration; copy verification/{src,drivers,scripts} as in verify_hydration-1.
  (a) no user action: $V/scripts/vsrv.sh start vh-a3-dev a3 dev $V/src/vhsync 3660 8660 REFLEX_API_URL=http://localhost:8660
      $V/scripts/vrun.sh a3dev_docsrestart4 2 3660 docs-restart 4 --restart-cmd "echo '# reload' >> $V/run/vh-a3-dev/vhsync/vhsync.py" --restart-wait 15
      = 4 tabs opened one at a time on /doc/d0..d3 (Recent.last_doc = rx.LocalStorage("", name="vh_last_doc", sync=True), on_load stamps the slug); quiet and
        converged on d3; then the backend reloads, every tab reconnects (hydrate_and_load -> on_load) and stamps its slug at once -> endless loop.
  (b) browser restart: $V/scripts/vraw.sh a3dev_rtt100_rawdocs6_st0 2 3660 6 0 docs 0 10 (6 real background tabs restored at once, 100 ms RTT via vlproxy.sh)
  (c) explorer fixture: a3_hydration/scripts/run_stamp.sh <venv> dev 2 <FP> <BP> /stamp 6 (control /same 6 stays quiet).
EVIDENCE: a3_hydration/NOTES.md "## VERIFICATION"; verification/results/{a3,a2,s912}dev_docsrestart4_*.json, *_rtt100_rawdocs6_st0_*.json, summary.json;
  verification/explorer_rerun/console.txt + results/stamp/. docs-restart4: a3 2/2 (39-47k frames/5 s), a2 2/2 (43-46k), 0.9.12 2/2 (21-25k); raw docs6: a3 2/2,
  a2 2/2, 0.9.12 2/2; run_stamp /stamp 6: a3 2/2, a2 2/2, 0.9.12 2/2, /same quiet 1/1; 3 tabs loaded 300 ms apart: 0/3. Tabs end on 2-3 different values.
ROOT_CAUSE_GUESS: reflex_base/.templates/web/utils/state.js:1267-1277 handleStorage sends e.newValue to update_vars_internal (reflex/state.py:2738) and the answer is
  written back by applyClientStorageDelta (state.js:1076) even when another tab changed the key meanwhile; no versioning, so two values in flight never die out.
  Fix belongs in the frontend storage-sync path: never write back the answer to a storage-event sync and treat localStorage as the source of truth (sync from
  localStorage.getItem). Prototype on a scratch compiled state.js: the loop is gone (0/4) but 3/4 runs left one tab displaying a value other than localStorage's, so the
  fix must also re-read localStorage when a sync answer disagrees with it (or version the values). Fixing A3-12 alone does not fix A3-11 (the stale boot write is a lost update).
