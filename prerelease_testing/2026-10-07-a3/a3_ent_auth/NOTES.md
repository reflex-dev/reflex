# a3_ent_auth — N-032 (reflex#7493) on reflex 0.10.0a3 + reflex-enterprise 0.9.7a5, OIDC/MCP/maps regression sweep

Status: COMPLETE (2026-10-07 ~21:30 UTC). Verdicts: N-032 FIXED (dev/prod/memory, every probe); N-033 UNCHANGED;
no regression from #7493 in the auth flows; one LOW behaviour change (reset tab not redirected) and one pre-existing
MEDIUM enterprise finding (protected client storage wiped on client-side navigation with Redis). Inbox files
`../board/findings-inbox/a3_ent_auth-{1..4}.md`; report `../board/results/a3_ent_auth.md`.
Big logs are gzipped in `logs/` (`zcat`); screenshots are `.jpg` in `shots/`.

## Environment

```sh
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_ent_auth            # work dir; this DEST dir mirrors it (apps/, bin/, drivers/, scripts/, logs/, shots/)
```
Shared, read-only venvs (Python 3.12; nothing installed by this item; versions checked with `uv --no-config pip freeze`):
- `$SB/envs/a3-ent`        reflex 0.10.0a3 + reflex-base 0.10.0a3 + offline enterprise 0.9.7a5 [mcp] + oidc-provider-mock 0.4.8 (UNDER TEST)
- `$SB/envs/a3`            reflex 0.10.0a3 core only (coregd_app)
- `$SB/envs/alpha2-ent`    reflex 0.10.0a2 + OLD offline enterprise 0.9.7a4 (the a2-pass state; positive control)
- `$SB/envs/alpha2-ent-a5` reflex 0.10.0a2 + enterprise 0.9.7a5
- `$SB/envs/s912-ent-a5`   reflex 0.9.12 + enterprise 0.9.7a5 (baseline)
- `$SB/envs/alpha2`, `$SB/envs/stable` — core only, for coregd_app
- `$SB/envs/driver` (playwright 1.63, Chromium `/opt/pw-browsers/chromium`); `$SB/envs/ent_auth2-drv` (a2 + a4 wheel +
  playwright + mcp) is used ONLY as the client interpreter of the MCP / a4-matrix drivers (their venv guards name it);
  the servers always run on the venv under test.
- enterprise a4 → a5 diff (installed packages): only `components/ag_grid/aggrid.py` + CHANGELOG differ; every auth/OIDC
  file is byte-identical, so any N-032 change comes from reflex.

Ports (item range): vauth/vauthx/entauth dev 3340/8340, prod single port 8341; a4 `auth` 3342/8342, `auth_min` 3343/8343,
`components` backend-only 8346; maps dev 3344/8344, prod 8345; coregd 3347/8347; redis 8349; mock OIDC 8358.
Every server: `CI=true REFLEX_TELEMETRY_ENABLED=false AUTHLIB_INSECURE_TRANSPORT=1 OIDC_ISSUER_URI=http://localhost:8358`
(+ `REFLEX_REDIS_URL=redis://localhost:8349` unless `NOREDIS=1`), `--loglevel debug`. `bin/start_app.sh` first runs a venv
guard from a neutral dir and writes `VENV_GUARD venv=... reflex X reflex-base Y reflex-enterprise Z` as line 1 of the log.

## Fixtures
- `apps/vauth/` = the a2 verifier app (`../../2026-10-07/ent_auth/verification/app`), unchanged. Per-venv copies `$W/vauth_<tag>/`.
- `apps/vauthx/` = NEW: vauth + `Vault.draft = rx.LocalStorage(name="vx_draft", sync=True)` and `Vault.ck = rx.Cookie(name="vx_ck")`
  on the default-protected state, `set_draft` event, `/` shows them (regression hunt of #7493 × the enterprise delta filter).
- `apps/coregd_app/` = core-only `get_delta` override app, unchanged.
- `apps/entauth/`, `apps/mapsapp/`, `apps/a4auth/` = explorer apps + 10-05 a4 matrix (with `reference/` upstream tests copied
  from `../../2026-10-05/enterprise/a4/auth/reference/`). `apps/entauth` is the a2-pass DEST version (with `fill_loaded`).
- `drivers/vdrv.py` (a2 verifier driver: `stale|away|xtab|logins|storm|logoutcookies`) — only changes: mock IdP port
  8738 → 8358, venv guard. `drivers/{race,timeline,noise,coregd_drv}.py` as in the a2 pass.
- NEW `drivers/hunt.py fresh|loads|relogin|pubslash <base> <label> <N>` (#7493 hunt; per-step counts of cookie-sync POSTs,
  sent events, hash writes, storage events; `fresh` records EVERY storage/cookie write), `drivers/hunt_cmp.py <label>...`,
  `drivers/storx.py <base> <label> <N>` (vauthx protected client storage), `drivers/json_cmp.py a.json b.json`.
- `scripts/` = explorer scripts; only change: work dir `apps/ent_auth2` → `apps/a3_ent_auth` (ports already this range).
- `bin/start_app.sh <venv> <appdir> <dev|prod> <log>` (env: `GRANIAN_WORKERS`, `VAUTH_PID_HEADER`, `NOREDIS=1`, `FP/BP/PP`),
  `bin/stop_app.sh`, `bin/wait_ready.sh`, `bin/post_sync.sh`, `bin/infra.sh` (= `scripts/infra.sh`: redis 8349 + mock 8358),
  `bin/run_storx.sh <venv>:<appdir>:<label>...`, `bin/sync_dest.sh`.

## Rerun commands

```sh
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_ent_auth
# fresh work dir from this DEST: mkdir -p $W/{logs,shots,screenshots,run}; cp -r bin drivers scripts $W/;
#   cp -r apps/vauth $W/vauth_src; cp -r apps/vauthx $W/vauthx_src; cp -r apps/coregd_app $W/coregd_src;
#   cp -r apps/entauth $W/entauth_src; cp -r apps/mapsapp $W/mapsapp_src; cp -r apps/a4auth $W/a4auth
for t in a2e a2e5 s912e5 a3e; do mkdir -p $W/vauth_$t $W/vauthx_$t; cp -r $W/vauth_src/* $W/vauth_$t/; cp -r $W/vauthx_src/* $W/vauthx_$t/; done
for t in a2 s912 a3; do mkdir -p $W/coregd_$t; cp -r $W/coregd_src/* $W/coregd_$t/; done
mkdir -p $W/entauth_a3e; cp -r $W/entauth_src/* $W/entauth_a3e/
$W/bin/infra.sh start
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
# --- N-032 probes; per build: a3-ent/vauth_a3e (a3e), alpha2-ent/vauth_a2e (a2e), alpha2-ent-a5/vauth_a2e5 (a2e5), s912-ent-a5/vauth_s912e5 (s912e5)
redis-cli -p 8349 flushall
$W/bin/start_app.sh a3-ent vauth_a3e dev $W/logs/a3e-dev-redis.server.log     # memory: NOREDIS=1 ...; prod 1 worker: GRANIAN_WORKERS=1 ... prod (base http://localhost:8341)
$W/bin/wait_ready.sh http://localhost:3340/ http://localhost:8340 400
cd $W/drivers
$DRV vdrv.py stale http://localhost:3340 a3e-dev-redis 3
$DRV vdrv.py away  http://localhost:3340 a3e-dev-redis 3
$DRV vdrv.py xtab  http://localhost:3340 a3e-dev-redis 6; $DRV race.py ../logs/a3e-dev-redis-xtab.json
$DRV hunt.py fresh|loads|relogin http://localhost:3340 a3e-dev-redis 2; $DRV hunt_cmp.py a2e-dev-redis a3e-dev-redis s912e5-dev-redis
$W/bin/stop_app.sh
# --- protected client storage (vauthx), dev Redis, one server per build
$W/bin/run_storx.sh a3-ent:vauthx_a3e:a3e-dev-redis alpha2-ent:vauthx_a2e:a2e-dev-redis s912-ent-a5:vauthx_s912e5:s912e5-dev-redis
# --- N-033 (default granian workers = 9 on this 4-CPU box), fresh server
redis-cli -p 8349 flushall; VAUTH_PID_HEADER=1 $W/bin/start_app.sh a3-ent vauth_a3e prod $W/logs/a3e-prod-redis-9w.server.log
$W/bin/wait_ready.sh http://localhost:8341/ http://localhost:8341 600; sleep 20
$W/bin/post_sync.sh http://localhost:8341 27 $W/logs/a3e-prod-9w-post-fresh.txt
$DRV vdrv.py logins http://localhost:8341 a3e-prod-redis-9w 6
$W/bin/post_sync.sh http://localhost:8341 27 $W/logs/a3e-prod-9w-post-after-logins.txt
$DRV vdrv.py storm http://localhost:8341 a3e-prod-redis-9w 3; $W/bin/stop_app.sh
# --- core-only get_delta fixture (dev; prod: PP=8347 ... prod, base http://localhost:8347)
FP=3347 BP=8347 NOREDIS=1 $W/bin/start_app.sh a3 coregd_a3 dev $W/logs/coregd-a3.server.log
$W/bin/wait_ready.sh http://localhost:3347/ http://localhost:8347 400
$DRV coregd_drv.py http://localhost:3347 > $W/logs/coregd-a3.driver.out; grep GET_DELTA_SAW $W/logs/coregd-a3.server.log; $W/bin/stop_app.sh
# --- explorer app (entauth) dev Redis: explorer probes, full auth cycle, hydration writes, MCP
redis-cli -p 8349 flushall; VENV=a3-ent APP_DIR=entauth_a3e $W/scripts/start_app.sh dev $W/logs/entauth-dev-redis-a3e.log
$W/bin/wait_ready.sh http://localhost:3340/ http://localhost:8340 400; cd $W/scripts
$DRV stale_hash_probe.py http://localhost:3340 a3e-dev-redis 3; $DRV xtab_probe.py http://localhost:3340 a3e-dev-redis-rep 5
$DRV drive_auth_redis.py http://localhost:3340 a3e-dev-redis cycle,pubnav,twotab,xtab
$DRV hydration_token_probe.py http://localhost:3340 a3e-dev-redis
MPY="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/ent_auth2-drv/bin/python"
$MPY check_mcp_anon.py http://localhost:8340 a3e-dev-redis --rate; $MPY check_mcp_oauth_redis.py http://localhost:8340 http://localhost:3340 a3e-dev-redis
$W/scripts/expiry_matrix.sh a3-ent entauth_a3e a3e proactive; $W/scripts/infra.sh restart-oidc 3600   # (expiry_matrix kills the mock)
# prod (1 worker) suite: GRANIAN_WORKERS=1 $W/scripts/prod_suite.sh a3-ent entauth_a3e a3e-prod-redis; $W/bin/stop_app.sh
# --- 10-05 a4 auth matrix (dev, memory; servers on the venv under test, drivers on ent_auth2-drv)
$W/scripts/a4_matrix.sh a3-ent a3e; $W/scripts/a4_matrix.sh s912-ent-a5 s912e5; $W/bin/a4_tally.sh a3e; $W/bin/a4_tally.sh s912e5
# --- maps (mkdir -p $W/mapsapp_a3e; cp -r $W/mapsapp_src/* $W/mapsapp_a3e/)
VENV=a3-ent APP_DIR=mapsapp_a3e APP_FP=3344 APP_BP=8344 $W/scripts/start_app.sh dev $W/logs/maps-dev-redis-a3e.log
$W/bin/wait_ready.sh http://localhost:3344/ http://localhost:8344 400; (cd $W/scripts && $DRV drive_maps.py http://localhost:3344 a3e-dev-redis)
$W/bin/stop_app.sh; VENV=a3-ent APP_DIR=mapsapp_a3e APP_BP=8345 $W/scripts/start_app.sh prod $W/logs/maps-prod-redis-a3e.log
$W/bin/wait_ready.sh http://localhost:8345/ http://localhost:8345 600; (cd $W/scripts && $DRV drive_maps.py http://localhost:8345 a3e-prod-redis)
# --- protected client storage incl. memory: NOREDIS=1 $W/bin/run_storx.sh a3-ent:vauthx_a3e:a3e-dev-memory-v2; $DRV storx_table.py <label>...
$W/bin/stop_app.sh; $W/bin/infra.sh stop
```

## Results

### Phase A (before a3 was published)

(a) Positive control — the harness reproduces N-032 on the a2-pass state (alpha2-ent = a2 + enterprise a4, dev Redis):
stale P1/P2/P3 0/3, 0/3, 0/3, P4 3/3; away 0/3 (`who=alice`, `click1:alice`) — identical to the a2-pass record.
coregd_app: alpha2 prints only `GET_DELTA_SAW theme='bogus-nav'`; stable 0.9.12 prints `'bogus-boot'` and `'bogus-nav'`.

(b) alpha2-ent-a5 (a2 + NEW enterprise a5), dev Redis: stale 0/3, 0/3, 0/3, P4 3/3; away 0/3 — a5 alone does NOT fix N-032
(expected: the auth code is byte-identical a4 → a5; the fix is reflex-side #7493).

(c) s912-ent-a5 (0.9.12 + a5), dev Redis: stale 3/3, 3/3, 3/3, 3/3; away 3/3; xtab 6/6 (race 6/6, all healed by tab2's
return boot) — identical to the a2-pass 0.9.12 + a4 record; a4 auth matrix 36/36 + both MCP checks; a5 does not break 0.9.12.

### N-032 on a3-ent (reflex 0.10.0a3 + enterprise 0.9.7a5) — FIXED

| probe | a3 dev Redis | a3 prod Redis 1 worker | a3 dev memory | a2 + a4 (a2 pass / this pass) | 0.9.12 + a5 |
|---|---|---|---|---|---|
| stale P1 anon boot bogus hash → "" | **3/3** | **3/3** | **3/3** | 0/3 | 3/3 |
| stale P2 signed-in boot re-asserts real hash | **3/3** | **3/3** | **3/3** | 0/3 | 3/3 |
| stale P3 cookies cleared + hash "" → signed out | **3/3** | **3/3** | **3/3** | 0/3 | 3/3 |
| stale P4 control (live storage event) | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| away (clean logout in tab2, Back in tab1) → signed out | **3/3** | **3/3** | **3/3** | 0/3 | 3/3 |
| xtab two-tab race, tab1 logged out | **6/6** (race 1/6, healed) | **6/6** (race 4/6, healed) | **4/4** (race 0/4) | a2 pass: dev 1/6, prod 3/6, memory 4/4 | 6/6 (race 6/6, healed) |

Explorer probes (entauth app, dev Redis): `stale_hash_probe.py` `CORRECTED {"anon_boot": [3, 3], "loggedin_boot": [3, 3],
"live_update": [3, 3]}` (a2: 0/3, 0/3, 3/3); `xtab_probe.py` `TAB1_LOGGED_OUT 5 / 5` (a2: 3/7); `drive_auth_redis.py`
cycle/pubnav/twotab/xtab `ALL_PASSED` (a2: twotab/xtab "stayed").
Boot events now: `hydrate_and_load` then, on a hash mismatch, `/_reflex/cookies/sync` + `reconcile_tokens_after_sync`
(a2: `hydrate_and_load` only; 0.9.12: `hydrate` + `update_vars_internal` + `on_load_internal` + reconcile).
coregd_app on a3: `GET_DELTA_SAW theme='bogus-boot'` exactly once + `'bogus-nav'`, in dev AND prod (like 0.9.12).
Server logs: 0 tracebacks in every vauth run. Console: only the known-benign noise (mock IdP pico.css tunnel error,
favicon 404, cookie-sync keepalive `ERR_ABORTED` on navigation — same counts per sync as 0.9.12).

Behaviour change (LOW, see ISSUE in results): after the boot reconcile resets a stale tab, a3 leaves it on the protected
page with blanked values (who="", clicks 0) until its next protected event (which redirects to /login); 0.9.12 usually
redirects at once (P3: 0.9.12 3/3 on /login; a3 dev 0/3, prod 1/3, memory 0/3; away: 0.9.12 2/3, a3 0/3). No protected
value or action is exposed in either version (the boot snapshot briefly carries `user_sub: alice` before the reset on both).

### #7493 regression hunt (dev Redis unless noted)

| check | a3 | a2 + a4 | 0.9.12 + a5 |
|---|---|---|---|
| fresh anonymous browser (`hunt fresh`, 2 reps): token hash / cookie / client-storage default written? | none (only `theme`, `last_compiled_theme`, `debug` color-mode keys, session `token`) | identical | identical |
| signed-in page loads (`hunt loads`): per boot (reload ×3, new tab /vault, new tab /) | 1 `hydrate_and_load`, 1 hash write (same value echoed back; no storage event), 0 cookie syncs | 1 `hydrate_and_load`, 0 hash writes | `hydrate` + `update_vars_internal` + `on_load_internal`, 1 hash write |
| client nav / → /vault | 1 `update_vars_internal`, 1 hash write | same | same |
| 10 s idle with 3 tabs | 0 events (no loops) | 0 | 0 |
| totals per run (cookie syncs) | 1 (the login) | 1 | 1 |
| `hunt relogin` alice → add → reload → logout → bob on same tab → reload → add → new tab | 2/2 dev, 2/2 prod 1w | 2/2 | — |
| protected client storage (`storx`, vauthx): reload / new tab /vault / new tab `/` keeps alice's `vx_draft`/`vx_ck` | kept | kept | **wiped** on new-tab boot (LocalStorage) |
| …any client-side navigation while signed in (Redis; see the extended table below) | **wiped** (both written as "") | **wiped** | **wiped** |
| `hydration_token_probe.py` flags (entauth) | reload_writes ✓, newtab_writes ✓, garbage_* = 0.9.12 flags | same | same |
| proactive refresh (75 s tokens, idle 120 s) | refreshed at +69 s, still Alice, protected event allowed | (a2 pass: pass) | — |

=> no duplicate cookie syncs, no reconcile loops, F-002 not back from the auth angle; the extra hash write per boot is
the documented trade-off of #7493 (0.9.12 did the same). The protected-storage wipe on client navigation to a public page
is pre-existing on all three versions (enterprise delta filter: `update_vars_internal` under the Redis manager does not resolve
the user, so the protected vars are replaced by their anonymous placeholders and the browser persists them) — reported as
a pre-existing finding; a3 is no worse than a2 and better than 0.9.12 at boot.

Harness note: `/pid` (vauth, `auth=False`) redirects anonymous users to /login on every version because its
`on_load=PidState.load_pid` handler lives on a default-protected state (secure by default gates the handler) — fixture
design, not a finding (`hunt pubslash`).

### N-033 on a3-ent, prod, default workers (9), Redis — UNCHANGED (enterprise)

| | a3 + a5 | a2 + a4 (a2 pass) | 0.9.12 + a4 (a2 pass) |
|---|---|---|---|
| fresh server: 27 POST `/_reflex/cookies/sync` | **27/27 405** over 8 pids | 27/27 405 (8 pids) | 27/27 405 (9 pids) |
| 6 full logins: token cookies stored | **3/6** (every failure: its single sync POST hit a cold pid → 405; new tab → /login) | 1/6 | 1/6 |
| 27 POSTs after the logins | 18×400 / 9×405 (3 pids still cold) | 19×400 / 8×405 | 22×400 / 5×405 |
| `storm` (failed-sync login + second tab) | 2 failed-sync logins: 40 and 16 POSTs in the first 5 s, then both ended by logging the login tab out; 3rd attempt found no cold worker in 6 logins | 1/3 sustained ~115 POSTs/s for 40 s, 2/3 ended in 5 s | (logins runs: 336-409 POSTs per tab) |
Logs: `logs/a3e-prod-9w-post-*.txt`, `logs/a3e-prod-redis-9w-{logins,storm}.json`, server log `logs/a3e-prod-redis-9w.server.log`.
The 405 rate still equals the share of cold workers; the lower login failure count is within warm-up noise (each boot
reconcile now builds `HTTPCookie.sync()` and warms a worker, as on 0.9.12).

### MCP on a3-ent dev Redis (entauth)
`check_mcp_anon.py --rate` and `check_mcp_oauth_redis.py`: structurally identical to the a2-pass results
(`drivers/json_cmp.py` diff: only dict key order, one more handler (the app copy has `fill_loaded`), and +1-2 websocket
frames per browser flow = the boot echo delta). Parallel 2×20 bumps = 40, rate limits (61st read, 429 token grants),
upload tickets, background tool, OAuth registration/consent/deny/PKCE/refresh rotation/replay/revoke all pass.
Pre-existing I-6 unchanged: `scoped_write` denied by token scope returns `{"is_error": false, "delta": {}}`.
Server log: the known ERROR + traceback for the anonymous read of the protected resource (2 tracebacks, same as a2).

### Prod suite on a3-ent (entauth, single port 8341, Redis, `GRANIAN_WORKERS=1`, `scripts/prod_suite.sh`)
`logs/prod-suite-a3e.out`: `drive_auth_redis.py` cycle/pubnav/twotab/xtab **ALL_PASSED** (a2: twotab/xtab stayed signed in);
`xtab_probe.py` ×5 **TAB1_LOGGED_OUT 5/5** (a2 prod 3/5); `stale_hash_probe.py` ×2 **CORRECTED 2/2, 2/2, 2/2** (a2 prod 0/2,
0/2, 2/2); hydration_token_probe reload_writes ✓ newtab_writes ✓; bglive `direct` not live (pre-existing N-034, same as a2);
MCP OAuth + anonymous prod: structurally identical to a2 prod (`json_cmp.py`: key order, +1 handler, +1-2 boot frames).
Server log: 2 tracebacks = the known anonymous protected-resource read (as a2).

### Protected client storage, extended (`storx.py`, vauthx with /vault2; `bin/run_storx.sh`, labels `*-v2`)
| step (alice signed in unless noted) | a3 Redis | a2 Redis | 0.9.12 Redis | a3 memory |
|---|---|---|---|---|
| reload /vault, new tab /vault, new tab / | kept | kept | **wiped** (new-tab boot) | kept |
| client nav /vault → /vault2 (both protected) | **wiped** | **wiped** | **wiped** | kept |
| client nav /vault2 → /vault, /vault → / | **wiped** | **wiped** | **wiped** | kept |
| anonymous boot with leftover protected values in the browser | blanked ("" written) | left in browser (not shown) | blanked | blanked |
=> pre-existing enterprise bug with Redis (`a3_ent_auth-3`): `update_vars_internal` does not load `AuthUserState`, the delta
filter fails closed and the browser persists the "" placeholders. a3's boot behaviour equals a2's for signed-in tabs and
0.9.12's for anonymous leftovers (consistent with the filter's "blank stale authed values" design).

### 10-05 a4 auth matrix (dev, memory manager; `scripts/a4_matrix.sh <venv> <label>`, `bin/a4_tally.sh <label>`)
| part | a3 + a5 | 0.9.12 + a5 | a2 + a4 (a2 pass) |
|---|---|---|---|
| full upstream auth app (22 cases) | 22/22 | 22/22 | 22/22 |
| public nav + 2 reloads | 3/3 | 3/3 | 3/3 |
| auth_min default | 4/4 | 4/4 | 4/4 |
| auth_min extra scopes | 4/4 | 4/4 | 4/4 |
| iframe pending replay | 3/3 | 3/3 | 3/3 |
| **total** | **36/36** | **36/36** | 36/36 |
| MCP OAuth / anonymous MCP | pass / pass | pass / pass | pass / pass |
0 page errors, 0 server tracebacks; failed requests are the known cookie-sync keepalive aborts (a3: 21/11/10, a2: 21/10/11)
and 3 dev route-module aborts. Logs: `apps/a4auth/logs/{a3e,s912e5}/`.

### Maps (`scripts/drive_maps.py`, mapsapp; dev 3344/8344 and prod 8345 default workers, Redis)
a3 dev **16/17**, a3 prod (9 workers) **16/17** — the one miss is the pre-existing `on_layeradd` never firing (a2 and 0.9.12
identical). 200 markers, drag → State, background ticker live (8 distinct geometries, 0 long tasks), reload restores
state, base-layer/overlay switching from State, geolocation denied/granted all pass. 0 tracebacks; console only the
favicon 404. Logs `logs/maps-a3e-{dev,prod}-redis.out`, `logs/maps-{dev,prod}-redis-a3e.log`.

### Not covered
- `a3-ent-a4` (a3 + OLD enterprise a4): not in this item's brief (N-032's fix is reflex-side, the a4 auth code equals a5's,
  so a3 + a4 is expected to behave like a3 + a5 for auth).
- a4 matrix in prod; two-provider (`AUTH_MULTI=1`) variant; Redis restart mid-session; expiry scenarios other than
  `proactive`; bglive `loaded` variant on a3.

## VERIFICATION

Verifier `verify_ent_auth` (independent; own app + driver built from the FINDINGS/inbox text before opening the explorer's
apps/drivers, then the explorer's fixtures re-run). Verdicts: **A3-10 CONFIRMED (and broadened), MEDIUM, pre-existing, enterprise**;
**A3-09 NARROWED, LOW, enterprise** (a3 behaviour confirmed; the 0.9.12 "redirect" is the outcome of a race, not a guarantee).
Artifacts: `verification/` (app `app/` = `vea`, `bin/`, `drivers/`, `drivers_explorer_copy/`, `out/*.json.gz`, `out_vdrv/*.json.gz`,
`logs/*.trimmed.log`, `shots/*.jpg`). Inbox: `../board/findings-inbox/verify_ent_auth-{1,2}.md`.

### Setup (verifier ports 3620/8620 dev, 8621 prod single port, redis 8629, mock IdP 8638)
```sh
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/verify_ent_auth
V=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_ent_auth/verification
mkdir -p $W/{bin,drivers,scripts,logs,shots,run,out}; cp $V/bin/*.sh $W/bin/; cp $V/drivers/*.py $W/drivers/; cp $V/scripts/mock_oidc.py $W/scripts/
mkdir -p $W/vea_src; cp -r $V/app/* $W/vea_src/; for t in a3e s912e5 a2e; do mkdir -p $W/vea_$t; cp -r $W/vea_src/* $W/vea_$t/; done
$W/bin/infra.sh start          # redis :8629 + oidc-provider-mock (2026-10-07/ent_auth/scripts/mock_oidc.py, guard -> a3-ent, port 8638)
redis-cli -p 8629 flushall; VEA_INSTRUMENT=1 $W/bin/start.sh a3-ent vea_a3e dev $W/logs/a3e-dev-redis.server.log
#   MGR=disk|memory (no Redis), VEA_FIX=1 (causality probe), GRANIAN_WORKERS=1 ... prod (base http://localhost:8621)
$W/bin/wait.sh http://localhost:3620/ http://localhost:8620 420
cd $W/drivers; DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
$DRV vea_drv.py storx|xsync|stale|away|live|stalenav http://localhost:3620 <label> <reps>   # -> ../out/<label>-<scen>.json
$DRV summ.py ../out/<label>-{stale,away,live}.json; $DRV frames.py ../out/<label>-stale.json 0   # A3-09 summary / ws timeline
grep VEA_FILTER $W/logs/<log>      # instrumented filter: which deltas were rewritten and whether AuthUserState was in the tree
$W/bin/stop.sh; $W/bin/infra.sh stop
```
App `vea`: `rxe.Config(plugins=[AuthPlugin()])` (secure default). `Vault(rx.State)` (default-protected): `secret` (plain field),
`draft = rx.LocalStorage(name="vea_draft", sync=True)`, `plain = rx.LocalStorage(name="vea_plain")`, `ck = rx.Cookie(name="vea_ck")`,
`ss = rx.SessionStorage(name="vea_ss")`; protected events `fill` (writes `*-of-<sub>` everywhere) and `show_server` (echoes what the
BACKEND holds for the four client-storage vars). Control `Pub(rx.State)`: `rxe.field(rx.LocalStorage(..., sync=True), auth=False)` +
`rxe.field(rx.Cookie(...), auth=False)`, public `pfill`. Pages `/` (auth=False), `/vault`, `/vault2` (secure default), `rx.link` nav.
`VEA_INSTRUMENT=1` wraps `enforcement.filter_protected_delta` (logs rewritten keys + whether `_get_state_from_cache(AuthUserState)`
succeeds); `VEA_FIX=1` makes `AuthMiddleware.preprocess` call `resolve_userinfo(state)` before `update_vars_internal` (what the gate
already does for `hydrate`/`hydrate_and_load`). Explorer fixtures re-run from copies: `vauth`, `vauthx` apps unchanged;
`drivers_explorer_copy/vdrv.py` = `drivers/vdrv.py` with only the IdP port (8358 -> 8638) and OUT/SHOTS dirs changed; `storx.py`,
`hunt.py` unchanged; `storx_table.py` reads `../out_vdrv`.

### A3-10 — protected client storage erased (CONFIRMED, broadened)
`storx` (sign in alice, `fill`, then client nav /vault -> /vault2 -> /vault -> /, reload, `show_server`) and `xsync` (two tabs of one
browser on /vault, `fill` in tab A, no navigation):

| build / manager | client nav: draft, plain, ck, ss in UI + browser | backend after nav (`show_server`) | backend after next reload | xsync: tab A's own `draft` after 4 s | `auth=False` controls |
|---|---|---|---|---|---|
| a3 + a5, dev, Redis | **"" (all four), every nav** (3/3 navs) | still `draft-of-alice` | **""** (re-seeded from the browser) | **""** (2/2) | kept, synced |
| a3 + a5, dev, Redis, `VEA_FIX=1` | kept | kept | kept | kept; tab B receives it | kept |
| a3 + a5, dev, disk (default) / memory | kept | kept | kept | kept; tab B receives it | kept |
| a3 + a5, prod, Redis, 1 worker | **""** | still alice's | **""** | **""** (1/1) | kept |
| a3 + a5, prod, Redis, 9 workers | **""** (2/2) | still alice's | **""** | **""** (1/1; rep 2 lost its login = N-033) | kept |
| 0.9.12 + a5, dev, Redis | **""** | still alice's | **""** | **""** | kept |
| a2 + a4, dev, Redis | **""** | still alice's | **""** | **""** | kept |
| explorer `vauthx` + `storx.py`, a3 dev Redis | **""** on 3c/3d/4 (2/2 reps) | – | – | – | – |

Wire evidence (a3 dev Redis, `out/a3e-dev-redis-storx.json.gz`): the nav's `update_vars_internal` carries
`vault.draft="draft-of-alice"`, `ck="ck-of-alice"`, ...; the reply delta carries `vault: {draft:"", plain:"", ck:"", ss:""}` next to
`pub: {pdraft:"pub-draft", pck:"pub-ck"}` unchanged; `applyClientStorageDelta` then writes "" to localStorage/cookie/sessionStorage.
Server log: `VEA_FILTER ... state=vea___vea____vault auth_user=NOT-LOADED(ValueError) defer=True changed={'draft_rx_state_':
('draft-of-alice', ''), ...}` once per navigation (and once per storage-event sync in `xsync`); never with disk/memory or `VEA_FIX=1`.
xsync chain: A's `fill` writes localStorage -> storage event in B -> B sends `update_vars_internal{draft: "draft-of-alice"}` -> B's
delta rewritten to "" -> B writes "" -> storage event in A -> A sends `update_vars_internal{draft: ""}` -> A's value gone (~1 ms).
Answers to the brief: not specific to `sync=True` (plain LocalStorage, Cookie and SessionStorage are erased by navigation too;
`sync=True` adds a second trigger that needs no navigation, only a second open tab); affects every protected client-storage var
(default or explicit `auth=True`; a callable check also withholds when no user is resolved), never `auth=False` ones; the trigger is
`update_vars_internal` (an exempt framework state, so `AuthMiddleware.preprocess` returns before `resolve_userinfo`; only
`hydrate`/`hydrate_and_load` load `AuthUserState` on that branch); Redis only (partial state tree), dev and prod (1 and 9 workers);
cause confirmed by instrumentation + the `VEA_FIX` counter-experiment. User data: the backend keeps the value until the tab's next
boot, which re-seeds it from the now-empty browser storage -> lost on both sides. Same root cause as N-034 (enterprise#263,
identity read only from the event's tree cache); here the fail-closed placeholder is PERSISTED by the browser, so it is data loss,
not just a stale display. Workaround: `rxe.field(rx.LocalStorage(...), auth=False)`.

### A3-09 — stale tab left blanked on the protected page (NARROWED)
`stale` = tab1 signed in on /vault (after `fill`) goes to same-origin `/blank.html`, cookies cleared + token hash "" written, tab1
returns to /vault; `away` = tab1 leaves, tab2 logs out via /logout + IdP end_session, tab1 Back; `live` = tab1 stays open while tab2
logs out (P4 analogue). "stay" = tab ends on /vault with who="" and every protected value blanked.

| build | my app `vea` stale | `vea` away | `vea` live | explorer `vauth` + `vdrv.py` P3 | `vauth` away | `vauth` P4 (live) |
|---|---|---|---|---|---|---|
| a3 + a5 dev Redis | stay 3/3 | stay 3/3 | stay 3/3 | stay 3/3 | stay 3/3 | stay 3/3 |
| 0.9.12 + a5 dev Redis | **stay 3/3** | **stay 3/3** | stay 3/3 | /login 3/3 | /login 3/3 | stay 3/3 |
| a3 + a5 prod Redis 1 worker | stay 3/3 | stay 2/3, /login 1/3 | – | (explorer: /login 1/3) | – | – |
| 0.9.12 + a5 prod Redis 1 worker | stay 1/3, /login 2/3 | stay 2/3, /login 1/3 | – | – | – | – |

In every "stay" case: a protected click redirects to /login in ~0.2 s (vea 9/9 a3, 9/9 0.9.12; vauth 6/6), a client-side nav to
another protected page redirects to /login (`stalenav` 2/2), public events still work; nothing protected is rendered after the reset.
Pre-existing on both versions: before the reset the boot snapshot renders the previous user's protected values (`secret-of-alice`;
DOM mutation log): a3 dev 6–20 ms, 0.9.12 dev 30–51 ms, a3 prod 24–221 ms, 0.9.12 prod 19–178 ms.
Mechanism (frames): 0.9.12 sends `hydrate`, `update_vars_internal`, `on_load_internal`; the hash mismatch in `update_vars_internal`'s
delta triggers the `/_reflex/cookies/sync` POST; whether the POST lands before the `on_load_internal` page guard decides the outcome
(vauth: POST first -> guard sees no tokens -> `/login`; vea: guard first -> allowed, then `reconcile_tokens_after_sync` ->
`reset_auth` blanks the page). a3 chains `on_load_internal` server-side from `hydrate_and_load`, so the guard nearly always wins
(prod 1/6 lost it). The live cross-tab logout (P4) never redirects on any version: `reset_auth` (enterprise `oidc/state.py:868`)
resets state and syncs cookies but does not re-run the page guard. => a3 changes the odds of a pre-existing race; not a
deterministic regression, no exposure; fix belongs in enterprise (redirect/re-guard after the reconcile reset).

### Noise seen (benign / known)
mock IdP page's pico.css `ERR_TUNNEL_CONNECTION_FAILED`, cookie-sync keepalive `ERR_ABORTED` on navigation, granian
`Unexpected exit from worker-1` at shutdown, Radix implicit-enablement + `disable_plugins` string deprecation warnings (my config),
prod 9-worker xsync rep 2 lost its login (N-033 cold-worker cookie sync). 0 server tracebacks in all 16 runs.
