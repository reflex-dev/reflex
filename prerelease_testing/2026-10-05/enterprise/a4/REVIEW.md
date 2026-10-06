# Adversarial review of the a4 release-gate artifacts

The release conclusion is HOLD for one conditional confidentiality gap in
enterprise #245, freshly reproduced on the published a4 wheel. Mixed-version
workers/downgrades are now explicitly unsupported under the maintainer's policy
and no longer block release. Source fixes were not attempted.
An independent auth agent reviewed the logout evidence and installed cleanup
code; the root reviewed raw classifications and the assembled reports.

1. **Security evidence is conditional and now refreshed.** A completely fresh
   published-a4 installation matches all 157 enterprise wheel files. The new
   ordinary control and two factory-failure cases each run once, with app
   dependency recovery before login and **no manual cookie clearing**. A checked
   new identity, explicit reload, visually reviewed screenshots and independent
   action log support retained-data disclosure. Anonymous mutations remain
   denied. Do not label this an anonymous bypass, universal account-switch
   failure or newly introduced a4 regression. The root-reviewed
   [fresh report](logout-recheck/REPORT.md) supersedes the older intervention
   limitation; [the earlier independent review](security/REVIEW.md) is preserved
   as historical evidence, not represented as reviewing this new run.
2. **The extra security MCP driver did not complete.** It assumed an MCP
   transport-session identifier that the SDK did not return. Some negative
   checks completed; the cross-bearer comparison and final Bob SDK read did not.
   The partial JSON/failure log and report preserve this distinction. Ordinary
   MCP isolation/replay/redaction passes come from the separate completed auth
   and component lanes, not the incomplete driver.
3. **Scale observer exit/status and screenshots require interpretation.** It
   intentionally exits 0 after observing failing cases; per-case JSON is
   authoritative. Appending runs overwrites a graph-level summary. Screenshots
   follow fallback root navigation, so they are not necessarily the original
   failed dynamic page. The first observer stopped assertions on stable's known
   direct-route 404; a later stable root-route control independently confirms
   React overflow. Exact executed observers are retained alongside the formatted
   reusable helper. No precise universal threshold is inferred.
4. **Retained browser drivers have incomplete gates.** Cookie failures are
   recorded rather than all rejected; some screenshots precede JSON saving;
   focused auth observation drivers can return zero with false JSON booleans;
   OAuth success does not substitute for a wrong-verifier rejection test. The
   current per-case fields were inspected. The iframe fixture's idempotent event
   does not prove exactly-once invocation or force the PR's deterministic race.
   Free-tier socket/denial/path-check limits are unchanged and documented.
5. **Expected errors are present.** License diagnostics and moving map-tile
   aborts are retained. Cookie abort causes are unresolved. Missing or unobserved
   metrics are not silently turned into zeros. Standalone I001 import-order
   diagnostics in retained helper files are harness formatting issues, not
   package failures; no reviewed historical driver was repaired here.
6. **Coverage reuse is explicit.** Live PyPI metadata verifies the 13 original
   core/tooling alpha archive hashes remain unchanged and not yanked. Their broad
   historical browser, Redis, migration, upgrade and tooling results are reused.
   The a4 fresh runs do not establish every IdP, platform, state manager, cloud
   entitlement, production auth or sustained load path. CI bypass is disclosed
   for ordinary auth/root samples; entitlement guards are active in the separate
   production/export matrix.
7. **The maintainer's support policy changes the Redis disposition.** Fresh
   stable-only and alpha-only controls pass while alpha→stable→alpha loses the
   update. The maintainer explicitly says mixed versions and downgrades are
   unsupported across the minor state-format change. Finding 16 is now an
   expected unsupported configuration, not a release blocker. Its sealed
   historical report remains intact, with [a superseding disposition](rolling/DISPOSITION.md).

Validation parses saved Python/JSON/JSONL, checks local report links, source
manifests and generated-file exclusions, and runs published Ruff on the sources.
New root helpers pass focused lint/format checks. Full checkout unit tests,
coverage, Pyright and stub generation are inapplicable to this no-fix,
published-package validation and were not run. No worktree framework source,
installed package or generated browser asset was patched. Numbered limitations
remain visible for follow-up; this task stops after testing/report publication.
