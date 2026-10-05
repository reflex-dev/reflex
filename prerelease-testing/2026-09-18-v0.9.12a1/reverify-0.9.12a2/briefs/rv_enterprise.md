# rv_enterprise — reflex-enterprise 0.9.6a1 on reflex 0.9.12a2: FINDING-011 (redaction), FINDING-001 downstream, MCP/OIDC, demos
Ports: frontend 3140-3159 / backend 8140-8159 (redis: 8159). Scratch: $SB/reverify/rv_enterprise/. Notes dir: reverify-0.9.12a2/rv_enterprise/.
Venv under test: `$SB/envs/enta2` (a2 + reflex-enterprise 0.9.6a1[mcp]). Contrast venvs: `envs/ent` (a1 + rxe 0.9.5,
the broken pair), `envs/entprev` (0.9.11.post1 + rxe 0.9.5). Demo sources: `/home/user/wt/rxe/demos/` (copy to scratch;
they are app sources, the PACKAGE always comes from the wheel in the venv). Campaign material: `ent_mcp_oidc/`,
`ent_map_dnd_flow_mantine/`, `ent_aggrid/` (NOTES.md + `## VERIFICATION`, scripts, verification/).

Checks:
1. Wheel inspection (seconds): in the 0.9.6a1 wheel, `reflex_enterprise/auth/oidc/state.py` `OIDCCookieMeta` derives
   from `type(rx.State)` (not `BaseStateMeta` directly); `plugins/event_handler_api.py` `redact_router_session` handles
   `rx_router_session` and `RouterData`/`SessionData` values; `Requires-Dist: reflex[db]>=0.9.6`. Note anything else
   that changed vs 0.9.5 in those two modules.
2. FINDING-001 downstream / #7211: `import reflex_enterprise.auth.oidc.state`, the full `orch_probes/ent_import_probe.py`
   module list (relax the venv assert) → all OK with NO shim; the `MCPPlugin`-only app (`ent_mcp_oidc`, `a2_mcpapp`) and
   the `AuthPlugin`-only app start and answer `/ping` 200; `demos/oidc` imports and starts (CI=true).
3. FINDING-011 / #7214: `ent_map_dnd_flow_mantine/scripts/probe_router_redact.py` (argv venv marker → your venv) on
   enta2 → `VERDICT OK`; on `envs/ent` it prints LEAK (record); on `envs/entprev` OK. Then the HTTP proof: the
   unmodified `demos/tickets` on enta2 (CI=true, dev, your ports) with a copy of
   `ent_map_dnd_flow_mantine/verification/v_leak_http.py` → `retrieve_state` AND the ndjson event delta carry
   `rx_router_session` with `client_token`/`session_id` blanked (`client_ip` kept); nothing else in the bodies contains
   the server-side token. Optional dual-compat proof: a venv with 0.9.11.post1 + the 0.9.6a1 wheel → legacy `router`
   still redacted.
4. FINDING-003 enterprise manifestation: `ent_mcp_oidc/scripts2/uncached_after_login.py` (an `@rxe.var(auth=True,
   cache=False)` must show the server value right after login, not only after a reload) on enta2 → PASS expected now.
5. OIDC + MCP end to end on enta2 without any shim: the campaign's `ent_mcp_oidc` harness (login / reload / second tab /
   logout drivers, MCP resources and tools listing, protected handler enforcement) — everything the campaign recorded
   as passing "behind the metaclass shim" must pass with no shim; zero page errors / 4xx-5xx beyond the expected auth
   redirects.
6. Demos regression: `demos/ag_grid` (dev; prod is behind the paid-tier gate — note, do not force), `demos/map`, `dnd`,
   `flow`, `mantine` pages load and the campaign's interaction drivers pass with no console errors; the REST
   `EventHandlerAPIPlugin` endpoints on `tickets` behave as in the campaign (auth required, ndjson stream).
7. Pin sanity: `uv pip list --python $SB/envs/enta2/bin/python | grep -i reflex` and the wheel's Requires-Dist; note that
   0.9.6a1 still has no upper bound and whether that matters now that both halves are fixed.
Write the pass/fail table in NOTES.md and return it in the structured result.
