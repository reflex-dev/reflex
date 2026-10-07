ITEM: a3_ent_auth
KIND: reverify
REF: N-032
TITLE: Enterprise OIDC cross-tab logout / stale token hash at boot — FIXED on reflex 0.10.0a3 (#7493) + enterprise 0.9.7a5
SEVERITY: high
STATUS: fixed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: |
  SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_ent_auth  (layout: prerelease_testing/2026-10-07-a3/a3_ent_auth/NOTES.md "Rerun commands")
  $W/bin/infra.sh start; redis-cli -p 8349 flushall
  $W/bin/start_app.sh a3-ent vauth_a3e dev $W/logs/a3e-dev-redis.server.log; $W/bin/wait_ready.sh http://localhost:3340/ http://localhost:8340 400
  cd $W/drivers; DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
  $DRV vdrv.py stale http://localhost:3340 a3e-dev-redis 3; $DRV vdrv.py away http://localhost:3340 a3e-dev-redis 3; $DRV vdrv.py xtab http://localhost:3340 a3e-dev-redis 6
  (prod: GRANIAN_WORKERS=1 ... prod, base http://localhost:8341; memory: NOREDIS=1; positive control: alpha2-ent/vauth_a2e)
  Results (a3 dev Redis / prod Redis 1 worker / dev memory): stale P1 3/3/3, P2 3/3/3, P3 3/3/3 of 3; away 3/3 each;
  xtab 6/6, 6/6, 4/4 (the cross-tab race still happens 1/6, 4/6, 0/4 and is healed every time, like 0.9.12).
  Positive control on the same harness: a2 + enterprise a4 stale 0/0/0 of 3, away 0/3; a2 + enterprise a5 0/0/0, away 0/3
  (a5 alone does not fix it: auth code byte-identical a4 -> a5); 0.9.12 + a5 3/3/3, away 3/3, xtab 6/6.
  Explorer probes on the entauth app (a3 dev Redis): stale_hash_probe.py CORRECTED anon 3/3, loggedin 3/3, live 3/3;
  xtab_probe.py TAB1_LOGGED_OUT 5/5; drive_auth_redis.py cycle,pubnav,twotab,xtab ALL_PASSED.
  Core-only coregd_app on reflex 0.10.0a3 (dev and prod): GET_DELTA_SAW theme='bogus-boot' exactly once + 'bogus-nav' (a2: nav only; 0.9.12: both).
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_ent_auth/logs/{a3e-dev-redis,a3e-prod-redis-1w,a3e-dev-memory,a2e-dev-redis,a2e5-dev-redis,s912e5-dev-redis}-{stale,away,xtab}.json(.gz), logs/coregd-{a2,s912,a3,a3-prod}.*, logs/stalehash-a3e-dev-redis.out, logs/xtab-a3e-dev-redis.out, logs/drive-auth-a3e-dev-redis.out(.gz), shots/a3e-*-away-*.jpg; NOTES.md "N-032 on a3-ent"
ROOT_CAUSE_GUESS: fixed by reflex/state.py (0.10.0a3) BaseState.hydrate_and_load: `applied = await _apply_client_storage_vars(...)`, re-marked dirty after the guarded snapshot, so the event's own delta passes OIDCAuthState.get_delta; boot now sends hydrate_and_load + reconcile_tokens_after_sync on a hash mismatch.
NOTE: no regression found from #7493 in the auth flows (fresh browser writes nothing; one same-value hash echo per boot as on 0.9.12; no extra cookie syncs/loops; relogin alice->bob clean; MCP identical). One LOW behaviour change filed separately (a3_ent_auth-4).
