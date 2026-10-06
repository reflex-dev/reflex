# Reflex 0.9.12 production MCP routing control

**The failure reproduces on published Reflex/base 0.9.12 with enterprise
0.9.7a3.** The minimal app and config are byte-identical to the previous alpha
comparison. The bare MCP URL returns 405 even with a valid issued token; the
slash URL authenticates and supports published SDK initialization/tool listing.

| Production request | Bare `/_reflex/mcp` | Slash `/_reflex/mcp/` |
| --- | --- | --- |
| No bearer | 405, no redirect | 401 |
| Fabricated bearer | 405, no redirect | 401 |
| Issued anonymous bearer | 405, no redirect | 200 initialization |
| Published MCP SDK with issued bearer | Initialization fails at HTTP 405 | Initialization and `list_tools` pass (200/202/200) |

The slash SDK negotiates protocol `2025-11-25` and lists `search_events` and
`queue_event`. The direct JSON-RPC probe uses protocol `2025-03-26`. Anonymous
token issuance is HTTP 200. No state mutation was attempted in this routing
control. The earlier alpha/a2 comparison remains under the parent directory.

This rules out an exclusively Reflex 0.10-alpha occurrence of the routing
failure. Enterprise a2 with stable Reflex was not tested here; these observations
do not identify which original release introduced the problem or establish its
root cause. No framework or generated-code fix was applied.

## Isolation and real execution

Fresh `/private/tmp/reflex-enterprise-mcp-stable-20261005-venv` installs only
published PyPI packages from [the exact 91-package stable graph](requirements-lock.txt).
CPython 3.12.1/macOS arm64, enterprise 0.9.7a3, Reflex/base 0.9.12, MCP 1.30.0,
Playwright 1.55.0/Chromium 140.0.7339.16 and existing Bun 1.4.2 were used.
`uv pip check` passes. [Provenance](logs/provenance.json) confirms isolated
site-packages imports and no direct-URL/editable distributions.

All app/driver execution occurs in neutral
`/private/tmp/reflex-enterprise-mcp-stable-20261005`. The public production CLI
uses full-stack port 3131. Seven recorded guard contexts show CI/harness flags
absent and offline mode false. The real hosting SDK makes two loopback HTTP
account requests with only fictional credentials; a disposable local fixture
returns Pro identity data. No live account is used, and no tier guard is patched.
[Source comparison](source-comparison.json) verifies every app/config/CLI-adapter
file against the previous alpha sample and actual stable execution; the saved
controller also matches the executed copy.

The real production page loads in Chromium and shows `MCP routing probe` and
counter 0. Browser console, page exceptions, HTTP errors and failed requests are
all empty. [Screenshot](logs/browser.png) and [raw results](logs/results.json)
retain this evidence. Server output has existing Sitemap/Radix/debug deprecation
notices and in-memory token-store guidance, with no traceback. Bun installation
is skipped. The expected bare-URL SDK error/traceback is in the results and
driver log; it is not a backend failure or a passing endpoint result.

Both CLI/account processes exit 0 on shutdown. [Cleanup](cleanup.json) confirms
ports 3131 and local account port 61332 have no listeners. Source snapshots
exclude generated assets, requirements, `.web`, state and runtime/cache files.

## Reproduce

Create a fresh UV environment and install `requirements-lock.txt` exclusively
from `https://pypi.org/simple`. Copy `source/` into a neutral directory. Configure
the saved app's Bun path if the recorded existing binary is unavailable, and
install published Playwright Chromium into a private browser cache if needed.
From the copied source directory:

```sh
env -u PYTHONPATH PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reflex-enterprise-browsers \
  UV_CACHE_DIR=/private/tmp/reflex-pre-uv-cache \
  uv --no-config run --no-project --python /private/tmp/your-stable-venv/bin/python \
  python validate.py
```

The controller owns the local account server and public CLI, saves logs beneath
its copied source directory, and shuts both down. Its `completed` flag means
the observation sequence finished; the default endpoint remains a failure.
Results must be interpreted using the recorded route statuses and SDK flags.

Adversarial review leaves two reusable-driver limitations for followup:
**1.** Cleanup calls occur before writing final JSON; an unexpected cleanup
exception can prevent partial result persistence. **2.** SDK checks do not have
an explicit controller deadline and this probe covers initialization/list-tools,
not the full event/resource or multi-worker surface. Current runs completed and
saved every observation. No driver changes followed this review.
