# Published prerelease exploration — October 5, 2026

**Latest enterprise rerun: 0.9.7a3 resolves the three a2 auth blockers, but
validation is not fully passing.** The full auth browser suite passes 21/22 on
Reflex 0.10.0a1 and 22/22 on stable. An independently reproduced protected async
value fails on public-page navigation/reload with the alpha; stable passes.
Grid/maps, cookie scenarios and the Free-tier matrix pass. Embedded pending
login and production MCP routing have additional recorded limits.
See the [a3 report and reusable repros](enterprise/a3/REPORT.md).

The initial 0.9.7a2 campaign below found broken auth fields, extra OIDC scopes
and logout with Reflex 0.10.0a1; the same a2 wheel worked with Reflex 0.9.12.
That evidence is retained. [Numbered findings and exact repros](FINDINGS.md)
distinguish resolved blockers, remaining compatibility failures and older defects.

[Issue triage](issue-triage/README.md) records the user-supplied enterprise
references, filed issues for findings 4–8, and the instruction to ignore 9–10.

All 14 announced alphas have published PyPI wheels and sdists. Their downloaded
bytes match PyPI SHA256 digests. Wheel and sdist `.pyi` names/content match;
monorepo alpha stub names match the release source manifest. No checked-out
package, editable install or branch build was installed or executed as the
framework. Source refs, changelogs, PR descriptions and demos were read as
reference material; every running framework came from isolated PyPI installs.
The superseded enterprise 0.9.7a1 cut from this same batch is also published and
archive-audited in `inventory/superseded-enterprise-alpha.json`; install/test
pins use its requested successor, 0.9.7a2. The enterprise source/changelog is
pinned at `40aa7b33af419a6dc354e33873f6cd1270d28205` under `enterprise/reference/`.

The campaign used parallel Sol 6.1 agents at Extra High effort. Actual browser
tests ran in dev and prod where applicable, with browser console/page/network
capture, server logs, local OIDC/MCP HTTP services, real Redis, SQLite migrations
and prior-stable upgrade comparisons. No framework fixes were attempted.

## Release inventory

| Published alpha | Version |
| --- | --- |
| reflex, reflex-base | 0.10.0a1 |
| reflex-components-code/core/gridjs/markdown/moment/plotly/radix/recharts | 0.10.0a1 each |
| reflex-docgen | 0.10.0a1 |
| reflex-hosting-cli | 0.1.73a1 |
| reflex-release | 0.1.2a1 |
| reflex-enterprise | 0.9.7a2 initially; follow-up 0.9.7a3 |

The six other branch changelog heads describe unchanged stable releases. See
[every changelog head](inventory/changelog-heads.md),
[PyPI metadata/archive audit](inventory/inventory.json),
[stub manifest audit](inventory/manifest-audit.json),
[exact alpha pins](inventory/alpha-requirements.txt) and
[linked issue/PR descriptions](inventory/linked-descriptions.json).
The main and tooling refs are independently recorded with their commit IDs.
The follow-up a3 [publication audit](enterprise/a3/publication.json) independently
verifies its PyPI wheel/sdist hashes and matching stubs.
The migration fragment links to unrelated issue #6706; its implementing PR is
#6770, whose description is separately saved under `tooling/reference/`.

## Results by exploration

| Exploration | Outcome and reusable report |
| --- | --- |
| Enterprise a3 follow-up: auth, cookies, grid/maps, OAuth/anonymous MCP and Free-tier guards | Three a2 blockers resolved; async public reload and additional limits remain; [a3 report](enterprise/a3/REPORT.md) |
| State descriptors, shadowing, inherited events/background mutation, ABC, mode guards, contexts, memo/ComponentState/client State, shared/private state, deep equality, slicing, download and event recovery | 71 browser assertions in each of dev/prod plus backend checks; [core report](core_state/README.md) |
| Buffered/chunked uploads, HTTP event streams, concurrent clients/uploads, disconnect/navigation cancellation, recovery after response closure and actual OTel lineage | All seven scenarios in each mode, with 25 visible assertions plus timing/transport/span checks; [upload report](core_state/upload/README.md) |
| Redis application state corruption/recovery, concurrent contexts, inherited background values and lock notification race; DB-extra guidance and SQLAlchemy-only migrations | Seven browser scenarios/79 value assertions, four lock scenarios and four actual cross-version Redis scenarios pass; [Redis and DB report](core_state/redis/README.md) |
| Duration migration and Redis pool contention/timeouts | Pass; [services report](services/README.md) |
| Callable datetime/UUID defaults in actual schema migrations | Ordinary alpha cases pass; unique UUID backfill of two existing rows still fails; stable reproduces original CompileErrors; [migration report](services/README.md) |
| Forms/memoization, State-based match, charts, Shiki, Markdown, data editor, upload, media, Moment, Radix and toast | Final prod 12/14 scenario groups pass; two older wrapper defects remain; initial Grid.js console anomaly could not be reproduced; [component report](components/REPORT.md) |
| AG Grid 36.2, integrated charts, editing/selection/download, HTTP datasources, saved state, Leaflet maps and Google font helper | Pass across 15 grid cases plus map/storage checks; [enterprise report](enterprise/REPORT.md) |
| OIDC login/profile/protected event replay/iframe popup and MCP OAuth/PKCE/refresh/replay/redaction | Most flows pass; fields, extra scopes and logout fail; [enterprise repros](enterprise/REPORT.md) |
| Enterprise a2 Free-tier production/export permissions and enforced badge, paid badge-off control and rejected credentials | Eight public CLI cases pass against a local account API with CI/harness flags absent; rejected operations return exit 0; [Free-tier report](enterprise/free_tier/REPORT.md) |
| Real browser upgrade of unmodified Todo, Overkey and basic_crud examples, preserving frontend/data then cold rebuilding | Main flows pass; Overkey's reset defect is preexisting; [Todo report](upgrades/README.md), [other upgrades](components/upgrades/REPORT.md) |
| Self-hosted dynamic routes, query/header named self, path prefix, compression, CSS hot reload, package formatting cache, JSON supervision and process shutdown | Pass; [runtime report](lifecycle/README.md) |
| 500/1,000/1,500 dormant States | Both versions pass 500/1,000; alpha browser fails at 1,500; stable build blocked at 1,500; [controlled comparison](enterprise/many_states/REPORT.md) |
| Release dispatch input boundary, docgen BOM/whitespace/CRLF parsing, hosting SDK/CLI JSON/error/auth contracts and ty event callbacks | [tooling report](tooling/README.md) |

Browser screenshots and raw diagnostics accompany the reports. No unexpected
backend errors were discarded. Expected failures, controlled test exceptions,
old-browser version mismatches, missing test favicons, local mock-provider
artifacts and fixture-authoring corrections are identified in the relevant
reports. A combined shell log can contain a warning from the `uv` wrapper;
the JSON audit records that separately from Reflex output.

## Isolation and repeating the campaign

Create fresh environments outside the checkout. Exact example commands:

```sh
uv --no-config venv --python 3.12 /private/tmp/reflex-next-alpha
uv --no-config pip install --python /private/tmp/reflex-next-alpha/bin/python --index-url https://pypi.org/simple -r /absolute/path/to/inventory/alpha-requirements.txt
uv --no-config pip install --python /private/tmp/reflex-next-alpha/bin/python --index-url https://pypi.org/simple 'reflex[db]==0.10.0a1' 'reflex-enterprise[mcp]==0.9.7a2' playwright
```

Copy only the sample app into a neutral directory and run there with
`env -u PYTHONPATH ... uv --no-config run --no-project --python <venv>/bin/python`.
Do not use repository `uv sync`, source installs, editable installs or a
workspace interpreter. Each cluster provides app/start/driver commands and its
tested dependency graph. Use those frozen graphs when reproducing a specific
finding; the broad `--prerelease allow` resolver can also choose prerelease
transitive dependencies. The root graph selected Pydantic 2.14.0b2; stable
comparison environments and independent auth-field repros are recorded.

`provenance.py` records executable, site-packages origins, graph and absence of
direct-URL/editable installs. `inventory.py --repo <read-only repo> --output
<directory>` accepts alternate release refs and enterprise versions.
`catalog_prs.py` saves linked descriptions. Drivers retain expected failures
instead of substituting framework workarounds.

## Limits and adversarial review

This campaign establishes the observed behavior on macOS with Playwright
Chromium/native Chrome and the Codex in-app browser (engine unspecified); it is not
exhaustive acceptance or a performance benchmark. Windows socket-handle fixes,
actual paid/free cloud entitlements and deployed badge enforcement, external
IdPs and remote collectors, every enterprise grid/map mode, unsupported Node
preflight/npm switching, and long-running production load remain unverified.
Editable-install stub preservation was intentionally not exercised because the
task forbids installing the checkout. PostgreSQL migrations were not run.
The public Free-tier production/export guard and local badge behavior were
exercised with mocked account responses; no real cloud entitlement was used.
Cross-version serialized-state details are documented in the Redis report.
The default runtime accepted existing Bun 1.4.0, its supported minimum. A fresh
isolated install of the announced Bun 1.4.2 also builds the 1,500-State sample;
native Chrome still reproduces its blank page and stack overflow.

Publication merges the existing September testing history before adding this
campaign, so prior artifacts remain available on the requested branch. Git SSH
authentication was unavailable; authenticated HTTPS via the existing GitHub CLI
credentials provides the publication path. No real cloud account or identity
provider was modified. Temporary environments remain available for reruns;
owned app servers and local fixtures are stopped at completion.

Review identified the numbered issues in `FINDINGS.md`; release owners must
decide their followup. No issue was fixed during testing. Framework unit tests,
coverage, Pyright and stub regeneration were not run against the checkout.
Validation targets the reusable campaign sources, syntax, evidence, import
origins and real behaviors using published tools and distributions.
The [independent artifact review](REVIEW.md) also identifies four reusable-driver
limitations for followup. Current raw diagnostics were manually checked and
are preserved; a driver's pass flag alone must not be treated as acceptance.
