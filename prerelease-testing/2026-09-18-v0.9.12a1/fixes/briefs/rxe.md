# rxe — FINDING-011 / issue reflex-dev/reflex#7214, plus the downstream half of FINDING-001 / reflex-dev/reflex#7211: reflex-enterprise compatibility with reflex 0.9.12

Worktree: `/home/user/wt/rxe` — a git worktree of the reflex-enterprise clone `/home/user/reflex-enterprise` (treat that
clone as READ-ONLY, same rules as for `/home/user/reflex`). Branch: `fix/reflex-0.9.12-compat` (from `main`, commit
592d5cc). Ports: 3980-3989 / 8980-8989. Repository: `reflex-dev/reflex-enterprise` (internal). Its `.venv` from
`uv sync` has reflex 0.9.6 locked on Python 3.14 — do NOT use it for the 0.9.12a1 checks; create your own venvs in
scratch (below). In this repository, qualify issue references as `reflex-dev/reflex#7214` / `reflex-dev/reflex#7211`
(a bare `#7214` would point at an rxe issue).

Campaign material: FINDINGS.md `## FINDING-011` and `## FINDING-001`; `ent_map_dnd_flow_mantine/NOTES.md` "ISSUE 2"
and its `## VERIFICATION`, `ent_map_dnd_flow_mantine/scripts/probe_router_redact.py`,
`ent_map_dnd_flow_mantine/verification/v_leak_http.py`; `ent_mcp_oidc/NOTES.md` and
`ent_mcp_oidc/scripts2/oidc_meta_shim.py` (the campaign's test-only shim — NOT a fix); `orch_probes/metaclass_probe.py`.
The venv `.../scratchpad/envs/ent` (read-only) holds the PUBLISHED rxe 0.9.5 wheel with reflex 0.9.12a1 and
demonstrates both defects; `.../scratchpad/envs/entprev` holds rxe 0.9.5 with reflex 0.9.11.post1.

Two defects, both in reflex-enterprise, both triggered by the published reflex 0.9.12a1:

1. `reflex_enterprise/plugins/event_handler_api.py:733 redact_router_session()` blanks `router.session.client_token` /
   `session_id` in a state dict. Since reflex #7068 the root state dict has no `router` key — it carries
   `rx_router_url`, `rx_router_page`, `rx_router_session`, `rx_router_headers`, `rx_router_route_id` (check the exact
   wire key names, e.g. `rx_router_session_rx_state_`, in `state.dict()` on 0.9.12a1). The redaction therefore silently
   no-ops and `POST /_reflex/retrieve_state` and the ndjson event deltas return the server-side client_token/session_id.
2. `reflex_enterprise/auth/oidc/state.py:347 class OIDCCookieMeta(BaseStateMeta)`: reflex 0.9.12a1's `rx.State` uses the
   sibling metaclass `_StateMeta(BaseStateMeta)` (reflex #7136), so `class OIDCAuthState(ConfigMixin, rx.State,
   mixin=True, metaclass=OIDCCookieMeta)` (line 381) raises `TypeError: metaclass conflict` and every AuthPlugin /
   MCPPlugin / EventHandlerAPIPlugin app dies at startup. reflex may also fix this on its side (#7211), but rxe must not
   depend on that.

Fix goals:
- (1) Redact the session data wherever it lives: the legacy `router` entry (reflex < 0.9.12) AND the split
  `rx_router_session` entry (reflex >= 0.9.12), in the root state dict and in deltas. Check every caller of
  `redact_router_session` and every other place that serialises state for the REST / MCP / agent surfaces
  (`grep -rn "redact_router_session\|client_token\|router" reflex_enterprise/plugins reflex_enterprise/mcp`).
  Redact by structure (the SessionData fields), never by string-matching values. Keep the function's public
  signature.
- (2) Make the metaclass compatible with both reflex versions: `class OIDCCookieMeta(type(rx.State))` (or
  `type(reflex.state.BaseState)`) works on 0.9.11.post1 (where it IS `BaseStateMeta`) and on 0.9.12a1. Keep the
  cookie-descriptor behaviour identical; check for any other `BaseStateMeta` use in the package.
- Pins: do NOT change `reflex[db] >=0.9.6` yourself. In REPORT.md recommend what the next rxe release should pin
  (keep the floor if your fix is dual-compatible; say so explicitly) and note that the already-published 0.9.5 has
  no upper bound on reflex.
- Follow this repository's own conventions (look at `tests/units/`, `news/`, `CHANGELOG.md`, the `[tool.*]` sections
  of `pyproject.toml`, README/docs notes) for tests, lint/format and changelog fragments. If it uses towncrier-style
  `news/` fragments like reflex does, add one fragment per defect.

Regression tests (`tests/units/`, following the existing layout): (a) `redact_router_session` on a dict shaped like
0.9.12a1's root state (an `rx_router_session…` entry carrying client_token/session_id, as SessionData and/or as a
plain dict — match what the callers pass) leaves no token anywhere, and the legacy `router`-shaped dict still
redacts; (b) `OIDCAuthState` (or a minimal State using `OIDCCookieMeta`) can be defined with the installed reflex.
Run the unit tests in BOTH venvs below. They must fail before the fix where applicable ((a) on the 0.9.12a1 shape;
(b) as an import error under 0.9.12a1).

Venvs (create under your scratch dir; install the worktree EDITABLE so your edits are live):
- `v12`: `uv venv <scratch>/v12 --python 3.11 && uv pip install --python <scratch>/v12/bin/python --prerelease=allow
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' -e "/home/user/wt/rxe[mcp,testing]" pytest`
  — verify with `uv pip list --python <scratch>/v12/bin/python` that reflex is 0.9.12a1 and reflex-enterprise resolves
  to the worktree. If the `[mcp]` extra will not resolve, install without it and say so in REPORT.md. The full set of
  component alpha names is visible via `uv pip list --python .../scratchpad/envs/shared/bin/python`.
- `v11`: the same with `'reflex==0.9.11.post1'` and no `--prerelease` flag (dual-compat proof; component packages
  resolve to their stable releases).

E2E:
1. A copy of `probe_router_redact.py` (it asserts a venv marker in `reflex.__file__` via argv — pass a matching marker)
   run from a neutral cwd in `v12` must print `VERDICT OK`; with the published package (`envs/ent/bin/python`, read-only)
   it prints `LEAK`. Also run it in `v11` → OK.
2. `<scratch>/v12/bin/python -c "import reflex_enterprise.auth.oidc.state"` succeeds (it raises TypeError in `envs/ent`).
3. The HTTP proof: run the `tickets` demo (copy `/home/user/wt/rxe/demos/tickets` to scratch; read the campaign NOTES
   for how it was started — `CI=true`, dev mode, `REFLEX_TELEMETRY_ENABLED=false`, your ports) with `v12` and your fixed
   package, WITHOUT the metaclass shim (your fix makes it start), then a copy of `v_leak_http.py` against it → the
   tokens are blanked in both `retrieve_state` and the event delta. Save the response bodies (token values masked)
   under `/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/fixes/rxe/evidence/`.

Deliverables: commits on `fix/reflex-0.9.12-compat` (one per defect is ideal; bodies say `Fixes reflex-dev/reflex#7214`
and `Refs reflex-dev/reflex#7211`), `git format-patch origin/main` output saved to
`/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/fixes/rxe/patches/`, and REPORT.md under `fixes/rxe/` as the
shared brief describes. Never push, never open a PR.
