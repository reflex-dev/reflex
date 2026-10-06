# Published enterprise 0.9.7a3 validation

Enterprise **0.9.7a3 resolves all three a2 blockers observed in this campaign**:
auth fields render and hydrate, extra OIDC scopes compile and work, and logout
clears the UI and permits a different user to log in. Validation is **not fully
passing**: protected async computed values fail to restore on public pages with
Reflex 0.10.0a1, while identical stable controls pass. An embedded pending-event
login flow and production MCP routing also expose residual limits below.

All installs use published PyPI distributions in fresh isolated UV environments.
The alpha lanes freeze the previous 104-package enterprise graph and change
only `reflex-enterprise==0.9.7a2` to `0.9.7a3`. Stable uses Reflex 0.9.12 with the
same a3 wheel. Apps run from neutral temporary directories with `PYTHONPATH`
absent and workspace resolution disabled. No branch build, editable install or
framework fix was used. The original a2 artifacts remain intact.

[Publication audit](publication.json) confirms both non-yanked PyPI archives,
matching SHA256 downloads, and all 39 stub names/content matching between wheel
and sdist. [Exact alpha graph](requirements-alpha-lock.txt) and each lane's
provenance retain interpreter, package versions and site-packages origins.

| Exploration | Observed result |
| --- | --- |
| Auth fields and scope metadata on alpha/stable | Four field variants pass; extra-scope checks pass |
| Full auth browser suite | Alpha 21/22; stable 22/22 |
| Independent small async protected-var app | Alpha fails 3/3 public navigation/reload observations; stable passes 3/3 |
| AG Grid edits, selections, filters, serialization, download, charts and datasource flows | 15/15 in dev and 15/15 in production |
| Maps, saved state and font helper | 5/5 flows in each mode, plus bounds/storage checks |
| OAuth MCP | Discovery, registration, browser consent, PKCE, protected events, redaction, code replay rejection and refresh rotation/replay rejection pass |
| Anonymous MCP | Dev passes; production default URL fails 405; explicit slash URL passes full session-isolation/redaction checks |
| HTTP-only cookies, inherited cached vars and `rx.memo` | 6/6 production-browser scenarios on alpha and stable |
| Free-tier production/export guard and badge matrix | 8/8; rejected operations still return exit 0 |

The parallel agents retained the requested Sol 6.1 Extra High configuration.
Playwright Chromium 140 and Bun 1.4.2 were used for the rerun. Browser console,
page errors, network responses/request failures, and backend output are saved.
No real account, external identity provider or production cloud API was changed.

## Residual findings

1. **Protected async computed values on a public page.** Authenticate Alice on
   `/dashboard`, observe `async-admin-data`, then fully navigate to the public
   `/` route and reload. Alpha shows `async-admin-placeholder` indefinitely,
   including an additional 15-second wait; synchronous protected values and
   Alice's identity remain correct. The full auth test fails and repeated
   observations confirm it. A small app using core State fields, an awaited
   sibling-State authorization check and `rxe.var` reproduces without enterprise
   field wrappers or MCP. Identical source on stable restores the async value.
   This is a confirmed alpha/stable compatibility difference. It is not proven
   to have been introduced by a3: the a2 alpha full app could not compile.

2. **Iframe popup return after an anonymous protected event.** In the default
   scope configuration, press Reveal anonymously inside `/iframe`, authenticate
   Alice in the popup, and wait for it to close. The child receives the app's
   `post_auth_generic` message but remains on `/login?redirect_to=%2F`; pending
   event storage remains. Three focused repeats fail after an extra ten seconds.
   Navigating the same child to `/` replays the protected event and consumes
   storage in all three repeats. Ordinary pending replay and direct iframe login
   pass; the combined extra-scope case also passes. The enhanced default-scope
   driver also fails this combined case on stable Reflex 0.9.12 (3/4 overall),
   with the same child URL and pending event. This is shared with stable rather
   than an alpha-only regression; no a2 baseline exists for the new combination.

3. **Production MCP URL boundary.** The documented/default
   `POST /_reflex/mcp` returns 405 on the public full-stack production server,
   for missing or fabricated bearer credentials. Dev redirects to the expected
   authentication response. Explicit `POST /_reflex/mcp/` returns 401 and permits
   the authenticated session tests. A minimal public-CLI comparison reproduces
   the same 405/401 boundary on a2 and a3 with otherwise identical alpha graphs.
   This is preexisting in the tested a2/core-alpha combination. The trailing
   slash is a diagnostic variant, not a fix or a passing default-route result.

Historical finding 11 also persists: rejected production/export credentials
block the operation but exit 0. No new issues or external comments were filed
during this rerun; the user's earlier disposition remains in issue triage.

## Evidence and reproduction

- [Alpha auth report](auth-alpha/REPORT.md): full/minimal apps, local OIDC
  provider, field/scope/logout repros, repeat drivers, OAuth and anonymous MCP.
- [Stable and independent controls](auth-stable/README.md): full auth suite,
  repeated public reloads and the small identical-source alpha/stable probe.
- [Components and routing report](components/REPORT.md): all grid/map flows,
  real public production account fixture and isolated a2/a3 MCP wire comparison.
- [Cookie app and driver](cookies/REPORT.md): same app on both production graphs.
- [Free-tier matrix](free_tier/REPORT.md): real SDK/local API and public CLI.

Install a lane's exact frozen requirements into a fresh environment using
`uv --no-config pip install --python <venv>/bin/python --index-url
https://pypi.org/simple -r <requirements>`. Copy only the saved sample source to
a neutral app directory; exclude generated `.web`, state files and caches.
Use the lane's startup/driver commands with `env -u PYTHONPATH` and
`uv --no-config run --no-project --python <venv>/bin/python`. No repository
dependency synchronization is needed or permitted for this validation.

## Diagnostic limits

Unlicensed AG Grid trial messages are expected and retained: dev grid/maps
210/28 console lines and production 105/14. Grid has no failed requests, page
exceptions or HTTP errors. Map navigation records 32 dev and 29 production
aborted tile requests, without unexpected console or HTTP errors. Cookie runs
each record 15 successful sync responses and 15 aborted-request notifications;
values and headers pass but the request log is not wholly clean. Published
cookie code emits a `fix_events` deprecation warning. Auth navigation can also
abort cookie synchronization requests. Detailed raw diagnostics remain in each
report; pass counts alone do not replace diagnostic review.
Stable cookie output additionally has twelve string-assignment field-type
warnings; alpha has none. The cookie abort cause is unresolved: read-only
published-source inspection found no explicit abort signal. Those fifteen
notifications per run cannot all be attributed to the single reload.

The Free-tier frontend-only development export records three console WebSocket
connection failures because no backend is running for that static preview.
Its counter is asserted only on the real production-server cases. The inherited
Free-tier browser helper checks page exceptions but does not enforce its console
log or capture HTTP/request failures. Its socket audit covers Python, excluding
Bun/browser traffic. Actual guard contexts, SDK requests and CLI output were
manually reviewed; these driver limits remain for a requested followup.

The production component account fixture uses fictional paid responses to the
official SDK's local HTTP endpoint, with guards active. The Free-tier lane uses
fictional Free/paid/rejected responses. Actual cloud entitlements/deployment,
external IdPs, Windows, HTTPS/partitioned cookies, multiple production workers,
all map/grid modes and prolonged load remain unverified. Auth suites run in
development; cookie/grid/map/Free-tier lanes supply production coverage.
Non-enterprise prerelease findings were not rerun or reclassified by this task.

[Adversarial artifact review](REVIEW.md) lists the reusable-driver limitations
left for followup. Syntax/evidence/link audits and published-Ruff checks are
saved under `validation/`; framework coverage, checkout Pyright and stub
regeneration were not run for this published-package testing task.
