ITEM: a3_class_state
KIND: reverify
REF: N-004
TITLE: State store sharing across versions behaves exactly as the new #7494 breaking-change note says (Redis and disk)
SEVERITY: medium
STATUS: changed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: Python: a3_class_state/bin/schema_matrix.sh <out> a3 alpha2 stable (ORIGINAL derive_h_schema.py): a3 hash == a2 hash
  (bbd147dc...); a3<->a2 load both ways (also across a default change); 0.9.12 -> a3 loads (same default); a3 -> 0.9.12
  StateSchemaMismatchError. probes/pickle_keys.py: the a3 pickle holds only field values (no dirty_vars/dirty_substates/_backend_vars,
  no _replaced_defaults; a2 still wrote the three empty keys). probes/upgrade_pickle.py: a3 loading 0.9.12/a2 pickles drops their stale
  keys, dirty sets clean, re-serializes without them. Disk store: bin/disk_matrix.sh (StateManagerDisk, shared REFLEX_STATES_WORKDIR):
  a3->a3, a3->a2, a2->a3, 0.9.12->a3 keep the session; a3->0.9.12 (and a2->0.9.12) silently start fresh and the 0.9.12 write replaces
  the session. E2E fleet (prod, one Redis on 8109, same token, bin/fleet_phase.sh): 0.9.12->a3 kept, a3->a3 kept, a3->0.9.12 FRESH
  (user '', count 5; no traceback, nothing logged), 0.9.12->a3 kept (post-reset data), a3->a2 kept, a2->a3 kept, a3(d5)->a3(d7) kept.
  Note: with `reflex run` the disk store is wiped at every start (reset_disk_state_manager), so the disk case only applies to stores
  shared by running backends; documented note is accurate.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/logs/schema_matrix.phaseB.txt, logs/disk_matrix.txt, logs/upgrade_pickle.a3.txt,
  logs/fleet/chain_summary.txt, out/fleet/chain.jsonl, out/fleet/*.redis.txt, logs/fleet/fleet-chain-4_a3-_stable_rollback_.trimmed.log
ROOT_CAUSE_GUESS: by design (#7494); 0.9.12 istate/manager/redis.py suppresses StateSchemaMismatchError into a fresh state, disk.py load_state swallows it
