# Combined payload release-blocker reassessment

Target the original monorepo/tooling alpha manifest plus published enterprise
0.9.7a4. Fresh isolated UV environments install published PyPI packages only;
copy sample source into neutral temporary directories and record exact graphs,
import origins and absence of editable/direct-URL installs. Never install/run
the framework from a branch or checkout. Preserve previous evidence; no fixes.

Apply the user's gate: a blocker is newly introduced, critical in severity, or
a demonstrably weak security issue that must be resolved before release. Do
not relabel a noncritical preexisting defect as a blocker solely because it is
still open. The known MCP trailing-slash problem is explicitly deferred.

Parallel Sol 6.1 Extra High lanes:

1. Auth: full browser suite, field/scope metadata, public async-value and iframe
   pending-event fixes, OAuth/MCP replay/refresh/redaction. Ports3132/8132/9131.
2. Security: independent application-level logout/reset faults, subsequent
   anonymous/protected actions and cross-user session boundaries; legitimate
   auth/MCP wire probes. Ports3152/8152/9151. Only confirmed disclosure/mutation
   or policy weakness counts as a security finding; ordinary errors alone do not.
3. Components/core review: dev/prod grid/maps/storage/fonts, anonymous MCP,
   independent reassessment of prior nonenterprise findings and reports.
   Ports3131/8131.
4. Root: publication/combined inventory integrity, cookie and Free-tier checks,
   narrower stable/alpha large-State comparison, aggregate gate and review.
   Ports3144/3145/3146 as needed, never concurrently reused.

Reuse original core/tooling/upgrade results only where the published versions
and bytes are unchanged; identify reused coverage separately from new runs.
If a new candidate emerges, preserve a minimal real-browser/wire reproduction
and compare the relevant published baseline. Do not file/comment new issues
without further authorization. Stop owned services, audit source/evidence,
commit reusable artifacts and publish to the existing testing branch.
