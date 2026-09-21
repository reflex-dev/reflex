# rv_enterprise — Phase 7 re-verification: reflex-enterprise 0.9.6a1 on reflex 0.9.12a2

Date: 2026-09-21. Agent: `rv_enterprise`. Ports used: frontend 3140–3147, backend 8140–8151, fake IdP 8158.
All processes killed at the end (`ports.py` reports nothing in 3140–3159 / 8140–8159).

**Headline: every check in the brief passes. reflex-enterprise 0.9.6a1 on reflex 0.9.12a2 runs the whole
MCP / OIDC / REST / demo surface with NO shim.** FINDING-001, FINDING-003 (enterprise manifestation) and
FINDING-011 (redaction, in-process AND over HTTP AND over MCP) are fixed. One previously-unrecorded
pre-existing defect found (rxe's OpenAPI endpoint needs an undeclared `pyyaml`); no new regression.

## Environments

| venv | contents | role |
|---|---|---|
| `$SB/envs/enta2` | reflex 0.9.12a2 + component alphas + reflex-enterprise[mcp] 0.9.6a1 | tree under test (import/probe checks) |
| `$SB/reverify/rv_enterprise/venv_a2tk` | same set, built by me, **plus** `aiosqlite greenlet faker==36.2.2 pandas==2.2.3 alembic aiohttp pyyaml` | every demo/app run (demos need a DB driver) |
| `$SB/envs/ent` | 0.9.12a1 + rxe 0.9.5 | the broken pair (LEAK control) |
| `$SB/envs/entprev` | 0.9.11.post1 + rxe 0.9.5 | previous-stable baseline |
| `$SB/reverify/rv_enterprise/venv_dual` | reflex 0.9.11.post1 + stable components + **rxe 0.9.6a1** | dual-compat proof |
| `$SB/envs/driver` | playwright 1.63, chromium `/opt/pw-browsers/chromium` | all browser drivers |

`venv_a2tk` freeze (reflex packages):
```
reflex 0.9.12a2, reflex-base 0.9.12a2, reflex-components-code 0.9.6a1, -core 0.9.10a1,
-dataeditor 0.9.3a1, -gridjs 0.9.2a1, -lucide 1.0.4, -markdown 0.9.4a1, -moment 0.9.4,
-plotly 0.9.7a1, -radix 0.9.10a1, -react-player 0.9.2, -recharts 0.9.4a1, -sonner 0.9.4a1,
reflex-enterprise 0.9.6a1 (from $SB/wheels/reflex_enterprise-0.9.6a1-py3-none-any.whl),
reflex-hosting-cli 0.1.72, mcp 1.30.0, sqlmodel 0.0.44, alembic 1.20.0
```
Created from a neutral cwd (`cd $SB`), `--prerelease=allow`, every component alpha named explicitly.
App sources copied out of the read-only clones (`/home/user/wt/rxe/demos/`, the campaign directories);
nothing installed from any checkout.

## Result table

| # | Check | a2 + rxe 0.9.6a1 | a1 + rxe 0.9.5 | 0.9.11.post1 + rxe 0.9.5 | Evidence |
|---|---|---|---|---|---|
| 1 | Wheel inspection (`OIDCCookieMeta` base, `redact_router_session`, `Requires-Dist`) | **PASS** | n/a | n/a | `out/diff_oidc_state.txt`, `out/diff_event_handler_api.txt` |
| 2a | `import reflex_enterprise.auth.oidc.state`, 23-module sweep, no shim | **PASS** 23/23, BAD=0 | FAIL (metaclass conflict) | 23/23 | `out/import_probe_enta2.txt` |
| 2b | `MCPPlugin`-only app `/ping` | **200** | 000 (worker dies) | 200 | `logs/mcpapp_a2.tail.log` |
| 2c | `AuthPlugin`-only app `/ping` (no shim) | **200**, 0 tracebacks | dies at import | 200 | `logs/authonly_a2.tail.log` |
| 2d | shipped `demos/oidc` imports + builds its `App` | **PASS** | FAIL | PASS | `out/demo_import_a2.txt` |
| 3a | `probe_router_redact.py` | **VERDICT OK** | **VERDICT LEAK** | VERDICT OK | `out/redact_probe_{enta2,ent,entprev}.txt` |
| 3b | HTTP proof: unmodified `demos/tickets`, `retrieve_state` + ndjson event delta | **PASS** (blanked) | (app cannot start) | n/a | `out/leak_http_a2.txt`, `out/leak_retrieve_state_a2.json`, `out/leak_event_delta_a2.ndjson` |
| 3c | Dual-compat: rxe 0.9.6a1 on reflex 0.9.11.post1 (legacy `router` var) | **VERDICT OK** | n/a | n/a | `out/redact_probe_dual_0911_rxe096a1.txt`, `out/import_probe_dual.txt` |
| 3d | MCP surface redaction (delta + `reflex://state/vars/...`) | **PASS** (blanked) | leaked a real UUID | `""` | `out/mcp_router_read_a2.txt`, `out/mcp_drive_a2.txt` |
| 4 | FINDING-003: `@rxe.var(auth=True, cache=False)` right after login | **PASS** (`SERVER-ONLY-SECRET`) | FAIL (stale) | PASS | `logs/uncached_a2.json` |
| 5a | Full OIDC browser flow (login / protected events / bg event / secret page / reload / 2nd tab / logout), no shim | **PASS** | passed only behind shim | PASS | `out/auth_a2new.json` |
| 5b | MCP resources/tools listing + `queue_event` + error handling | **PASS** | PASS (shim) | PASS | `out/mcp_drive_a2.txt`, `out/mcp_probe2_a2.txt` |
| 5c | MCP protected-handler enforcement (anon session) | **PASS**, byte-identical to campaign | PASS (shim) | PASS | `out/mcp_auth_probe_a2.txt` |
| 5d | MCP extra probes (rate limit, garbage bearer, SSE, streamable) | **PASS** | PASS | PASS | `out/mcp_extra_a2.txt` |
| 6a | `demos/map` driver | **13/13** | 13/13 | — | shots `map_a2/`, console: only the environmental OSM tile failures |
| 6b | `demos/dnd` driver | **18/18**, 0 console/net/page errors | 18/18 | — | `shots/dnd_a2/` |
| 6c | `demos/flow` driver | **11/11**, clean | 11/11 | — | `shots/flow_a2/` |
| 6d | `demos/mantine` `mantine_dates` (52 steps) + `tabs` + `discover` | **PASS**, clean | 52/52 | — | `out/mantine_*_a2.json` |
| 6e | `demos/ag_grid` (dev, patched demo) 13 routes | **all ok, 0 errors, 0 failed** — identical to campaign | same | — | `out/aggrid_a2_report.json` |
| 6f | tickets REST: auth required / ndjson stream / api-catalog | **PASS** (401/401/401, 200 catalog, ndjson delta) | (could not start) | — | `out/tickets_rest_a2.txt` |
| 6g | **NEW:** tickets `/` UI is alive (hydrate + events) | **PASS** | inert (2026-09-10 campaign) | inert | `out/tickets_hydrate_a2.json`, `out/tickets_crud1_a2.json` |
| 7 | Pin sanity | **noted** — `reflex[db]>=0.9.6`, still no upper bound | same | same | below |

## Check 1 — wheel inspection (all three claims hold)

`reflex_enterprise/auth/oidc/state.py`
* `class OIDCCookieMeta(_StateMetaclass)`, with `_StateMetaclass = type(rx.State)` at runtime and
  `reflex.istate.validation._StateMeta` under `TYPE_CHECKING`. `from reflex.vars import BaseStateMeta`
  is gone. This is exactly the fix shape FINDING-001 suggested.
* Other changes in that module (not required by the brief, recorded per instruction): `post_auth_message`
  gains a `fallback_url` arg; `auth_callback` branches on `from_popup` and hands the tokens to the opener
  (or closes without announcing them when the exchange rejected them) instead of following
  `redirect_to_url`; `_cookie_sync_token_update`'s `callback` type narrowed from `EventType[Any]`.
  This is the rxe #223 popup fix, announced in the wheel's CHANGELOG.

`reflex_enterprise/plugins/event_handler_api.py`
* `_ROUTER_SESSION_VAR = getattr(_route_constants, "ROUTER_SESSION", "rx_router_session")`;
  `redact_router_session` now redacts on **either** the marked `router` key or the marked
  `rx_router_session` key, **and** on `isinstance(value, RouterData)` / `isinstance(value, SessionData)`
  — so a further framework rename cannot silently re-open the hole. New `_redact_session_value`
  handles dict / dataclass / proxied-dataclass shapes.
* `collect_delta_for_agent` now redacts **before** the `json_dumps` round-trip (the type-based match
  needs the dataclasses intact) — a real ordering bug fixed, not cosmetic.

`METADATA`: `Requires-Dist: reflex[db]>=0.9.6` — byte-identical to 0.9.5, **still no upper bound**.

Also changed vs 0.9.5 (worth the maintainers' attention, all in the wheel CHANGELOG):
* `auth/enforcement.py::is_exempt` looks the provider module up in `sys.modules` instead of importing it
  (rxe #231). This is why an `MCPPlugin`-only app no longer grows `IsIframedState` /
  `GenericOIDCAuthState` after `App._compile()` — i.e. this is the enterprise-side cure for the
  hydrate-time `backend_state_mismatch` latch that FINDING-023 describes framework-side.
* `plugins/mcp_auth/tools.py` passes `enforce_auth=access.enforce_auth` to `register_reflex_resources`.
* `plugins/mcp_builtin_resources.py` no longer hard-codes `var_name == "router"` before redacting.
* `components/message_listener/funcs.py`: `CLOSE_POPUP` / `POST_MESSAGE_AND_CLOSE_POPUP` take
  `fallback_url` and catch the cross-origin `opener.origin` throw.

## Check 3 — FINDING-011, the evidence

In-process (`scripts/probe_router_redact.py <venv-marker>`, run from `$SB/reverify/rv_enterprise/work`):

```
enta2   : rx_router_session_rx_state_ = SessionData(client_token='SECRET-CLIENT-TOKEN', ...) -> VERDICT OK
ent     : same input                                                                        -> VERDICT LEAK
          ['.reflex___state____state.rx_router_session_rx_state_.client_token']
entprev : router_rx_state_ = RouterData(session=SessionData(...))                           -> VERDICT OK
dual    : reflex 0.9.11.post1 + rxe 0.9.6a1, legacy router var                              -> VERDICT OK
```

Over HTTP, the **unmodified** `demos/tickets` on a2 (dev, CI=true, ports 3140/8140), anonymous app bearer:

```
POST /_reflex/retrieve_state          -> 200, root keys: is_hydrated + the five rx_router_*
   rx_router_session = {"client_token": "", "client_ip": "0.0.0.0", "session_id": ""}
POST /_reflex/event/<state>/seed      -> 200, ndjson
   rx_router_session = {"client_token": "", "client_ip": "127.0.0.1", "session_id": ""}
```
`client_ip` preserved, as intended. A regex sweep for UUIDs over both bodies finds only the demo's own
four `ticket_id`s — no server-side token under any other name.

Over MCP (`scripts/mcp_router_read.py`): `reflex://state/vars/<root>/rx_router_session` and the whole
`reflex://state/vars/<root>` read both return `client_token: ""`, and the session bearer does not appear
anywhere in the payload. On 0.9.12a1 the campaign recorded a real UUID here.

## Check 5 — the auth driver, diffed step by step

`scripts2/drive_auth.py 3141 a2new 8158` against the **unshimmed** `apps/authapp`. Compared field by
field against the campaign's `auth_a2prev.json` (0.9.11.post1) and `auth_a2new.json` (0.9.12a1 + shim):

* vs **0.9.11.post1**: the only differences are the port numbers inside the recorded URLs and
  `anon_raw_html.length` 3587 → 3661 (the expected compiler-output change of this train). Every
  functional field is identical.
* vs **0.9.12a1 + shim**: one substantive difference, `after_login_click` —
  `shared=default-shared` (a1, FINDING-003) → `shared=SERVER-ONLY-SECRET` (a2). That is the fix.

`CONSOLE ERRORS: [] / PAGE ERRORS: [] / HTTP >=400: []`. The two `net::ERR_ABORTED` on
`/_reflex/cookies/sync` are the pre-existing quirk the campaign already documented on both versions.

## Check 6g — the tickets UI came back to life

The 2026-09-10 campaign recorded the tickets demo's `/` page as inert on 0.9.10.post2 and 0.9.11a1
("the OIDC substates join the state tree without a frontend dispatcher"), and 0.9.12a1 could not start
it at all. On a2 + 0.9.6a1 `scripts/probe_tickets_hydrate.py` shows a full, healthy handshake:
hydrate → deltas → `is_hydrated: true`, the Seed click sends an event frame, 4 rows render, console
carries only the four benign dev-server lines. `actions/tickets_crud1.json` runs 38/38 steps with
`FAILED STEPS: [] / CONSOLE ERRORS: [] / PAGE ERRORS: [] / HTTP>=400: []`; search, URL-persisted
filters, reload, reset and both sort directions all round-trip.

**Driver artifact, not a defect:** in that scripted run the `New Ticket` → `Create` sequence left the
row count at 4. A focused probe (`scripts/probe_create.py <base> fill <shot>`) shows the flow is fine —
`set_draft_title` fires with the typed value, `submit_draft` fires, rows 4 → 5, the form closes, no
console or page errors. The scripted run's `click_text: "Create"` matches the wrong element. Recorded
so nobody re-files it.

## Check 7 — pin sanity

```
$ uv pip list --python $SB/envs/enta2/bin/python | grep -i reflex
reflex 0.9.12a2 / reflex-base 0.9.12a2 / components: code 0.9.6a1, core 0.9.10a1,
dataeditor 0.9.3a1, gridjs 0.9.2a1, lucide 1.0.4, markdown 0.9.4a1, moment 0.9.4,
plotly 0.9.7a1, radix 0.9.10a1, react-player 0.9.2, recharts 0.9.4a1, sonner 0.9.4a1,
reflex-enterprise 0.9.6a1, reflex-hosting-cli 0.1.72
```

`reflex_enterprise-0.9.6a1` declares `reflex[db]>=0.9.6`, unchanged, **no upper bound**.

Does it still matter now that both halves are fixed? The acute danger is gone — the two things that made
the missing ceiling fatal for 0.9.12 (the metaclass conflict and the silent redaction no-op) are fixed on
the enterprise side, so an existing rxe app that runs `pip install -U reflex` now lands on a working pair.
Two caveats remain, and they are worth one line in the release notes rather than a blocker:

1. **The fix only protects users who also upgrade reflex-enterprise.** With no upper bound, a user who
   upgrades reflex to 0.9.12 and leaves rxe at 0.9.5 gets the broken pair, and the resolver says nothing.
   Only a ceiling on the *old* wheel could have prevented that, and that ship has sailed; the release
   notes should say "reflex 0.9.12 requires reflex-enterprise >= 0.9.6".
2. The unbounded floor keeps the same exposure open for 0.9.13+: rxe reaches into framework internals
   (`reflex.istate.validation`, `reflex.istate.data.RouterData/SessionData`, `reflex_base.constants.route`)
   and nothing in the metadata will stop the next such change from repeating this. 0.9.6a1 at least fails
   *safe* on the redaction path now (type-based matching), which is the important half.

## Known-pre-existing things seen again (confirmed unchanged, not re-filed)

* `reflex://state/vars/<short state name>` needs the fully-qualified name (previous campaigns' MCP
  resource-naming finding) — identical messages on a2.
* ag_grid: shipped `demos/ag_grid` still cannot start unpatched
  (`ValueError: Library $/app_components/ag_grid/formatters is not bundled`, from the demo's stale
  `$/utils/components` bundle call). I reproduced it on a2 and then used the campaign's patched
  `ent_aggrid/demo_new` copy, exactly as the campaign did. `/integrated-charts`, `/model`, `/model-auth`,
  `/model-ssrm` (campaign Issues C and D) were not re-run — known rxe-side, unrelated to this train.
* ag_grid `use_single_port=True` logs `Unable to find the base Starlette app. Proxying will not be
  enabled.` — same line in the campaign's `run_new_dev.log`.
* map demo: 77 `net::ERR_TUNNEL_CONNECTION_FAILED` against `*.tile.openstreetmap.org` (sandbox egress).
* `/_reflex/cookies/sync` → two `net::ERR_ABORTED` per auth run.
* Demo-source deprecation warnings (`ArrayVar.foreach`, `console.debug/error`, `reflex.Model`,
  `register_auth_endpoints`, string `disable_plugins`) on both versions.
* Enterprise prod mode remains unavailable to unlicensed QA (`check_paid_tier_for_command`); not forced.

## New issue (not in FINDINGS.md) — pre-existing, enterprise-side, not a release blocker

**`GET /_reflex/events/openapi.yaml` returns 500 unless `pyyaml` happens to be installed.**
The `EventHandlerAPIPlugin`'s own documented OpenAPI endpoint — the one the RFC 9727 catalog at
`/.well-known/api-catalog` advertises — 500s with
`AssertionError: 'pyyaml' must be installed to use parse_docstring.` raised from
`starlette/schemas.py:106`, reached from `reflex_enterprise/plugins/event_handler_api.py:1731`
(`schemas.get_schema`). `reflex-enterprise` does not declare `pyyaml`, and neither reflex nor starlette
pulls it in: it is absent from `envs/enta2`, `envs/ent` and `envs/entprev` alike.

* Repro: `demos/tickets` on any of those venvs, `reflex run --backend-only --backend-port <p>`, then
  `curl --noproxy '*' http://localhost:<p>/_reflex/events/openapi.yaml` → 500.
  `uv pip install pyyaml` into the venv and restart → 200 with a valid OpenAPI document (verified;
  `logs/tickets_openapi.tail.log` is the 500, `logs/tickets_openapi2.tail.log` the 200 run).
* Classification: **pre-existing, not a regression of this train.** `openapi_response` is byte-identical
  between the 0.9.5 and 0.9.6a1 wheels (`out/diff_event_handler_api.txt` shows no change in that region),
  the starlette version is the same, and `pyyaml` is missing from the 0.9.11.post1 venv too, so the same
  500 is what a 0.9.11.post1 + rxe 0.9.5 install returns. It is invisible to anyone whose environment
  happens to carry `pyyaml` transitively, which is presumably why it was never noticed.
* Severity: LOW-MEDIUM, reflex-enterprise-side. Fix is one line of metadata
  (`pyyaml` in the plugin's dependencies) or a graceful 501 with the same message.

## Rerun commands

```
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
D=$SB/reverify/rv_enterprise

# venv (from a NEUTRAL cwd)
cd $SB && uv venv $D/venv_a2tk --python 3.11
uv pip install --python $D/venv_a2tk/bin/python --prerelease=allow \
  'reflex==0.9.12a2' 'reflex-base==0.9.12a2' 'reflex-components-core==0.9.10a1' \
  'reflex-components-radix==0.9.10a1' 'reflex-components-code==0.9.6a1' \
  'reflex-components-dataeditor==0.9.3a1' 'reflex-components-gridjs==0.9.2a1' \
  'reflex-components-markdown==0.9.4a1' 'reflex-components-plotly==0.9.7a1' \
  'reflex-components-recharts==0.9.4a1' 'reflex-components-sonner==0.9.4a1' \
  aiosqlite greenlet 'faker==36.2.2' 'pandas==2.2.3' alembic aiohttp pyyaml \
  "reflex-enterprise[mcp] @ file://$SB/wheels/reflex_enterprise-0.9.6a1-py3-none-any.whl"

# checks 1-3a (no server)
cd $D/work && $SB/envs/enta2/bin/python ent_import_probe.py
cd $D/work && for e in enta2 ent entprev; do $SB/envs/$e/bin/python probe_router_redact.py "/envs/$e/"; done

# check 3b (HTTP leak proof)
cd $D/apps/tickets && REFLEX_TELEMETRY_ENABLED=false CI=true \
  $D/venv_a2tk/bin/reflex run --frontend-port 3140 --backend-port 8140 &
cd $D/work && NO_PROXY=localhost,127.0.0.1 $D/venv_a2tk/bin/python v_leak_http.py rs.json ev.ndjson
cd $D/work && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python probe_tickets_hydrate.py http://localhost:3140/ th.json
cd $D/work && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_mht.py \
  http://localhost:3140 actions/tickets_crud1.json crud.json $D/shots/tickets_a2

# checks 2b-2c, 4, 5 (fake IdP on 8158)
cd $D/mcpoidc_idp  && NO_PROXY=localhost,127.0.0.1 $D/venv_a2tk/bin/python fake_idp.py 8158 &
cd $D/mcpoidc_apps/mcpapp   && CI=true REFLEX_TELEMETRY_ENABLED=false $D/venv_a2tk/bin/reflex run --backend-only --backend-port 8141 &
cd $D/mcpoidc_scripts && NO_PROXY=localhost,127.0.0.1 $D/venv_a2tk/bin/python mcp_drive.py 8141
cd $D/mcpoidc_scripts && NO_PROXY=localhost,127.0.0.1 $D/venv_a2tk/bin/python mcp_probe2.py 8141
cd $D/mcpoidc_scripts && NO_PROXY=localhost,127.0.0.1 $D/venv_a2tk/bin/python mcp_extra_probe.py 8141 a2 extra.json
cd $D/work            && NO_PROXY=localhost,127.0.0.1 $D/venv_a2tk/bin/python mcp_router_read.py 8141
cd $D/mcpoidc_apps/authonly && CI=true REFLEX_TELEMETRY_ENABLED=false OIDC_ISSUER_URI=http://localhost:8158 \
  OIDC_CLIENT_ID=test-client OIDC_CLIENT_SECRET=test-secret $D/venv_a2tk/bin/reflex run --backend-only --backend-port 8142 &
cd $D/mcpoidc_apps/authapp  && CI=true REFLEX_TELEMETRY_ENABLED=false OIDC_ISSUER_URI=http://localhost:8158 \
  OIDC_CLIENT_ID=test-client OIDC_CLIENT_SECRET=test-secret $D/venv_a2tk/bin/reflex run --frontend-port 3141 --backend-port 8143 &
cd $D/mcpoidc_scripts2 && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python uncached_after_login.py 3141 a2 8158
cd $D/mcpoidc_scripts2 && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_auth.py 3141 a2new 8158
cd $D/mcpoidc_scripts  && NO_PROXY=localhost,127.0.0.1 $D/venv_a2tk/bin/python mcp_auth_probe.py 8143

# check 6 (one demo at a time)
cd $D/apps/<map|dnd|flow|mantine> && CI=true REFLEX_TELEMETRY_ENABLED=false \
  $D/venv_a2tk/bin/reflex run --frontend-port 314X --backend-port 814X &
cd $D/work/drivers && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_map.py  http://localhost:3142 $D/shots/map_a2 a2
cd $D/work/drivers && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_dnd.py  http://localhost:3143 $D/shots/dnd_a2 a2
cd $D/work/drivers && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_flow.py http://localhost:3144 $D/shots/flow_a2
cd $D/work && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_mht.py http://localhost:3145 actions/mantine_dates.json m.json $D/shots/mantine_a2
# ag_grid needs the campaign's patched demo + a seeded DB
cp -r prerelease-testing/2026-09-18-v0.9.12a1/ent_aggrid/demo_new $D/apps/aggrid_patched
cd $D/apps/aggrid_patched && sed -i 's|^sqlalchemy.url = .*|sqlalchemy.url = sqlite:///reflex.db|' alembic.ini \
  && CI=1 $D/venv_a2tk/bin/alembic upgrade head && CI=1 $D/venv_a2tk/bin/python $D/work/seed_db.py 200
cd $D/apps/aggrid_patched && CI=true REFLEX_TELEMETRY_ENABLED=false $D/venv_a2tk/bin/reflex run --frontend-port 3147 --backend-port 8149 &
cd $D/work && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_aggrid.py http://localhost:3147 $D/shots/aggrid_a2 / /editable /formatters /simple-serialization /advanced-serialization /master-detail /pivot /selected-items /state-grid /tree /cell-selection /fill-handle /aligned-grids
```

## Verdict for the release decision

From this cluster's surface: **release-ready.** The two release blockers that touched reflex-enterprise
(FINDING-001 and FINDING-011) and FINDING-003's enterprise manifestation are fixed, verified without any
shim, over four channels, with the previous stable as the reference. Nothing in 0.9.6a1's other changes
regressed the demos. The only items left are one pre-existing enterprise packaging gap (`pyyaml`) and the
release-note line telling users that reflex 0.9.12 needs reflex-enterprise >= 0.9.6.

## VERIFICATION

Independent adversarial verifier, 2026-09-21. Ports 3640–3643 / 8640–8643 (all released; `ports.py` clear).
Nothing installed into `envs/*`. Own venvs under
`$SB/reverify/rv_enterprise-verify/` (`venv_a2` = reflex 0.9.12a2 + the component alphas + rxe 0.9.6a1[mcp]
from the offline wheel + `aiosqlite greenlet`, **deliberately without pyyaml**; `venv_entprev` = reflex
0.9.11.post1 + stable components + rxe 0.9.5 + `aiosqlite greenlet`, also without pyyaml). Demo copied fresh
from the read-only `/home/user/wt/rxe/demos/tickets`, unmodified. Evidence under `verify/`.

### Claim — `GET /_reflex/events/openapi.yaml` 500s without pyyaml: **CONFIRMED, pre-existing, not a blocker**

Reproduced from the written repro alone, in a venv I built myself, and refuted every alternative explanation
I could construct. Verdict matches the cluster's, including the classification and the severity.

| run | tree | pyyaml | `GET /_reflex/events/openapi.yaml` | `/.well-known/api-catalog` |
|---|---|---|---|---|
| a2 | reflex 0.9.12a2 + rxe 0.9.6a1 | absent | **500** `Internal Server Error` (`text/plain`) | **200**, points at that exact URL |
| a2 + fix | same venv, `uv pip install pyyaml` (6.0.3) | present | **200**, 27 210 B, `application/vnd.oai.openapi`, 34 paths, `Link: </.well-known/api-catalog>; rel="api-catalog"` | 200 |
| baseline | reflex **0.9.11.post1 + rxe 0.9.5** | absent | **500**, same assertion, same code path (0.9.5's `event_handler_api.py:1686`) | **200** |
| a1 | reflex 0.9.12a1 + rxe 0.9.5 | absent | **not reachable** — worker dies before serving | n/a |

Four channels on the a2 no-pyyaml run: server log = the traceback below; network = 500 on the openapi URL
with a 200 api-catalog advertising it; rendered body = the literal string `Internal Server Error`;
browser console = n/a (curl surface).

```
reflex_enterprise/plugins/event_handler_api.py, line 1731, in openapi_response
    schema = schemas.get_schema(routes=routes)
starlette/schemas.py, line 138, in get_schema
    parsed = self.parse_docstring(endpoint.func)
starlette/schemas.py, line 106, in parse_docstring
    assert yaml is not None, "`pyyaml` must be installed to use parse_docstring."
AssertionError: `pyyaml` must be installed to use parse_docstring.
```
(`verify/openapi_a2_noyaml_traceback.txt`; the byte-for-byte same assertion on the 0.9.11.post1 pair in
`verify/openapi_entprev_noyaml.txt`.)

### Root cause, read out of the installed wheel

`starlette/schemas.py` treats pyyaml as optional — `try: import yaml / except ModuleNotFoundError: yaml = None` —
and then asserts on it in **two** places: `SchemaGenerator.parse_docstring` (line 106, the one that fires) and
`OpenAPIResponse.render` (line 23, which would fire next even if no route had a docstring). Starlette declares
pyyaml only under its `full` extra and documents it as "Required for `SchemaGenerator` support".
`reflex_enterprise/plugins/event_handler_api.py:1518` imports both symbols unconditionally and calls them from
the route handler at :1731–1732, while the wheel's `Requires-Dist` is `asgiproxy>=0.2.0, httpx, joserfc, psutil,
reflex[db]>=0.9.6` (+ `mcp` / `testing` extras) — no pyyaml, no `starlette[full]`. Nothing in reflex,
reflex-base or reflex-hosting-cli pulls yaml in (absent from all seven campaign venvs and from both of mine),
so a clean `pip install reflex-enterprise` always lands in the failing state. The blast radius is exactly this
one endpoint: yaml is used nowhere else in reflex_enterprise (grep over the installed package: the only hits are
the two starlette symbols and the URL string), and `/ping`, the 401 auth checks, the event endpoints, the
ndjson delta stream and the api-catalog are all unaffected.

**Why nobody noticed** (new detail, corroborates the "pre-existing and invisible" story): rxe *does* test this
endpoint — `tests/units/plugins/test_api_security.py:214 test_openapi_documents_the_token_endpoint` asserts
`spec.status_code == 200`. It passes because the rxe development venv carries pyyaml transitively:
`/home/user/wt/rxe/.venv/.../site-packages/yaml/` exists, pulled in by the `[dependency-groups] dev` entries
`pre-commit` and `oidc-provider-mock` and by `uvicorn` / `pydantic-settings` / `markdown-it-py`. None of those
are runtime dependencies of the published wheel, so the green test is testing an environment users never get.

### Refutation attempts, all failed

* **Environment quirk / dirty venv** — no. Built two clean venvs from PyPI + the offline wheel from a neutral
  cwd; the 500 appears in both, on two different reflex versions, and disappears the moment pyyaml is added
  to the very same venv.
* **Misuse** — no. A plain unauthenticated `GET` on the URL the demo's own `rxconfig.py` docstring advertises
  and the RFC 9727 catalog returns with a 200.
* **Introduced by this train** — no, and the cluster's code argument holds up: `diff` of
  `event_handler_api.py` between the 0.9.5 and 0.9.6a1 wheels is 139 changed lines, **zero** of them matching
  `yaml|SchemaGenerator|OpenAPIResponse|get_schema|openapi`; the `openapi_response` region is byte-identical
  (0.9.5 L1680–1705 == 0.9.6a1 L1725–1750); the two wheels' `Requires-Dist` blocks are identical; starlette is
  1.6.0 in both venvs. And I did not rest on the diff — I **ran** the 0.9.11.post1 + rxe 0.9.5 pair and got the
  same 500.
* **"Not runnable on a1" unverified** — verified independently, not just inherited from FINDING-001. A
  12-line `EventHandlerAPIPlugin`-only app of my own on `envs/ent` (0.9.12a1 + rxe 0.9.5) never binds its port:
  the granian worker dies in `App.__call__ -> plugin.post_compile -> iter_public_event_handlers ->
  is_exempt -> auth/oidc/state.py:381` with `TypeError: metaclass conflict`
  (`verify/mini_a1_rxe095_post_compile.tail.log`). So the a1 row is genuinely "cannot start", and the same
  minimal app is also a fresh, non-demo reproduction of FINDING-001.
* **Already recorded** — no. `FINDINGS.md` mentions openapi exactly once, at line 705, in the
  `ent_map_dnd_flow_mantine` summary listing "tickets REST/OpenAPI (blocked)" among the *skipped* checks. No
  FINDING covers it; the word pyyaml appears nowhere in `FINDINGS.md` or `RELEASE_PLAN.md`.
* **Known-benign noise** — no. A 500 on a documented endpoint is not on the agent brief's benign list.

### Severity and release impact — agree with the cluster

LOW-MEDIUM, reflex-enterprise-side, **not a reflex 0.9.12 release blocker**: pre-existing on the previous
stable pair, confined to one discovery endpoint, no security or data impact, and worked around by installing
pyyaml. It does deserve a reflex-enterprise ticket, because the failure is a bare 500 whose cause is visible
only in the server log while the catalog next to it returns 200 and points straight at it. Two candidate
fixes, either one line: declare `pyyaml` (or `starlette[full]`) in the wheel's dependencies, or catch the
missing module at route-registration time and serve a 501 carrying starlette's own explanation. The latter
also wants the unit test to run without pyyaml so the gap cannot reopen.

Evidence: `verify/openapi_a2_noyaml.txt`, `verify/openapi_a2_noyaml_traceback.txt`,
`verify/openapi_entprev_noyaml.txt`, `verify/openapi_a2_withyaml.txt`,
`verify/openapi_a2_withyaml.head.yaml`, `verify/mini_a1_rxe095_post_compile.tail.log`.
