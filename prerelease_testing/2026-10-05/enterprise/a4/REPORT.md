# Combined prerelease gate after enterprise 0.9.7a4

**HOLD: two blockers remain: enterprise #245's demonstrated security weakness,
and newly introduced mixed-version Redis persistence loss.** The two reported
a3 authentication failures now pass. No other new or critical blocker was
established by the reassessment. The outstanding MCP URL
trailing-slash issue is explicitly deferred to the next release by the user.

This gate follows the user's definition: a blocker is newly introduced, critical
in severity, or demonstrably weak security requiring a pre-release fix. An open
noncritical preexisting issue alone does not satisfy the gate. See the
[machine-readable disposition](release-gate.json), [plan](PLAN.md) and retained
[reference PR/issue descriptions](reference-prs-and-issues.json).

## Security blocker and patch direction

The defensive validation confirms a confidential-state isolation gap when
application default factories fail during logout cleanup. Protected state can
survive an account change on the same Reflex client session. Both frontend and
backend state cases show this; ordinary successful logout clears them. This
is sufficient to hold release under the security criterion, even though its
introducing version is not established. It is tracked in the already-open
[enterprise #245](https://github.com/reflex-dev/reflex-enterprise/issues/245).

The completed handoff cleared browser cookies and restored the app dependency
before the next ordinary OIDC login. A fresh page and independently reviewed
observations establish data re-delivery beyond stale DOM. A handoff without
that intervention and an older baseline were not completed. Anonymous protected
actions remained denied; no anonymous authorization bypass is claimed. The
[defensive report](security/REPORT.md) and [independent review](security/REVIEW.md)
retain the evidence and exact limits; this report intentionally omits exploit
instructions.

Recommended patch requirements:

1. Revoke provider/local authentication, normalized identity and auth cookies
   reliably even if application reset/default-factory/state-load work raises.
   Keep an explicit failure signal; a partial cleanup must not report success.
2. On failed cleanup, discard, invalidate or quarantine the affected client
   State tree and its protected frontend/backend/computed caches before another
   identity can use it. Clearing cookies or continuing the other State resets
   alone does not establish confidentiality. The next authenticated session
   must get newly constructed state or a verified reset, not the failed tree.
3. Add regression checks for frontend/backend factory failures, reset/load
   failures, cookie synchronization failure, and subsequent account change on
   the same client. Verify old data is absent, anonymous actions remain denied,
   and recovery cannot restore access to quarantined state. Validate supported
   state managers and browser/API/MCP surfaces sharing that session boundary.

These are patch requirements, not a prescribed untested implementation. No
framework fix or new external issue/comment was made in this task.

## Newly introduced rolling-upgrade blocker

Fresh real-Redis controls confirm backend-list mutations persist for both
stable-only and alpha-only workers, but are silently lost when an old worker
reads state saved by the alpha. The old worker mutates its in-memory value;
the stored state remains unchanged and the next fresh reader sees the old value.
Nine fresh worker processes run the identical app source with isolated published
graphs, and all owned Redis keys/services are cleaned afterward.
[The controlled report](rolling/REPORT.md) retains provenance, source,
dirty-state/snapshot observations, pickle hashes and all three comparisons.

The #7312 changelog explicitly describes this exception. It is nevertheless
newly introduced loss of previously working persistence during rolling upgrades,
and the user's criterion does not waive documented regressions. It is finding
16 and a release blocker independently of the security issue. The patch should
restore backward-compatible mutable-backend tracking for old workers reading
new State, then verify stable-only, mixed and alpha-only persistence with fresh
workers. Avoiding worker-version overlap or replacing whole values mitigates
the rollout exposure but is not a validated framework repair.

## Payload, isolation and coverage

The target is the original core/tooling alpha manifest plus enterprise a4:
Reflex/base and announced component/docgen releases 0.10.0a1, hosting CLI
0.1.73a1, release tooling 0.1.2a1 and enterprise 0.9.7a4. All 13 original
core/tooling alpha wheel/sdist filenames and hashes remain unchanged and none
are yanked, verified against live PyPI metadata in
[unchanged-core-tooling.json](unchanged-core-tooling.json). Their original broad
core, uploads, Redis, migration, lifecycle, components, example upgrades and
tooling results are reused, rather than claimed freshly rerun.

The [a4 publication audit](publication.json) verifies both downloaded archives
against PyPI SHA256 and matching names/content for 39 stubs, with no unexpected
generated artifacts or direct-URL references. New installations use exact
104-package alpha and 91-package stable graphs from published PyPI packages:
[alpha lock](requirements-alpha-lock.txt), [stable lock](requirements-stable-lock.txt),
[alpha pip check](pip-check-alpha.log), [stable pip check](pip-check-stable.log).
Each differs from its a3 counterpart only by enterprise a3→a4. Fresh sample apps
run from neutral temporary directories; framework origins resolve inside the
isolated environments. No source/editable/checkout installation or framework
patch occurred. Root installs initially hit restricted-network DNS failure;
the same authorized PyPI installs succeeded with network access. Some agent
caches initially predated a4; explicit package metadata refresh resolved that.

Parallel Sol 6.1 Extra High lanes ran actual public CLI/browser/wire checks with
Bun 1.4.2 and Playwright 1.55/Chromium 140, preserving server and browser/network
diagnostics. Auth uses a fictional local OIDC provider. Production entitlement
checks use official SDK HTTP against a fictional loopback account API, with
CI/harness/offline bypasses absent. No real cloud account/provider was modified.

| Fresh check | Result and evidence |
| --- | --- |
| Auth fields and OIDC extra-scope setup | Pass; previous a2 blockers remain resolved |
| Retained full auth browser matrix | 22/22, versus a3 21/22 |
| Default/extra-scope enhanced flows | 4/4 each, including clean logout/account change |
| Public navigation plus two successive reloads | 3/3 fresh contexts pass |
| Default iframe pending replay | 3/3 automatic return/replay/storage consumption |
| OAuth/anonymous MCP | Consent, protected reads, code/refresh replay rejection, ordinary isolation/redaction pass; [auth report](auth/REPORT.md) |
| HTTP-only cookies on alpha/stable | 6/6 scenario groups each; [cookie report](cookies/REPORT.md) |
| Free-tier public production/export matrix | 8/8, ten account HTTP requests, 33 active-guard contexts; [Free-tier report](free_tier/REPORT.md) |
| Enterprise grid/maps/storage/fonts | 15 grid plus 7 map/storage/font cases pass in each of dev/prod; [component evidence](components/REPORT.md) |
| PR #251 formatter demo recipe | Inline/State/API renderer cases 3/3 in each mode; full export archive/bundle integrity passes; [export evidence](components/results-summary.json) |
| Bounded core scale comparison | Alpha works at 1,200 where stable fails; both fail at 1,300; [scale report](scale/REPORT.md) |
| Fresh rolling-upgrade Redis controls | Stable-only and alpha-only persist; mixed workers lose backend mutation; [rolling report](rolling/REPORT.md) |
| Exceptional logout cleanup | Confidential-state isolation fails; security release blocker |

## Remaining nonblockers and review limits

Historical findings 1–3 and 12–13 are resolved by the observed a4 runs. Findings
5–7 reproduce on the stable baseline; 8 is a messaging/documentation boundary;
9–10 are user-ignored and do not demonstrate working stable functionality newly
broken by alpha. Finding 11 still returns exit 0 for denied enterprise CLI
operations, but blocks startup/export; it is preexisting and no entitlement
bypass is shown. PR #250 is the separate proposed exit-status fix. Finding 14
is user-deferred and also reproduces on stable. Their original evidence remains
in [FINDINGS.md](../../FINDINGS.md).

Finding 4 is a real State-scale limitation, but fresh stable builds now expose
the same failure class at 1,200/1,300. A separate ordinary-root probe confirms
stable's 1,300 React stack overflow independently of its known dynamic-route
404. No tested working stable app newly fails on the alpha; thresholds across
all browsers/topologies are not established. It is not critical severity in
this bounded dormant-State app and no security weakness is demonstrated.

Cookie `net::ERR_ABORTED` notifications persist in otherwise successful stable
and alpha flows; their cause is unresolved and they were not discarded. The
component runs also retain expected missing-enterprise-license console errors
and map-tile aborts during movement; their reports classify these explicitly.
The retained drivers vary in which metrics they enforce. Reports disclose those
limits; a pass flag alone is insufficient. The security lane's partial extra
MCP checks do not establish uncompleted session-claim comparisons. Real IdPs,
production authentication, Redis/multi-process exceptional logout, HTTPS cookie
settings, Windows behavior, real cloud entitlements and long-duration load are
not comprehensively validated by these local runs.

The [adversarial artifact review](REVIEW.md) records concrete driver limitations.
Owned services are stopped and cleanup evidence is retained. Reusable apps,
drivers, exact graphs and raw results are committed to the existing testing
branch. The release should remain held until #245's fail-closed recovery and
the rolling-upgrade persistence regression are patched and revalidated; this
testing task does not implement either patch.
