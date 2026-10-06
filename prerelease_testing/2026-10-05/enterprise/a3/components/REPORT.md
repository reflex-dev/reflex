# Published enterprise 0.9.7a3 component rerun

Published a3 passed all 15 retained AG Grid scenarios and all five map/saved-state/font flows in both development and production. Anonymous MCP passed in development. The documented production MCP endpoint failed with HTTP 405; the explicit trailing-slash endpoint passed the complete MCP assertions. A minimal comparison reproduced the same routing failure on published a2, so this is a pre-existing integration issue rather than an a3 regression.

| Coverage | Development | Production |
| --- | --- | --- |
| AG Grid sorting/filter/pagination/pinned rows, edits/row IDs/state updates, selection, loading, CSV, grouping, integrated chart, four legacy themes, two overlay cases, infinite/server-side HTTP datasources | 15/15 | 15/15 |
| Map controls, vectors/bounds callback, popup/backend event/geolocation/fly-to invocation, saved LocalStorage grid sort/reload, Google Font head | 5/5 flows; bounds/storage evidence recorded | 5/5 flows; bounds/storage evidence recorded |
| Anonymous MCP default `/_reflex/mcp` | Pass: bearer rejection, session isolation, mutation/computed reads, custom resource, router redaction | **Fail: HTTP 405**, before authentication |
| Anonymous MCP explicit `/_reflex/mcp/` diagnostic | Unnecessary | Pass: same complete assertions |

The MCP checks reject missing and fabricated bearers, issue two anonymous tokens, increment only session A to count 4/doubled 8 while B stays 0/0, read a parameterized custom resource, and verify empty router `client_token`/`session_id`. Fly-to coverage invokes both exposed commands and checks browser errors; it does not assert the final geographic center.

## Confirmed production endpoint issue

On the fullstack production origin, `POST /_reflex/mcp` returns `405 Method Not Allowed`, whereas `POST /_reflex/mcp/` reaches authentication and returns 401 for missing/fabricated credentials. Development redirects the bare endpoint with 307 and then returns 401. The published plugin's module documentation advertises the bare endpoint.

The identical minimal app was run through the public production CLI on fresh environments with 104 packages. The only graph difference was `reflex-enterprise==0.9.7a2` versus `0.9.7a3`; both reproduced 405 at the bare endpoint and 401 at the slash endpoint. Both issued anonymous tokens with 200. Evidence: [comparison.json](routing/comparison.json), each version's `routing/{a2,a3}/results.json`, server logs, contexts and network audits. The static frontend catch-all shadowing Starlette's slash redirect is an inference from the installed source and responses, not a confirmed root-cause fix. No framework or enterprise source was changed.

The initial failure is retained in [default-endpoint evidence](evidence/prod-default-endpoint/logs/mcp-http.json). The working slash run remains a diagnostic, and is not counted as a default production endpoint pass.

The subsequent [published Reflex 0.9.12 control](routing/stable-0.9.12/REPORT.md)
also reproduces the bare-route 405 with enterprise a3, including a valid bearer.
The slash route returns 401 for invalid credentials and 200 for a valid token;
published MCP SDK initialization/list-tools passes there. App/config source is
byte-identical to the alpha comparison. This is also present on stable Reflex;
enterprise a2 on stable was not tested.

## Exact execution boundary

- Fresh `/private/tmp/reflex-enterprise-a3-20261005-components` venv, Python 3.12.1. The retained enterprise requirements graph changed only a2 to published PyPI a3. [requirements-lock.txt](requirements-lock.txt), [a2 baseline graph](requirements-a2-baseline.txt), [provenance.json](provenance.json). `uv pip check` validated all 104 packages.
- All app and driver execution used neutral copies under `/private/tmp/reflex-enterprise-a3-20261005-components-app`, `PYTHONPATH` unset, `uv --no-config run --no-project --python ...`. No checkout/editable/source distribution installation occurred. Framework imports resolve inside the environment's `site-packages`.
- Development used ports 3131/8131, the established component lane's explicit `CI=true`, an empty disposable credential file, and unset ambient access tokens. This lane does not test account guards.
- Production used the public CLI on fullstack port 3131, with CI, app harness and offline bypasses disabled. A local HTTP endpoint returned fictional Pro identity data to the real hosting SDK. Credential paths were redirected to a disposable fictional token file. Context logs confirm no bypasses; the two main Python account connections went to loopback port 54717 and the four final comparison connections to loopback port 58000. No real account or cloud mutation occurred.
- Explicit pre-existing Bun 1.4.2 avoided the installer and shell startup changes. Published Playwright 1.55.0 used separate private Chromium 140.0.7339.16. The resolved frontend included AG Grid 36.2.0, AG Charts 14.2.0, React 19.3.0, Leaflet 1.9.4 and React Leaflet 5.0.0; [complete frontend versions](frontend-versions.json) and generated Bun lock are retained.

## Diagnostics and fixture corrections

Final browser runs had zero page exceptions and zero HTTP errors. Grid runs had zero failed requests. Console error lines were exclusively the expected unlicensed AG Grid/Charts trial banners: development grid/maps 210/28 lines; production 105/14. Map runs recorded 32 development and 29 production OpenStreetMap tile `ERR_ABORTED` requests during route/zoom transitions, with no HTTP failures. Raw console locations, request failures, screenshots and MCP HTTP response traces are saved under `evidence/`; [results-summary.json](results-summary.json) records exact counts. Server logs contain existing Sitemap/Radix/ArrayVar and logging deprecation notices, with no final traceback.

Two fixture-only corrections are preserved separately: the CLI adapter initially lacked the multiprocessing main guard; production minification changed the bounds object's console label from `LatLngBounds` to `O`. The final bounds assertion inspects both returned coordinate corners rather than the constructor name. Initial failures remain under `fixture-main-guard-initial.log` and `evidence/prod-initial-map-fixture/`. A first minimal comparison attempt was stopped by the loopback-only audit during automatic npm registry probing; explicitly configuring `NPM_CONFIG_REGISTRY` allowed the comparison while leaving the audit active. That rejected attempt is retained in `routing/initial-registry-audit/`.

`source/` and `routing/source/` contain neutral app/driver snapshots with hashes. Snapshot equality, Python parsing, targeted Ruff E4/E7/E9/F/I/B checks and formatting passed. All owned app/comparison/HTTP fixture processes were stopped; ports 3131, 8131, 54717 and 58000 had no listeners. [Cleanup evidence](logs/cleanup.txt). Prior a2 evidence was preserved.

## Reuse

Copy `source/` to a neutral runtime directory. Install the exact lock into a fresh PyPI-only venv with `uv --no-config pip install --python ENV/bin/python --index-url https://pypi.org/simple -r requirements-lock.txt`. Run the CLI adapter from the copied `app/`, with `TEST_HOSTING_CONFIG` pointing at an empty disposable file for development. Drivers take `QA_FRONTEND`, `QA_BACKEND` and `QA_OUTPUT`; `QA_MCP_PATH` defaults to the documented bare path.

For production, start the copied `account_fixture.py` with `QA_FIXTURE_TOKEN`, `QA_ACCOUNT_AUDIT` and `QA_ACCOUNT_PORT_FILE` under `/private/tmp`. Use only that fictional token in the disposable hosting file, set both Reflex Cloud URL variables to its loopback URL, and supply `QA_NETWORK_AUDIT`/`QA_CONTEXT_AUDIT`. The comparison driver reads the fixture port file through `QA_ACCOUNT_PORT_FILE`; its two published environment paths and owned app ports are explicit fixture inputs. Keep an existing Bun path and private browser cache configured. This fixture is intended for local published-package testing, not account-policy validation.

Adversarial review: **1.** The documented production MCP path remains unusable in this fullstack configuration on both a2 and a3; the slash diagnostic must remain separate from the failing matrix cell. **2.** Fly-to checks cover event invocation and lack of browser exceptions, not exact resulting center coordinates. No source fix or external issue/comment was submitted.
