# Enterprise alpha compatibility report

This is the historical **0.9.7a2** report. The [published a3 rerun](a3/REPORT.md)
resolves its field/scope/logout blockers and records the remaining failures.

Tested published `reflex-enterprise==0.9.7a2` with the exact announced alpha
manifest, including `reflex==0.10.0a1`, on CPython 3.12.1/macOS arm64.
Two compatibility defects remain: enterprise auth fields cannot render, and
OIDC extra-scope setup/session cleanup use a removed state attribute.

Release source audit: branch `r/pre-2026.10.05` was observed at commit
`40aa7b33af419a6dc354e33873f6cd1270d28205`; its
[changelog head and implementing PR references](reference/RELEASE-PROVENANCE.md)
are saved independently of the installed PyPI package. The AG Grid changelog
uses an orphan issue link that returns 404; the implementing PR is #238.

The follow-up [Free-tier production/export report](free_tier/REPORT.md) verifies
eight public CLI cases against a disposable local account API with CI and
app-harness bypasses absent. Badge enforcement and export inclusion pass.
Rejected credentials prevent output/startup but return exit 0; the same denial
implementation exists in published a1 source. Live cloud entitlement remains
unverified.

## Confirmed findings

1. **Enterprise auth fields fail to compile on Reflex 0.10.0a1.**
   `public_count: rx.Field[int] = rxe.field(0, auth=False)`,
   the same field with `auth=True`, and `public_simple: int = rxe.field(...)`
   stay `reflex_enterprise.auth.decorators._AuthField` objects on class access.
   Rendering any of them with `rx.text` raises `ChildrenTypeError`.
   A neighboring `rx.field` becomes a `NumberCastedVar` and renders normally.
   The unchanged upstream `AuthFlowApp` cannot compile for this reason.
   All four variants pass with the identical enterprise wheel and published
   Reflex 0.9.12. The root agent independently reproduced both results.
   Evidence: [minimal repro](repro_auth_field.py),
   [alpha log](logs/repro-auth-field-alpha.log),
   [stable log](logs/repro-auth-field-stable.log),
   [full auth app compile failure](logs/auth-run.log).

   The installed enterprise `_AuthField.__set_name__` records auth metadata
   without calling its superclass. The new core `Field.__set_name__` now
   performs descriptor initialization. That is the source-level explanation
   for the observed difference; no library was patched to test it.

2. **OIDC code still reads the removed `State.backend_vars` attribute.**
   Two public user flows reproduce this:

   - `AuthPlugin(extra_scopes=["offline_access"])` fails during a normal
     `reflex run` compile at `OIDCAuthState._set_extra_scopes`, which reads
     `GenericOIDCAuthState.backend_vars`. The app uses only core fields and
     normalized OIDC profile vars, independently of finding 1.
   - Default `AuthPlugin(extra_scopes=[])` compiles and logs in successfully.
     Clicking `AuthUserState.logout` raises the same attribute error in
     `enforcement._reset_protected(ProfileState)`. The page remains on
     `/profile` with a **Logout error** toast and the user's name/email visible.
     The provider's end-session page is never reached.

   Cleanup is partial: after the error, a protected Reveal action redirects to
   `/login`, and fresh `/profile` navigation also redirects to `/login`.
   The still-visible identity is stale UI. These tests do **not** demonstrate
   continued authorization after logout.

   Stable Reflex 0.9.12 passes extra-scope setup and the full upstream logout
   cases with the same enterprise 0.9.7a2 wheel. The root agent independently
   confirmed alpha compile and logout failures.
   Evidence: [public CLI sample](apps/auth_min/rxconfig.py),
   [extra-scope compile log](logs/auth-min-alpha-run.log),
   [minimal metadata repro](repro_oidc_scopes.py),
   [alpha metadata log](logs/repro-oidc-scopes-alpha.log),
   [stable metadata log](logs/repro-oidc-scopes-stable.log),
   [logout browser repro](repro_logout.py),
   [post-error behavior](logs/repro-logout-alpha.json),
   [backend runtime log](logs/auth-min-default-alpha-run.log).

   ![Logout error while the old identity remains visible](screenshots/oidc-logout-error-alpha.png)

## Coverage and results

| Surface | Result | Evidence |
| --- | --- | --- |
| AG Grid 36.2.0 render, nested snake-case definitions, sort, filter, pagination, pinned rows | Pass | `logs/components-browser.json` |
| Grid edit event payload, stable row ID, backend row replacement | Pass | Same |
| Selection events, select/deselect/select-by-key Python APIs | Pass | Same |
| Loading and no-matching-rows overlays, `suppress_overlays` | Pass | Same |
| All four legacy themes with actual row dimensions/styles | Pass | Same |
| CSV download contents | Pass | Same |
| Enterprise grouping/aggregate values/expansion | Pass | Same |
| Integrated AG Charts 14.2.0 chart with accessible series | Pass | Same, `screenshots/ag-grid-integrated-chart.png` |
| Infinite and server-side HTTP datasource pagination and sorting/query parameters | Pass | Same |
| Advanced grid state serialized to LocalStorage, sorting restored after reload | Pass | `logs/maps-saved-state-browser.json` |
| Leaflet controls, five vector paths, map bounds API callback | Pass | Same |
| Map zoom backend events, marker popup button event, mocked browser geolocation, fly-to APIs | Pass | Same |
| New `google_font("Inter", weights=[400, 700])` stylesheet in head, swap and preconnect | Pass | Same |
| Anonymous MCP bearer rejection, events, computed reads, parameterized app resource | Pass | `logs/mcp-anonymous.json` |
| Anonymous MCP separate token/session isolation and router token redaction | Pass | Same |
| MCP OAuth discovery, dynamic client registration, browser OIDC + consent + scopes, PKCE | Pass | `logs/mcp-oauth.json` |
| OAuth-protected MCP event resolves Alice, full-state token redaction | Pass | Same |
| OAuth authorization code is single-use; refresh rotates and rejects replay | Pass | Same |
| Default alpha OIDC profile login, name/email, protected events and pending-event replay | Pass | `logs/auth-min-alpha-browser.json` |
| Iframe direct OIDC login popup opens, authenticates, closes and updates opener | Pass | Same |
| Default alpha logout | **Fail**, finding 2 | `logs/repro-logout-alpha.json` |
| Alpha enterprise auth fields/full upstream auth app | **Fail**, finding 1 | `logs/repro-auth-field-alpha.log` |
| Alpha extra OIDC scopes | **Fail**, finding 2 | `logs/auth-min-alpha-run.log` |
| Previous stable full upstream auth flows, including refresh, sync/async authorization, redelivery, logout and next-user reset | 22 cases pass | `logs/auth-stable-browser.json` |

The final grid run executes all 15 upstream browser cases on the isolated
Playwright Chromium 140 runtime and rejects page exceptions, AG Grid/Charts
configuration errors and HTTP error responses. It reported none.
Expected unlicensed enterprise trial banners were present; enterprise features
ran successfully. The maps run reported no page exceptions. OSM tile requests
cancelled during deliberate route navigation were captured as
`net::ERR_ABORTED`; those are not failed map assertions.

Two early test assertions were corrected: Reflex LocalStorage keys have a
`_rx_state_` suffix, and Leaflet's console bounds callback prints
`LatLngBounds`, with coordinates available through the console argument.
The final saved-state and bounds tests assert the actual storage and object
contents. No failed test was converted into a framework workaround.

## Isolation and provenance

- Alpha environment: `/private/tmp/reflex-enterprise-test-20261005`.
- Stable environment: `/private/tmp/reflex-enterprise-baseline-20261005`.
- Only exact published PyPI packages were installed, using
  `uv --no-config pip install --python ... --index-url https://pypi.org/simple`.
- `requirements-lock.txt` records the final alpha/test dependency graph.
  The alpha manifest is `../inventory/alpha-requirements.txt`.
- Import-origin assertions show Reflex and enterprise under each isolated
  environment's site-packages. No checkout/editable/source install or
  `PYTHONPATH` injection was used.
- Apps run from their own directories through `uv --no-config run --no-project
  --python <isolated interpreter>`. `--no-config` prevents the repository's
  older resolver upload cutoff from excluding newly published alphas.
- Published `playwright==1.55.0`, its private downloaded Chromium runtime,
  `oidc-provider-mock==0.4.2` and MCP SDK `mcp==1.30.0` provide the tests.
  `uv pip check` passed.
- Upstream source is reference material from
  [enterprise prerelease branch](https://github.com/reflex-dev/reflex-enterprise/tree/r/pre-2026.10.05),
  with [AG Grid upgrade PR 238](https://github.com/reflex-dev/reflex-enterprise/pull/238),
  [font helper PR 239](https://github.com/reflex-dev/reflex-enterprise/pull/239),
  [Free-tier commands PR 241](https://github.com/reflex-dev/reflex-enterprise/pull/241),
  and the branch changelog reviewed.
- `apps/components` copies the upstream grid regression app and map demos.
  The map route decorator is reduced to registering pages. The advanced
  serialization demo uses four deterministic local records instead of fetching
  a remote Olympic data file. Added test state supplies MCP event/resources.
- `apps/auth` lifts the upstream `AuthFlowApp` body to module scope without
  changing its auth behavior. `apps/auth_min` independently tests normalized
  profile vars using core fields.
- `CI=true` is the upstream auth tests' supported cloud-account-check bypass.
  Final app configs disable telemetry. The mock client/provider and OAuth
  registration/consent/token mutations are local. No real IdP credentials were
  needed and bearer/refresh tokens or client secrets are not written to evidence.

## Reproduction

Use a fresh temporary environment and published packages:

```sh
export UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache
export PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reflex-enterprise-browsers
uv --no-config venv --python 3.12 /private/tmp/reflex-enterprise-test-20261005
uv --no-config pip install --python /private/tmp/reflex-enterprise-test-20261005/bin/python --index-url https://pypi.org/simple -r prerelease_testing/2026-10-05/inventory/alpha-requirements.txt 'reflex-enterprise[mcp]==0.9.7a2' 'playwright==1.55.0' 'pytest==8.4.2' 'oidc-provider-mock==0.4.2'
uv --no-config run --no-project --python /private/tmp/reflex-enterprise-test-20261005/bin/python playwright install chromium
```

From `enterprise/apps/components`, start the grid/map/anonymous MCP app:

```sh
env -u PYTHONPATH CI=true UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache /Users/masenf/.local/bin/uv --no-config run --no-project --python /private/tmp/reflex-enterprise-test-20261005/bin/python reflex run --frontend-port 3131 --backend-port 8131 --loglevel debug
```

In another terminal in that same directory, prefix each driver below with:

```sh
env -u PYTHONPATH PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reflex-enterprise-browsers UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache /Users/masenf/.local/bin/uv --no-config run --no-project --python /private/tmp/reflex-enterprise-test-20261005/bin/python python
```

Driver arguments: `../../drive_components.py`,
`../../drive_maps_saved_state.py`, or `../../check_mcp.py`.

The field repro requires no running app. From `enterprise/apps/auth_min`:

```sh
env -u PYTHONPATH UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache /Users/masenf/.local/bin/uv --no-config run --no-project --python /private/tmp/reflex-enterprise-test-20261005/bin/python python ../../repro_auth_field.py
```

For OIDC, start the provider from `enterprise/apps/auth_min`:

```sh
env -u PYTHONPATH UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache /Users/masenf/.local/bin/uv --no-config run --no-project --python /private/tmp/reflex-enterprise-test-20261005/bin/python python ../../mock_oidc.py
```

From that same directory in another terminal, the public compile failure:

```sh
env -u PYTHONPATH CI=true AUTH_TEST_EXTRA_SCOPES=1 OIDC_ISSUER_URI=http://localhost:9131 OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1 UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache /Users/masenf/.local/bin/uv --no-config run --no-project --python /private/tmp/reflex-enterprise-test-20261005/bin/python reflex run --frontend-port 3132 --backend-port 8132 --loglevel debug
```

Omit `AUTH_TEST_EXTRA_SCOPES=1` to start the default plugin. Run
`../../repro_logout.py`, `../../drive_auth_min.py`, or
`../../check_mcp_oauth.py` using the same driver prefix above.
The first two exit nonzero on the confirmed logout defect.

Stable comparison uses a separate `uv venv` with exactly
`reflex==0.9.12`, `reflex-enterprise[mcp]==0.9.7a2`,
`playwright==1.55.0`, and `oidc-provider-mock==0.4.2`.
Run the field/metadata repro with that interpreter. To repeat the 22 full
upstream auth-flow cases, stop the alpha app on 3132/8132, start
`enterprise/apps/auth` through that stable interpreter with the OIDC env vars,
then execute `../../drive_auth.py` through the alpha testing interpreter.
The driver imports test definitions; app execution uses only the stable
environment.

## Remaining gaps and review

1. Actual cloud account/tier entitlement remains unverified. The follow-up
   [local guard report](free_tier/REPORT.md) covers 0.9.7a2 Free production and
   exports, forced badge output, an Enterprise badge-off control, and rejected
   credentials through the public CLI. Those real builds/browser checks use a
   disposable HTTP account API and do not establish live paid-license or
   cloud-deployment acceptance.
2. AG Grid model wrappers backed by SQLModel/SSRM, master-detail, tree data,
   pivot, cell selection/fill handle, aligned grids, custom renderers and
   backward pinned-row aliases were not driven. HTTP server-side and infinite
   datasource behavior were driven, but that does not cover database wrappers.
3. Map layer-switching controls remain commented out upstream. Marker dragging,
   location-denied behavior and touch interactions were not tested.
4. Multi-provider auth, provider-side expired/revoked-session recovery,
   callback nonce mismatch/reconnect deduplication, Redis/multiple workers,
   callable field authorization, and every MCP scope-denial/consent-denial/
   rate-limit/upload/background-event combination were not covered.
5. DnD/kanban, React Flow, Mantine, AG Charts standalone and Highcharts demos
   were not run. None is a new changelog addition in this enterprise alpha.
6. The helper scripts use repository-pinned published Ruff 0.16.4;
   E4/E7/E9/F/I/B checks pass. The follow-up source comparison helper has one
   recorded formatting-only wrap left after final review. A full
   repository-rule check reports
   inherited upstream-demo docstring/commented-code issues and standalone
   script namespace/print rules. Framework unit coverage, Pyright and generated
   stubs were not run because no framework implementation was changed.
7. The source diff contains only test samples, drivers, evidence and reports.
   No workaround was installed into the tested libraries. Both confirmed
   findings still reproduce and need release-owner followup; no fix is included.

Servers and mock provider are stopped after final evidence collection. Generated
frontend/state/cache files are ignored; temporary package/browser environments
remain available for another verification run.
