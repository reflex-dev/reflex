Follow-up validation: **this reproduces on published Reflex/base 0.9.12 with enterprise 0.9.7a3.** I used a fresh isolated PyPI-only environment and the byte-identical minimal app/config from the alpha comparison, running through the public full-stack production CLI.

| Bearer | `POST /_reflex/mcp` | `POST /_reflex/mcp/` |
| --- | --- | --- |
| Missing | 405, no redirect | 401 |
| Fabricated | 405, no redirect | 401 |
| Valid anonymous token issued by this app | 405, no redirect | 200 initialization |

The published MCP SDK also fails initialization at the bare URL with HTTP 405. With the slash URL, initialization and `list_tools` succeed (HTTP 200/202/200), negotiating protocol `2025-11-25` and listing `search_events` and `queue_event`. Anonymous token issuance returns 200.

The production page loads in Chromium with no recorded console errors, page exceptions, HTTP errors or failed requests. Server output contains existing deprecation/plugin notices, without a traceback. All seven guard contexts have CI/harness flags absent and offline mode false; the official hosting SDK makes two HTTP requests to a disposable local account fixture with fictional Pro identity data. No real account or tier guard is modified.

Environment: CPython 3.12.1/macOS arm64, Bun 1.4.2, MCP 1.30.0, Playwright 1.55.0/Chromium 140.0.7339.16, exact 91-package stable graph. Framework imports resolve inside the fresh environment's site-packages; no checkout/editable package was installed.

- [Report and reproduction commands](https://github.com/reflex-dev/reflex/blob/ac56c845e6695db38b0c264a3ea68ee3d47e2976/prerelease_testing/2026-10-05/enterprise/a3/components/routing/stable-0.9.12/REPORT.md)
- [Raw responses, SDK trace and browser diagnostics](https://github.com/reflex-dev/reflex/blob/ac56c845e6695db38b0c264a3ea68ee3d47e2976/prerelease_testing/2026-10-05/enterprise/a3/components/routing/stable-0.9.12/logs/results.json)
- [Frozen graph](https://github.com/reflex-dev/reflex/blob/ac56c845e6695db38b0c264a3ea68ee3d47e2976/prerelease_testing/2026-10-05/enterprise/a3/components/routing/stable-0.9.12/requirements-lock.txt), [provenance](https://github.com/reflex-dev/reflex/blob/ac56c845e6695db38b0c264a3ea68ee3d47e2976/prerelease_testing/2026-10-05/enterprise/a3/components/routing/stable-0.9.12/logs/provenance.json) and [identical-source hashes](https://github.com/reflex-dev/reflex/blob/ac56c845e6695db38b0c264a3ea68ee3d47e2976/prerelease_testing/2026-10-05/enterprise/a3/components/routing/stable-0.9.12/source-comparison.json)

The failure is therefore not specific to Reflex 0.10 alpha. Enterprise a2 on stable Reflex was not tested, so the introducing release/root cause remains unidentified. This control covers initialization/tool listing, not the full event/resource surface. Both owned services are stopped; no framework fixes were applied.
