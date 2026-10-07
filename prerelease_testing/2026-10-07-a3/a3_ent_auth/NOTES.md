# a3_ent_auth — N-032 (reflex#7493) on reflex 0.10.0a3 + reflex-enterprise 0.9.7a5, OIDC/MCP/maps regression sweep

Status: IN PROGRESS (Phase A: harness positive controls and a5/0.9.12 baselines, before a3 is on PyPI).

## Environment

```sh
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_ent_auth            # work dir; this DEST dir mirrors it (apps/, bin/, drivers/, scripts/, logs/, shots/)
```
Shared, read-only venvs (Python 3.12; nothing installed by this item):
- `$SB/envs/alpha2-ent`    reflex 0.10.0a2 + OLD offline enterprise 0.9.7a4 (the a2-pass state; positive control)
- `$SB/envs/alpha2-ent-a5` reflex 0.10.0a2 + NEW offline enterprise 0.9.7a5
- `$SB/envs/s912-ent-a5`   reflex 0.9.12 + enterprise 0.9.7a5 (baseline)
- `$SB/envs/a3-ent`        reflex 0.10.0a3 + enterprise 0.9.7a5 (UNDER TEST; built by the orchestrator)
- `$SB/envs/alpha2`, `$SB/envs/stable`, `$SB/envs/a3` — core only, for `coregd_app`
- `$SB/envs/driver` (playwright 1.63, Chromium `/opt/pw-browsers/chromium`); `$SB/envs/ent_auth2-drv` (a2 + a4 wheel +
  playwright + mcp; used ONLY as the client interpreter of the a4-matrix / MCP drivers, the servers run on the venv under test)

Ports (item range): vauth/entauth dev 3340/8340, prod single port 8341; a4 `auth` 3342/8342, `auth_min` 3343/8343,
`components` backend-only 8346; maps dev 3344/8344, prod 8345; coregd 3347/8347; redis 8349; mock OIDC 8358.
Every server: `CI=true REFLEX_TELEMETRY_ENABLED=false AUTHLIB_INSECURE_TRANSPORT=1 OIDC_ISSUER_URI=http://localhost:8358`
(+ `REFLEX_REDIS_URL=redis://localhost:8349` unless `NOREDIS=1`), `--loglevel debug`. `bin/start_app.sh` first runs a venv
guard from a neutral dir and writes `VENV_GUARD venv=... reflex X reflex-base Y reflex-enterprise Z` as line 1 of the server log.

## Fixtures (copied from the a2 pass, `../../2026-10-07/ent_auth/`)
- `apps/vauth/` = a2 verifier app (`verification/app`), unchanged. Per-venv copies in `$W/vauth_<tag>/` (own `.web`).
- `apps/coregd_app/` = core-only `get_delta` override app (`verification/coregd_app`), unchanged.
- `apps/entauth/`, `apps/mapsapp/`, `apps/a4auth/` = explorer apps + 10-05 a4 matrix (with its `reference/` upstream tests
  copied from `../../2026-10-05/enterprise/a4/auth/reference/`).
- `drivers/vdrv.py` (a2 verifier driver) — only change: mock IdP port 8738 → 8358, venv guard. `drivers/coregd_drv.py` + guard.
- `scripts/` = explorer scripts; only change: work dir `apps/ent_auth2` → `apps/a3_ent_auth` (ports were already this range).
- `bin/start_app.sh <venv> <appdir> <dev|prod> <log>` (env: `GRANIAN_WORKERS`, `VAUTH_PID_HEADER`, `NOREDIS=1`, `FP/BP/PP`),
  `bin/stop_app.sh`, `bin/wait_ready.sh`, `bin/post_sync.sh`, `bin/infra.sh` (= `scripts/infra.sh`: redis 8349 + mock 8358),
  `bin/sync_dest.sh`.

## Rerun commands

```sh
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_ent_auth
# fresh work dir from this DEST: mkdir -p $W/{logs,shots,screenshots,run}; cp -r bin drivers scripts $W/;
#   cp -r apps/vauth $W/vauth_src; cp -r apps/coregd_app $W/coregd_src; cp -r apps/entauth $W/entauth_src; cp -r apps/mapsapp $W/mapsapp_src; cp -r apps/a4auth $W/a4auth
for t in a2e a2e5 s912e5 a3e; do mkdir -p $W/vauth_$t; cp -r $W/vauth_src/* $W/vauth_$t/; done
for t in a2 s912 a3; do mkdir -p $W/coregd_$t; cp -r $W/coregd_src/* $W/coregd_$t/; done
$W/bin/infra.sh start
export DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
# N-032 probes (per build: alpha2-ent/vauth_a2e, alpha2-ent-a5/vauth_a2e5, s912-ent-a5/vauth_s912e5, a3-ent/vauth_a3e)
redis-cli -p 8349 flushall
$W/bin/start_app.sh alpha2-ent vauth_a2e dev $W/logs/a2e-dev-redis.server.log
$W/bin/wait_ready.sh http://localhost:3340/ http://localhost:8340 400
cd $W/drivers && $DRV vdrv.py stale http://localhost:3340 a2e-dev-redis 3 && $DRV vdrv.py away http://localhost:3340 a2e-dev-redis 3
$DRV vdrv.py xtab http://localhost:3340 <label> 6; $DRV race.py ../logs/<label>-xtab.json
$W/bin/stop_app.sh
# core-only get_delta fixture
FP=3347 BP=8347 NOREDIS=1 $W/bin/start_app.sh alpha2 coregd_a2 dev $W/logs/coregd-a2.server.log
$W/bin/wait_ready.sh http://localhost:3347/ http://localhost:8347 400
cd $W/drivers && $DRV coregd_drv.py http://localhost:3347 > $W/logs/coregd-a2.driver.out; grep GET_DELTA_SAW $W/logs/coregd-a2.server.log
$W/bin/stop_app.sh; $W/bin/infra.sh stop
```

## Results so far

### Phase A (a) — positive control: harness reproduces N-032 on the a2-pass state

| probe | alpha2-ent (a2 + ent a4), dev Redis | a2-pass record |
|---|---|---|
| stale P1 anon boot bogus hash corrected | 0/3 | 0/3 |
| stale P2 signed-in boot re-asserts real hash | 0/3 | 0/3 |
| stale P3 cookies cleared + hash "" → signed out | 0/3 | 0/3 |
| stale P4 control (live storage event) | 3/3 | 3/3 |
| away (logout in tab2, tab1 Back) signed out | 0/3 (tab1 `who=alice`, `click1:alice`) | 0/3 |

coregd_app: alpha2 prints only `GET_DELTA_SAW theme='bogus-nav'` (boot value missing); stable 0.9.12 prints
`'bogus-boot'` and `'bogus-nav'`. Harness OK. Logs: `logs/a2e-dev-redis-{stale,away}.json`, `logs/coregd-{a2,s912}.*`.
