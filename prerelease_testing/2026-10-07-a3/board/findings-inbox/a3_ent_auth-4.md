ITEM: a3_ent_auth
KIND: new
REF: N-032
TITLE: After the #7493 boot reconcile signs a stale tab out, the tab stays on the protected page (blanked) instead of being redirected to /login as on 0.9.12
SEVERITY: low
STATUS: changed
REGRESSION_VS_0.9.12: yes
REGRESSION_VS_0.10.0a2: no
REPRO: |
  Same harness as a3_ent_auth-1 (vauth app, a3-ent, dev Redis, port 3340):
  cd $W/drivers; env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python vdrv.py stale http://localhost:3340 a3e-dev-redis 3
  then read p3_path / p3_who per rep (python -c 'import json;print([(r["p3_path"],r["p3_who"]) for r in json.load(open("../logs/a3e-dev-redis-stale.json"))])')
  and for `away`: tab1_who before the protected click.
  P3 (tab returns to /vault after cookies were cleared and hash "" written elsewhere): 0.9.12 + a5 lands on /login 3/3 right
  after boot; a3 dev Redis 0/3, a3 prod 1 worker 1/3, a3 dev memory 0/3 — the tab shows /vault with who="" and the protected
  values blanked (placeholders) until its next protected event, which redirects to /login. `away` (Back button): 0.9.12 2/3
  immediately on /login, a3 0/3 (dev) / 1/3 (prod). a2 never signed the tab out at all (N-032).
  Mechanism (timelines `drivers/timeline.py ../logs/<label>-stale.json 0 p3_log`): on a3 the page guard runs as the backend-
  chained on_load_internal of hydrate_and_load, BEFORE the frontend's cookie sync + reconcile_tokens_after_sync reset the session,
  so the guard still sees alice and allows the page; on 0.9.12 the separate on_load_internal often ran after the reset and redirected.
  No protected value or action is exposed: the boot snapshot briefly carries user_sub "alice" (also on 0.9.12), every later
  delta is blanked and the next protected event is refused with a redirect.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_ent_auth/logs/{a3e-dev-redis,a3e-prod-redis-1w,a3e-dev-memory,s912e5-dev-redis}-{stale,away}.json(.gz); shots/a3e-dev-redis-stale-*-p3.jpg, shots/s912e5-dev-redis-stale-*-p3.jpg
ROOT_CAUSE_GUESS: ordering, reflex/state.py (0.10.0a3) hydrate_and_load returns [OnLoadInternalState.on_load_internal] (guard runs server-side in the boot chain) while the hash reconciliation is a later frontend round trip (HTTPCookie.sync -> reconcile_tokens_after_sync in reflex_enterprise/auth/oidc/state.py); the enterprise reset does not re-run the page guard. Enterprise could redirect from reset_auth when the current page is protected.
