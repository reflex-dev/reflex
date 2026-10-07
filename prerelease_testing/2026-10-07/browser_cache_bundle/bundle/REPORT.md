CLUSTER: browser_cache_bundle / bundle
SUMMARY: Same modular production app tested on all three published graphs, default/lazy-library configurations, Chromium and WebKit. No material bundle/cache regression or functional release blocker found. Default alpha2 cold HTTP transfer increases9,282 bytes vs stable (+2.9%) while initial websocket application payload drops9,446→2,011 bytes; alpha1→alpha2 HTTP difference is2 bytes. All distinct functional journeys pass after two documented focus-driver rechecks.
ARTIFACTS: prerelease_testing/2026-10-07/browser_cache_bundle/bundle/ (NOTES.md, comparison.json, source/scripts, exact freezes, full compressed evidence), ~2.4MB.
TESTS:
- [pass]6 production graphs ×2 engines: landing/reload, dashboard event, chart navigation/update, editor/code load/edit, cached home/chart revisit and state preservation.
- [pass] Actual gzip serving; ETag/Last-Modified revalidation/cache reuse; warm client revisits0 transferred resource bytes.
- [pass] Heavy Plotly/editor code defers to respective routes, not cold home. Default initial RT321,627 stable vs330,907 alpha vs330,909 alpha2; whole-build raw JS6.44–6.48MB is explicitly separate.
- [pass] Small task121-byte reply, chart6,824-byte reply and catalog223-byte reply identical across trains; initial unchanged-default websocket payload is reduced in alphas.
- [anomaly] Optional lazy-library setting increases this ordinary app's cold payload~5.4KB but works correctly; not claimed as a regression or universal optimization result.
- [anomaly] Two immediate-click/Enter WebKit driver timeouts; both full rechecks pass with250ms focus settlement. Original evidence retained.
- [anomaly] Stable-only tuple position transformation warning falls back successfully; absent on alphas. Existing theme API deprecation and build peer/chunk warnings documented.
REVERIFIED: No existing numbered finding assigned.
ISSUES: None warranting release findings. No timing claims, no framework changes.
NOT_COVERED: CDN/proxy caching, stale tabs/rebuild invalidation, direct cold heavy-route entry, multi-user state isolation, Safari application behavior; separate workstreams.
