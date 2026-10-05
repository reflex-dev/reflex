# Cluster `ent_mcp_oidc` — enterprise MCP plugin and OIDC auth on reflex 0.9.12a1 vs 0.9.11.post1

**Known lead (orchestrator, before you start):** in `$SB/envs/ent` (0.9.12a1 train + `reflex-enterprise[mcp]==0.9.5`)
`import reflex_enterprise.auth.oidc.state` raises `TypeError: metaclass conflict: the metaclass of a
derived class must be a (non-strict) subclass of the metaclasses of all its bases`, while every
other enterprise module imports. `$SB/apps/probes/ent_import_probe.py` reproduces it; the
0.9.11.post1 baseline is `$SB/envs/entprev` + `ent_import_probe_prev.py`. Your first job: get the
full traceback, identify the class and the two metaclasses involved, and bisect it to the
framework change (candidates: #7068 router split — `BaseState.router` became a property /
`RouterDataVar`; #7077 `BaseVarShadowsInheritedVarError`; #7136 reserved names — `AuthUserState`
overrides `get_delta`; #6181/#6180; #7049 lazy imports). Read the failing rxe class definition in
`$SB/apps/packaging/entwheel/reflex_enterprise/auth/oidc/state.py`. Then determine the blast
radius: does `rxe.AuthPlugin()` work at all on 0.9.12a1? Does `rxe.App()` with `AuthPlugin`
start? Which user-facing enterprise features die with it?

Then the end-to-end work. The previous campaign built a complete harness — reuse it:
`git -C /home/user/reflex archive origin/claude/reflex-prerelease-testing-t0sd90 prerelease-testing/2026-09-10-v0.9.11a1/ent_mcp_oidc | tar -x -C $SB/apps/ent_mcp_oidc/`
→ `apps/mcpapp` (MCP exercise app), `apps/authapp` (OIDC exercise app with leak probes),
`idp/fake_idp.py` (self-contained OIDC provider with PKCE, refresh, userinfo, logout),
`scripts/mcp_drive.py`, `mcp_probe2.py`, `mcp_auth_probe.py`, `drive_auth.py`, and `NOTES.md`
with exact commands and the verdicts on earlier findings (FINDING-031/032/035 pre-existing quirks).
Run the whole thing on 0.9.11.post1 (baseline) and 0.9.12a1: anonymous token, auth rejection,
`initialize`, `tools/list`, `resources/list`, `search_events`, `queue_event` into root/sibling/
nested substates and background handlers, every `reflex://` resource (the MCP plugin walks
`RegistrationContext.get().base_states` — #7136 reserved names and #7068 router vars change what a
state's var list contains: check `reflex://state/vars/State` now lists `rx_router_*` and whether
the plugin handles them), the OAuth 2.1 metadata + 401 flow with `AuthPlugin`+`MCPPlugin`, and the
browser flow: anonymous browse → guard redirect → login through the IdP → authenticated pages →
reload → second tab → logout. Also `demos/oidc` from `/home/user/reflex-enterprise/demos/oidc`
against the fake IdP as the previous campaign did (its `requirements.txt` pins `reflex==0.8.14.post1`
— ignore the pin, use the train).

Auth internals this train touches: `AuthUserState.get_delta` override (filters the delta; #6946
changed `get_delta` for uncached vars), `enforcement.py` mutating `substate.dirty_vars` and reading
`event.router_data[CLIENT_TOKEN]` (#7068 caches connection-scoped router data at connect —
confirm the token still arrives per event and that REST/MCP-originated events have the right
token), `cookie.py` reading `instance.router_data` cookies and `dirty_vars.add(var_name)`,
`replay.py` (`pending.get_delta()`), the `@rxe.field/var/event` decorators tagging computed
vars/handlers (#7136 validates handler names before registration — do tagged handlers still
register?). Report regression vs pre-existing for every issue with evidence.
