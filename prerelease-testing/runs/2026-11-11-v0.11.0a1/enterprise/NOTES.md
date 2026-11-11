# enterprise cluster — reflex-enterprise 0.9.11 (PyPI) on reflex 0.11.0a1

## Status / resume here
- [in progress] Step 1 static scan.
- Venvs: `$SB/envs/new-ent` (reflex 0.11.0a1 + rxe 0.9.11[mcp], redis 8.2.0b1), `$SB/envs/prev-ent` (reflex 0.10.1 + rxe 0.9.11, redis 7.4.1). Both: mcp 1.30.0, oidc-provider-mock 0.4.8, starlette 1.10.0, granian 2.8.7, no fastapi.
- Ports: fe 3380-3399, be 8380-8399; Redis 8399, mock IdP 8398, account stub 8397 (127.0.0.1).
- Work dir: `$SB/apps/enterprise/` (SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad).
- Upstream rxe source (tag v0.9.11) became available read-only at /home/user/reflex-enterprise mid-run (demos/ + tests/).

