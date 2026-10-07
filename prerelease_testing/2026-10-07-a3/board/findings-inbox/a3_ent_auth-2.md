ITEM: a3_ent_auth
KIND: reverify
REF: N-033
TITLE: Prod multi-worker POST /_reflex/cookies/sync 405 on cold granian workers — UNCHANGED on a3 + enterprise 0.9.7a5
SEVERITY: high
STATUS: still-broken
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: |
  SB=...scratchpad; W=$SB/apps/a3_ent_auth; $W/bin/infra.sh start; redis-cli -p 8349 flushall
  VAUTH_PID_HEADER=1 $W/bin/start_app.sh a3-ent vauth_a3e prod $W/logs/a3e-prod-redis-9w.server.log   # default workers: 9 on 4 CPUs
  $W/bin/wait_ready.sh http://localhost:8341/ http://localhost:8341 600; sleep 20
  $W/bin/post_sync.sh http://localhost:8341 27 $W/logs/a3e-prod-9w-post-fresh.txt      # expect 400 from every worker
  cd $W/drivers; env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python vdrv.py logins http://localhost:8341 a3e-prod-redis-9w 6
  $W/bin/post_sync.sh http://localhost:8341 27 $W/logs/a3e-prod-9w-post-after-logins.txt; ... vdrv.py storm http://localhost:8341 a3e-prod-redis-9w 3
  Results: fresh 27/27 405 over 8 pids (a2: 27/27, 0.9.12: 27/27); logins with token cookies 3/6 (a2 1/6, 0.9.12 1/6) — every
  failing login's single sync POST got 405 from a cold pid and its new tab landed on /login; afterwards 18x400 / 9x405 (3 pids
  still cold; a2 19/8). storm: both failed-sync logins (40 and 16 cookie-sync POSTs in the first 5 s) ended by logging the
  login tab out; no sustained storm in 2 tries (a2: 1 of 3 sustained ~115 POSTs/s). With GRANIAN_WORKERS=1 every sync was 200.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_ent_auth/logs/a3e-prod-9w-post-{fresh,after-logins}.txt, logs/a3e-prod-redis-9w-{logins,storm}.json(.gz), logs/a3e-prod-redis-9w.server.log(.gz)
ROOT_CAUSE_GUESS: unchanged enterprise code (byte-identical a4 -> a5): reflex_enterprise/auth/cookie.py HTTPCookie.ensure_handlers_registered() adds the POST route lazily per process, only from HTTPCookie.sync(); cold workers fall through to the prod static mount (405).
