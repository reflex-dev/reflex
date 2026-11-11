# Phase 7 re-verification: enterprise group (reflex 0.11.0a2 + reflex-enterprise 0.9.12)

Date: 2026-11-11. Every run used published packages only. Evidence, scripts and app copies are in `phase7/enterprise/`
(`scripts/`, `src/`, `out/`, `logs/`, `shots/`; 0.5 MB; grepped clean of access-token strings). Work dir:
`$OLDSB/p7/work/ent/`. Ports: frontend/single 3380 (3386-3389 for fixture demo runs), backend 8380 (8387/8389), mock IdP
8398, account stub 8397. All servers, the IdP, the stub and the browsers were stopped at the end; ports 3380-3399 and
8380-8399 are free.

## Venvs used, and their integrity

Every venv below passed `cd /tmp && <venv>/bin/python -I $OLDSB/p7/work/cm/scripts/verify_record.py` (OK). My own
RECORD checker, `scripts/verify_record.py`, gave the same result.

| role | venv | contents |
|---|---|---|
| system under test | `$P7/ent-0912` | reflex 0.11.0a2, reflex-base 0.11.0a2, reflex-enterprise[mcp] 0.9.12 |
| control (rxe side) | `$P7/ent-0911` | reflex 0.11.0a2 + reflex-enterprise 0.9.11 |
| clean 0.11.0a1 control (reflex side) | `$OLDSB/p7/work/ent/envs/a1ent-clean` | reflex[db] 0.11.0a1 + reflex-enterprise[mcp] 0.9.11 + redis 8.2.0b1, built with a private `UV_CACHE_DIR` and `--link-mode=copy` |
| 0.10.1 baseline | `$OLDSB/envs/vent-prev` | reflex 0.10.1 + reflex-enterprise[mcp] 0.9.11 + faker/pandas (verified OK) |
| browser driver | `$P7/driver` | playwright |
| MCP OAuth client | `$OLDSB/envs/enterprise-entdrv` | used only for its mcp, httpx and playwright client libraries; the script does not import reflex |
| mock IdP | `$OLDSB/envs/vent-idp` | oidc-provider-mock |

**Contamination, found independently before the orchestrator's heads-up.** My first 0.11.0a1 control used
`$OLDSB/envs/new-ent` and passed the agapi repro, which should have failed. In that venv,
`reflex_base/components/component.py` does not match its RECORD hash: line 1840 adds an implicit
`ImportVar(tag="refs")`. `reflex/istate/manager/redis.py` is modified too. The file is a hardlink, with 57 links, to
`/root/.cache/uv/archive-v0/Q-gRUxuTKMN1xaM5/reflex_base/components/component.py`. That makes the uv cache entry itself
patched, so any venv built from that cache gets the patch. The affected venvs are `$OLDSB/envs/new-ent`,
`$OLDSB/envs/vent-new` and `$P7/ctrl-0.11.0a1`, plus venvs under `/tmp/claude-0/-home-user/.../apps/fix033`, `fix044` and others.
I discarded that control result; its output is kept as `out/f003_agapi_a1_control_CONTAMINATED_new-ent.txt`. I then built
`a1ent-clean`, and it reproduces every original 0.11.0a1 failure. The ag_grid demo needs faker and pandas, which are not
in the p7 venvs. They come from a separate `--target` overlay dir (`$OLDSB/p7/work/ent/overlay`) on `PYTHONPATH`, and no
venv was modified.

## Results

| finding | fix | 0.9.12 result | 0.9.11-on-a2 control | evidence |
|---|---|---|---|---|
| FINDING-002 MCPPlugin app dies at `reflex run --env prod` without `deploy_url` | rxe#290 (`resolve_server_url`: `deploy_url or api_url`) | **PASS**. `mcpmin` prod starts with no ConfigError. The MCP endpoint answers: anonymous token grant 200, `initialize` 200, `tools/list` (search_events, queue_event), `resources/list` and `tools/call search_events` all return 200 and list `s.bump`. With `REFLEX_API_URL=https://myapp.example.com`, the 401 advertises `https://myapp.example.com/...`. `REFLEX_DEPLOY_URL` and dev also work. | **reproduces**: `server exited`, `ConfigError: MCP OAuth needs the app's public origin ...` | `out/f002_0912_prod_mcp.txt`, `out/f002_variants.txt`, `logs/f002_0911_prod_ConfigError.txt` |
| FINDING-003 `refs[...]` throws `ReferenceError: refs is not defined` (AG Grid API, aligned_grids) | reflex#7806 (`globalThis.refs`) + rxe#290 (`_as_ref()` carries the import) | **PASS**. agapi dev+prod 3/3/3 with 0 ReferenceErrors. aligned_grids dev+prod 276/276. memo3 (API button in another module, no id) dev+prod 3 rows. Upstream demo features 46/47 in prod and in dev, the 0.10.1 number (0.11.0a1 had 39/48). The compiled module now imports `refs` explicitly. With the reflex-side global deleted in the browser, the grid still works, so the rxe fix works on its own. | **Works on a2.** The reflex global alone fixes 0.9.11's grid: agapi dev+prod, aligned and memo3 all PASS, and the demo gets 46/47. The module imports only `useRegisteredRef`, so 0.9.11 depends on the global: with `globalThis.refs` deleted it fails (0 rows). | `out/f003_agapi.txt`, `out/f003_aligned_memo3.txt`, `out/f003_compiled_imports.txt`, `out/f003_agapi_noglobal.txt`; clean-a1 control (FAIL, 6/22 ReferenceErrors): `out/f003_agapi_a1clean_control.txt`, `logs/f003_a1clean_ReferenceError.txt` |
| FINDING-008 MCP OAuth consent redirect points at the backend origin in dev (404) | rxe#290 (`deploy_url`, then `frontend_url` with split ports, then the issuer) | **PASS**. Dev `/authorize` → `302 http://localhost:3380/agent-consent` → 200. The full browser flow passes in dev: discovery, DCR, mock-IdP login, consent approve, PKCE exchange, code-replay 400, protected `reveal` over MCP = `revealed-alice`, refresh rotation, refresh-replay 400. Prod single-port: consent stays on the issuer origin (correct), and the full flow passes when the MCP client uses `/_reflex/mcp/`; see ENT-26 below. | **reproduces**: `302 http://localhost:8380/agent-consent` → 404. The browser flow times out. | `out/f008_consent.txt`, `out/f008_prod_and_prm.txt`, `out/oauthflow/mcp-oauth_0912_{dev,prod}.json` |
| FINDING-009 `reflex db migrate` exits 1 on a fresh rxe app | reflex#7817 (`evaluate_pages` skips initial-state compile) | **PASS**. Fresh ag_grid demo: `db migrate` rc 0 and `db init` rc 0, both creating `friend` + `alembic_version`. `compile`, then `migrate`: rc 0. `makemigrations` after `init`: rc 0. | **PASS** too, since the fix is reflex-side: same matrix, all rc 0. Positive control `a1ent-clean`: `migrate` / `init` / `makemigrations` rc 1 `ValueError: Library @radix-ui/themes is not bundled`. 0.10.1: `migrate` 0, `init` / `makemigrations` 1. | `out/f009_agdemo_matrix.txt`, `logs/f009_a1clean_migrate_ValueError.txt` |
| FINDING-021 `rxe.Config(use_single_port=True)` dev proxy never mounts | none (pre-existing, not in this train) | **still reproduces**. Backend `GET /` 404, log `Unable to find the base Starlette app. Proxying will not be enabled.` (printed via the deprecated `console.error`, proxy.py:135) | same | `out/f021_single_port.txt`, `logs/f021_0912_dev_tail.txt`, app `src/single` |

On the `fresh migrate` row, a2 also prints `Updated env.py to load the app; the previous one is kept as alembic/env.old`
on the demo that ships its own stock `env.py`. This is #7742 behaviour, already noted in the a1 pass, and it is the same
on a1.

On the `makemigrations` row, the case run on a fresh DB right after copying exits 1 with
`Target database is not up to date. Run reflex db migrate`. That is alembic's normal precondition, because the demo ships
revisions. It is not the FINDING-009 error.

## Enterprise regression smoke (ent-0912)

Upstream demos come from reflex-enterprise tag v0.9.12. `demos/` is byte-identical to v0.9.11 (`git diff v0.9.11 v0.9.12 -- demos`
is empty). The runs used the fixture drivers from the a1 pass (`$OLDSB/apps/enterprise/fx/grid`, run through
`scripts/smoke_seq.sh` with a shim `SB` whose `envs/` symlink to the p7 venvs). The prod runs used the account stub.

| demo | prod | dev | browser console / page errors / failed requests / 4xx-5xx | server log | vs a1 pass |
|---|---|---|---|---|---|
| ag_grid | smoke 20/20, coldefs 7/7, **features 46/47**, model 24/29 | same | prod: only AG Grid #129 warnings (benign). dev: 2 React DOM-nesting errors on `/qa-model-workaround` (rxe model add-dialog, NEW-ISSUE 2) | 2 tracebacks = the known `met` string → SQLite DateTime, as on 0.10.1 | features 39/48 → 46/47 (FINDING-003 fixed). The clipboard miss and the 5 model misses are the known pre-existing ones (ENT-32 / driver assumption). |
| ag_grid on ent-0911 (control) | identical to 0.9.12: 20/20, 7/7, 46/47, 24/29 | — | benign only | 2 known | — |
| dnd | 27/27 | 27/27 | clean | 0 tracebacks | same |
| flow | 21/22 | 22/22 | clean | 0 tracebacks | same. The prod miss is the known driver assumption: the index lists a 7th "Built with Reflex" entry. |
| mantine | 23/23 | 23/23 | clean | 0 tracebacks | same |
| map | 4/4 | 4/4 | 54 `ERR_TUNNEL_CONNECTION_FAILED` for OpenStreetMap tiles (sandbox blocks them, benign) | 0 tracebacks | same |

Summaries: `out/smoke_seq.txt`, `out/smoke_channels.txt`, per-driver output in `out/smoke/`. The prod agapi page logs one
404, for `/favicon.ico`; the app has no assets dir, which is benign.

### Deprecated reflex APIs that the 0.9.12 wheel still calls (warnings users cannot fix)

Runtime warnings came from the server logs of these runs, attributed to `reflex_enterprise/...`. The rest is a static
grep of the wheel against the a2 `console.deprecate(feature_name=...)` list.

| rxe 0.9.12 location | deprecated API (version → removal) | seen at runtime | when |
|---|---|---|---|
| `components/ag_grid/aggrid.py:1760` | `ArrayVar.foreach` (0.9.7 → 1.0) | yes | every grid that compiles the event-columns mapping |
| `components/ag_grid/datasource.py:182` | `ArrayVar.foreach` | yes | SSRM / infinite datasource |
| `components/ag_grid/wrapper.py:463` (reported at :481) | form control submitted by `id` (0.10.1 → **0.12.0**) | yes (3 per model) | `rx.checkbox(id=field)` for bool columns in the model wrapper's add dialog. After 0.12.0, bool fields are dropped from the submit (NEW-ISSUE 2). |
| `components/dnd/dnd.py:144` | `VarData(position=...)` (0.10.1 → 1.0) | static (known from the a1 pass) | dnd components |
| `auth/cookie.py:363` | `rx.event.fix_events()` (0.9.0 → 1.0) | static (path not exercised here) | HttpOnly cookie `notify_sync` |
| `app.py:159`, `plugins/api_tokens.py:114`, `plugins/mcp.py:1564`, `proxy.py:135` (+15 more `console.*` calls in `app.py`, `aggrid.py`, `resources/base.py`, `wrapper.py`, `event_handler_api.py`, `utils.py`) | `console.info/debug/error` (0.9.9 → 1.0) | yes: api_tokens/mcp on every MCP start without Redis, app.py/proxy.py with `use_single_port` | known ENT-08 family, unchanged |
| `config.py:22` | strings in `disable_plugins` (0.8.28 → 1.0) | yes | User-fixable (the demo passes strings), but the warning location points into rxe's `Config.__init__`, not the user's rxconfig. |

`vars.py:42` (`dynamic.bundled_libraries`) is only a fallback for an old reflex, and nothing printed it on a2. The
`self.router.page.params` text in MCP instructions/tool descriptions (`mcp.py:1443`, `mcp_auth/tools.py:406,433`,
`event_handler_api.py:645`) tells agents and users to use `RouterData.page`, which has been deprecated since 0.8.1 ("Use
RouterData.url"). That is documentation, not a runtime call.

### Follow-up items from rxe#290 (status only, not filed)

- **`collect_page_info` relative paths: still open in 0.9.12.** `base_url = (config.deploy_url or "")` is unchanged. In
  prod with `REFLEX_API_URL=https://myapp.example.com` and no deploy_url, the MCP `initialize` instructions say
  `The app is served at https://myapp.example.com.` and then list the pages as `` `/index` ``, `` `/404` ``, which are
  relative. With `REFLEX_DEPLOY_URL` set, the pages are absolute.
  - Side observation, pre-existing on 0.10.1 + 0.9.11 too: the root page is listed as `/index`, not `/` (`_unevaluated_pages` key).
  - Evidence: `out/f002_variants.txt` and the instructions lines in this report (probe `scripts/mcp_probe.py`).
- **`/.well-known/oauth-protected-resource/_reflex/mcp` returning app HTML in single-port prod.** The a1 observation
  came from `mcpmin`, which has MCPPlugin and no AuthPlugin, so OAuth is not enabled.
  - **With OAuth enabled (`auth_min`), the PRM is served correctly**: 200 `application/json`, `resource=http://localhost:8380/_reflex/mcp`, in prod and in dev, on 0.9.12 and on 0.10.1.
  - **In anonymous mode (no AuthPlugin), the route does not exist at all**: 404 HTML in prod, 404 text in dev. RFC 8414 metadata is 404 as well. The MCP 401 still sends `WWW-Authenticate: Bearer ... resource_metadata=".../.well-known/oauth-protected-resource/_reflex/mcp"`, which points at that missing document. The working credential path is `POST /_reflex/auth/token`.
  - Same on 0.10.1 + 0.9.11, so pre-existing.
  - Evidence: `out/f008_prod_and_prm.txt`, `out/f002_variants.txt`.
- **Known ENT-26 (rxe#254) unchanged.** Prod `POST /_reflex/mcp` (no trailing slash) → 405. That is the `resource` URL the
  PRM advertises, so an MCP client given it fails in single-port prod, while dev answers 307 to `/_reflex/mcp/`.
  0.10.1 behaves the same. The prod OAuth flow passes with `/_reflex/mcp/`.

## NEW-ISSUE sections

### NEW-ISSUE 1 (environment, not product): the shared uv cache holds a patched reflex-base 0.11.0a1
- `/root/.cache/uv/archive-v0/Q-gRUxuTKMN1xaM5/reflex_base/components/component.py` (inode 614510, 57 hardlinks) contains
  a local patch (an implicit `ImportVar(tag="refs")` at line 1840), and `reflex/istate/manager/redis.py` is modified too.
  Any venv that uv builds for `reflex-base==0.11.0a1` from the default cache inherits it, so 0.11.0a1 "controls" silently
  stop reproducing FINDING-003.
- Repro: `python3 -I phase7/enterprise/scripts/verify_record.py $OLDSB/envs/vent-new/lib/python3.12/site-packages` →
  `MODIFIED reflex_base-0.11.0a1.dist-info reflex_base/components/component.py`. Compare `stat -c '%i %h'` of that file
  with the cache path.
- Remedy for anyone building a1 venvs: use a private `UV_CACHE_DIR` and `--link-mode=copy`, or purge that cache entry.
  Do not patch files inside venvs, because uv hardlinks them into the cache.

### NEW-ISSUE 2 (rxe, pre-existing, LOW): the AG Grid model wrapper's add dialog uses id-only checkboxes and table rows without a body
- `reflex_enterprise/components/ag_grid/wrapper.py` `_add_dialog_field` renders bool columns as `rx.checkbox(id=field)`
  (with no `name`) and returns `rx.table.row(...)` directly under `rx.table.root(...)`, with no `rx.table.body`.
- Effect 1: reflex 0.10.1+ prints `Submitting the form control with id '<field>' by its id has been deprecated ... removed
  in 0.12.0` for every bool field, on every compile. The user cannot fix it. Once 0.12.0 removes id-based submission,
  bool fields are silently dropped from the add form.
- Effect 2: in dev, React logs `In HTML, <tr> cannot be a child of <table>. This will cause a hydration error` and
  `<table> cannot contain a nested <tr>` when the dialog renders.
- Repro: the upstream `demos/ag_grid` app (model pages, e.g. the fixture's `/qa-model-workaround`), `reflex run` in dev,
  open the page and read the console. The fixture driver reports it in `out/smoke/` → `ag_dev_*` (`ag_model-ent-0912.json`
  console_errors). The deprecation lines are in any compile log of that demo. The same code is in 0.9.11, so this is not
  a regression.

### NEW-ISSUE 3 (rxe, pre-existing, LOW): the MCP page list names the root page `/index`
- With `deploy_url` set, the MCP `initialize` instructions list `https://myapp.example.com/index` for the `/` route. The
  same happens on 0.10.1 + rxe 0.9.11.
- Repro: `src/mcpmin`. Run `scripts/srv.sh start ent-0912 prod src/mcpmin x REFLEX_DEPLOY_URL=https://myapp.example.com`,
  then `$P7/driver/bin/python -I scripts/mcp_probe.py http://localhost:8380`, then look at the `instructions` line.

## How to rerun

```
OLDSB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; W=$OLDSB/p7/work/ent; S=<this dir>/enterprise/scripts
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1   # client side only; srv.sh does not pass these to the server
# F-002
$S/srv.sh start ent-0912 prod <src>/mcpmin f002 && $OLDSB/p7/envs/driver/bin/python -I $S/mcp_probe.py http://localhost:8380; $S/srv.sh stop
$S/srv.sh start ent-0911 prod <src>/mcpmin f002c; $S/srv.sh stop          # -> server exited, ConfigError
# F-003 (DELETE_GLOBAL=1 removes globalThis.refs before each click)
$S/srv.sh start <ent-0912|ent-0911|a1ent-clean> <dev|prod> <src>/agapi l && $OLDSB/p7/envs/driver/bin/python -I $S/agapi_drv.py http://localhost:<3380|8380> l $W/shots; $S/srv.sh stop
#   also agaligned + agaligned_drv.py, agapi_memo3 + agapi_memo_noid_drv.py
# F-008 (mock IdP on 8398)
cd $W/run && IDP_VENV=vent-idp MOCK_OIDC_PORT=8398 setsid $OLDSB/envs/vent-idp/bin/python -I $S/mock_oidc.py &
OIDC="OIDC_ISSUER_URI=http://localhost:8398 OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1"
$S/srv.sh start ent-0912 dev <src>/auth_min f008 $OIDC && $OLDSB/p7/envs/driver/bin/python -I $S/mcp_consent_probe.py http://localhost:8380
(cd $S/oauthflow && FLOW_OUT=<dir with logs/ screenshots/> [FLOW_MCP_URL=http://localhost:8380/_reflex/mcp/] $OLDSB/envs/enterprise-entdrv/bin/python -s -E check_mcp_oauth.py); $S/srv.sh stop
# F-009 (ag_grid demo from `git -C /home/user/reflex-enterprise archive v0.9.12 demos`)
OVERLAY=$W/overlay $S/dbcmd_matrix.sh $W/demos/ag_grid agdemo a1ent-clean ent-0911 ent-0912 vent-prev
# F-021
$S/srv.sh start ent-0912 dev <src>/single f021 && curl --noproxy '*' -s -o /dev/null -w '%{http_code}\n' localhost:8380/; $S/srv.sh stop
# smoke
$S/smoke_seq.sh ag:ent-0912:prod ag:ent-0912:dev ag:ent-0911:prod d:ent-0912:prod:dnd d:ent-0912:dev:dnd ... ; python3 -I $S/channels.py $W/fxwork/grid/out/*_p7_*
```

`srv.sh` looks a venv up first in `$P7`, then in `$W/envs`, then in `$OLDSB/envs`. Prod reads the access token from
`$OLDSB/secrets` into the server environment only. Every app's rxconfig asserts `VE_VENV` against `reflex.__file__`.
