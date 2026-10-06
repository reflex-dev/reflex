# Published enterprise 0.9.7a4 authentication validation

No remaining release blocker was observed in this authentication lane. All 36 retained or focused browser cases passed, alongside field/scope checks and both MCP protocol checks. The two a3 failures now pass in the same copied samples with only the enterprise package changed. This is a local-provider, single-process development validation, not a claim about every identity provider or deployment.

## Exact environment and source

- CPython 3.12.1; published `reflex==0.10.0a1` and `reflex-enterprise==0.9.7a4`.
- Fresh environment `/private/tmp/reflex-enterprise-a4-20261005-alpha`, installed from PyPI with `uv --no-config pip install --only-binary :all:`. The 104-package graph differs from a3 only by `reflex-enterprise==0.9.7a3` → `0.9.7a4`; [requirements-lock.txt](requirements-lock.txt), [provenance.json](provenance.json), and [logs/pip-check.log](logs/pip-check.log) record the graph and origins. A cached resolver initially missed a4; refreshing that package's PyPI metadata succeeded. Both install logs are retained; this was not an unavailable publication.
- All app and driver execution used copied sources under `/private/tmp/reflex-enterprise-a4-20261005-auth`, with `PYTHONPATH` unset and `uv --no-config run --no-project --python` pointing to the fresh environment. No repository product installation, source installation, editable installation, `uv sync`, or package modification occurred.
- Explicit existing official Bun 1.4.2; published Playwright 1.55.0 with private Chromium 140.0.7339.16. Paths and Bun hash are in provenance. Configs already had the required ports and Bun path in a3. The only Python source change from the a3 bundle strengthens the focused reload driver with a second successive reload; all app bodies are unchanged. [source-hashes.json](source-hashes.json), [source-changes-from-a3.json](source-changes-from-a3.json), and [installed-enterprise-source-hashes.json](installed-enterprise-source-hashes.json) retain hashes.
- The retained full app and its 22 browser cases are the same upstream sources used for a3, not the newer PR's entire 24-case suite. Actual current issue #252 links merged [PR #255](https://github.com/reflex-dev/reflex-enterprise/pull/255), commit `faae5d2db97d00fb5736f29339c572b182e4b304`; issue #253 links merged [PR #256](https://github.com/reflex-dev/reflex-enterprise/pull/256), commit `8b060bcca817fb9efe4237fe107d75c91b776f93`. Issue/timeline, PR descriptions, and file diffs are saved here as JSON. Their source descriptions guided the focused checks; browser evidence establishes the passes.
- Provider `localhost:9131` exposed only fake Alice/Bob identities through published `oidc-provider-mock==0.4.2`. App ports were 3132/8132. Public CLI commands used `CI=true` to avoid unrelated real cloud login, while actual app authentication, authorization and local OAuth endpoints ran normally. No real account or cloud/IdP write was made. This lane does not evaluate Free-tier CLI guards.

## Results

| Check | a4 result | Evidence |
| --- | --- | --- |
| Enterprise/core field render variants | 4/4 pass; `NumberCastedVar` | [auth-field.log](logs/auth-field.log) |
| Extra-scope metadata setup | Pass; no removed `backend_vars` access | [oidc-scopes.log](logs/oidc-scopes.log) |
| Full upstream auth app, actual public CLI startup and browser | 22/22 pass, versus a3 21/22 | [auth-full-browser.json](logs/auth-full-browser.json), [server log](logs/auth-full-server.log) |
| Focused public navigation and two successive reloads | 3/3 fresh contexts pass | [reload-repeat.json](logs/reload-repeat.json) |
| Default `AuthPlugin`, four enhanced browser cases | 4/4 pass, versus a3 3/4 | [auth-min-default-browser.json](logs/auth-min-default-browser.json), [server log](logs/auth-min-default-server.log) |
| `offline_access` `AuthPlugin`, same four browser cases | 4/4 pass | [auth-min-extra-browser.json](logs/auth-min-extra-browser.json), [server log](logs/auth-min-extra-server.log) |
| Focused default-scope iframe pending replay | 3/3 fresh contexts pass automatically | [iframe-repeat.json](logs/iframe-repeat.json) |
| MCP OAuth: consent, S256 exchange, protected read, replay/rotation, root redaction | Pass | [mcp-oauth.json](logs/mcp-oauth.json) |
| Anonymous MCP: missing/fabricated bearer, state isolation, resources, redaction | Pass | [mcp-anonymous.json](logs/mcp-anonymous.json), [server log](logs/mcp-anonymous-server.log) |

The full app covers anonymous protected-field withholding, blocked-event replay, authorization checks, async checks, refresh, protected navigation, logout, and cross-user reset. Public navigation and both focused reloads retained `initial-secret`, `computed:initial-secret`, `admin-data`, and `async-admin-data` in each authenticated Alice context. No extra wait or recovery was needed.

Both minimal modes exercised protected profile login, Alice reveal, refresh, provider end-session, clean logged-out UI with message reset to `initial`, then Bob login and `revealed-bob` without Alice's displayed identity or prior message. The default pending iframe now receives `post_auth_generic`, returns automatically to `/`, displays `revealed-alice`, and clears pending storage in every repeat. The a3 diagnostic had required manual child navigation; no such recovery was executed on a4. See the [default iframe screenshot](screenshots/auth-min-default-iframe-replay.png), [logged-out screenshot](screenshots/auth-min-default-logged-out.png), and [Bob screenshot](screenshots/auth-min-default-bob.png).

MCP OAuth registration led to real local browser consent, then a successful S256 code exchange and authenticated `revealed-alice` read. Reusing the authorization code returned HTTP 400 `invalid_grant`; refresh returned a different refresh token; reusing the prior refresh token returned HTTP 400 `invalid_grant`. Root resource output blanked `client_token` and `session_id`. The separate anonymous backend rejected missing/fabricated bearer tokens with HTTP 401, while two legitimately issued local sessions remained separate: A count/doubled 4/8, B 0/0, with custom-resource and redaction assertions passing. Raw client secrets and exchanged tokens were not logged in these protocol evidence files.

## Diagnostics and blocker classification

No new failing behavior, critical failure, or demonstrated weak-security behavior was found in this lane. The previously reported public-page async-value regression and iframe pending-flow failure are resolved by the observed a4 runs. All prior a2/a3 evidence remains unchanged.

Full and enhanced browser matrices recorded zero page errors and zero console errors. Enhanced default/extra matrices recorded zero HTTP errors. Focused reloads recorded zero page errors and zero observed HTTP errors; focused iframe repeats recorded zero page errors. CLI logs contained no `Traceback` or `AttributeError` from these cases.

Requests are **not wholly clean**. The full matrix retained 24 `net::ERR_ABORTED` entries: 21 cookie-sync requests and 3 development route-module requests. Default/extra matrices retained 9/10 cookie-sync aborts; focused reloads retained 3. These categories were present in earlier successful/baseline runs and did not cause the asserted flows to fail. Their cause remains unresolved; this evidence does not establish a newly introduced regression, critical impact, or security weakness. [results-summary.json](results-summary.json) records exact counts; `null` means that a retained driver did not observe that metric, not zero. Framework deprecation warnings and in-memory token-store notices remain nonblocking observations.

All 44 copied Python sources parsed. Thirteen focused drivers/configs passed `ruff format --check`. The standalone focused lint check reported one `I001` import-order diagnostic in unchanged `check_mcp_oauth.py`; [ruff-check.log](logs/ruff-check.log) records it. This is a retained harness formatting limitation, not an a4 product failure. No format or package fix was applied.

## Reusable-driver review and limits

1. `recheck_reload.py` and `recheck_iframe.py` save per-attempt booleans but do not return nonzero when a case is false. Inspect their JSON. The current artifacts contain 3/3 true in each; main full/enhanced drivers also assert aggregate success and exited 0.
2. The MCP OAuth driver records browser page/console diagnostics but does not assert they are empty. They were inspected for this run and contain no errors. Its S256 check is a successful exchange, not a separately exercised wrong-verifier rejection. Replay assertions are explicit.
3. An idempotent `reveal` message and cleared pending storage establish successful automatic replay; these retained fixtures do not independently count handler executions to prove exactly once. Repeats did not force the deterministic cookie-before-message race used by the new upstream PR test.
4. The full driver records request failures, page and console errors but does not record every HTTP status; focused iframe repeats lack request/console listeners. Unobserved fields are disclosed rather than treated as clean requests. Redis, multi-process deployment, real-provider claims, expiry races and production authentication remain outside this local lane. Exceptional fail-closed checks are a separate root-owned lane.

[RUN.md](RUN.md) contains exact reproduction commands. Owned CLI/provider processes exited cleanly. Final probes found ports 3132, 8132 and 9131 closed; no a4 runtime reference was added to the shell profile. The neutral environments and evidence remain available; no commit, issue, or comment was created by this lane.
