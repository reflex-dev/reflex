# Cluster `ent_map_dnd_flow_mantine` — the remaining enterprise demos on reflex 0.9.12a1 vs 0.9.11.post1: map, dnd, flow, mantine, highcharts, tickets

Prebuilt READ-ONLY venvs: `$SB/envs/ent` (0.9.12a1 train + `reflex-enterprise[mcp]==0.9.5` wheel) and
`$SB/envs/entprev` (0.9.11.post1 + wheel). Demos: `/home/user/reflex-enterprise/demos/{map,dnd,flow,mantine,highcharts,tickets}`
— copy each to `$SB/apps/ent_map_dnd_flow_mantine/<demo>_new` / `<demo>_prev` (tickets needs
`aiosqlite`: make your own venv copies for it). Run with `CI=true`, dev mode (try prod too and
record what the licence gate does).

The previous campaign's drivers are reusable — extract them:
`git -C /home/user/reflex archive origin/claude/reflex-prerelease-testing-t0sd90 prerelease-testing/2026-09-10-v0.9.11a1/ent_map_dnd_flow prerelease-testing/2026-09-10-v0.9.11a1/ent_mantine_highcharts_tickets | tar -x -C $SB/apps/ent_map_dnd_flow_mantine/`
(read both NOTES.md files first: they list every route, the interactions that matter, the
known pre-existing rxe quirks, and `runpair.sh`/`drive_ent.py` for running the version pair).

Drive as a user, per demo, on BOTH versions and diff: map (pan/zoom, markers, popups, layer
events → `EventChain` dict props, geolocation stubs), dnd (drag items between lists — real mouse
drags with Playwright `mouse.down/move/up`; `can_drop`/`on_drop` handlers; the `rx.EventChain.create`
calls in dnd.py:413/642/651 hit #7122's interning), flow (nodes/edges, connect, delete, the
`VarData`-heavy `flow/util.py` hooks → #7015 var hashing and #7198 operand references are relevant:
watch for dropped hooks/imports in the compiled page), mantine (every widget page: inputs bound to
State, `as_child`-style triggers now transparent per #6850), highcharts (chart types, State-driven
series, callbacks), tickets (`EventHandlerAPIPlugin` REST/OpenAPI surface: `curl` the generated
endpoints — it assigns `state.router = RouterData.from_router_data(...)` in
`plugins/event_handler_api.py:683`, which #7068 turned into a property setter decomposing into
five vars; verify a REST-triggered handler sees a correct `self.router` and that the response
still carries the delta; also the OpenAPI document with and without `pyyaml`).

Also run the enterprise import probe on both venvs first:
`$SB/apps/probes/ent_import_probe.py` (0.9.12a1) — the orchestrator already saw
`reflex_enterprise.auth.oidc.state` fail to import on 0.9.12a1 with a metaclass conflict; that
one belongs to the `ent_mcp_oidc` cluster, but note any other import difference you see.
Report every behavioral difference between versions with console/network/server-log evidence.
