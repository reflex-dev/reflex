# Enterprise published-wheel verification

Test `reflex-enterprise==0.9.7a2` with `reflex==0.10.0a1` and the exact alpha
manifest at `../inventory/alpha-requirements.txt`. Only published PyPI wheels
are installed, in `/private/tmp/reflex-enterprise-test-20261005`; the source
checkout is reference material. Commands run from each sample app directory
with `PYTHONPATH` unset and `uv --no-config run --no-project --python` targeting
the isolated interpreter. The uv cache is `/private/tmp/reflex-enterprise-uv-cache`.

1. Verify package versions and import origins, plus release changelog and PRs.
2. Drive the upstream AG Grid 36 regression app: sorting, filtering, pagination,
   editing, pinned rows, selection APIs, overlays, themes, CSV, grouping,
   integrated charts, and HTTP infinite/server-side datasources.
3. Extend that app with Leaflet map controls, vectors, marker popup events,
   geolocation and map API callbacks, and saved grid state.
4. Test anonymous MCP sessions for session isolation, event execution, computed
   resource reads, router redaction and missing/fabricated token rejection.
5. Run a separate AuthPlugin + MCPPlugin app against published
   `oidc-provider-mock==0.4.2` on port 9131. Test protected pages, login,
   authorization, refresh, logout, iframe popup completion and MCP OAuth.
6. Compare suspected compatibility regressions with published Reflex 0.9.12.
7. Save browser console/network errors, backend excerpts, screenshots, results,
   reproduction commands, coverage limits and adversarial review in `REPORT.md`.

Development test apps use upstream's supported `CI=true` switch for the cloud
account check. This does not verify real cloud entitlement or paid production
licensing; those checks belong to the root packaging/tooling campaign.
