# Browser cache and payload follow-up (complete)

Owner: `codex-macos-pass2-01a11520`, macOS arm64. Claimed after the user requested deeper release diligence. The coordinator won the `events` claim race; this item does not duplicate that suite.

All runtime tests use published PyPI environments in `/private/tmp/reflex-prerelease-macos-pass2/envs`; the checkout is never installed/imported. Exact original environment freezes and bootstrap are in `../dataeditor/de/`, with current exact graphs in the subdirectories. Each subdirectory records its final rerun instructions. The structured aggregate report is `../board/results/browser_cache_bundle.md`; findings are in the three corresponding inbox files.

- `bundle/`: same modular production app on stable/a1/a2, actual browser cold/warm navigation payloads plus static raw/gzip asset sizes; optional lazy-library setting. Ports 3700–3709 / 8700–8709.
- `reload_cache/`: retained `.web`, imported-module edits, memo bodies/defaults/styles/events, dependency addition/removal, package formatting-only changes, warm restarts and production rebuilds. Ports 3710–3719 / 8710–8719.
- `state_cache/`: realistic nested order/inventory state, cached/uncached/transitive values, mutations through iteration/aliases, background updates and session isolation. Ports 3720–3729 / 8720–8729.
- `deploy_cache/`: old exported frontend assets against backend defaults and state-schema changes, backend-only production workers, Unicode/space project paths, browser history, persistent settings and factory defaults. Ports 3730/8730.

We do not make wall-clock performance claims while other agents are active. Static bundle bytes, actual HTTP transfer bytes, and websocket JSON payload bytes are separate measurements. Current release blockers elsewhere remain relevant: this cluster cannot establish whole-train readiness on its own.

Completed conclusions: no new 0.10 regression established in this scope. Alpha2 modular routes load heavy features on demand and warm route returns transfer no new content. Cold landing HTTP transfer rises about2.9% vs stable while initial received websocket application payload drops about79%; alpha1→alpha2 HTTP payload is effectively unchanged. Memo output, styles, events, hook artifacts, defaults and package changes update correctly through development reloads and production rebuilds.

Two reproducible pre-existing weaknesses remain: nested dictionary-view mutations bypass dirty/cache invalidation (independently confirmed with a second realistic inventory app), and npm still reinstalls packages on source-only edits because absence of an empty devDependencies object defeats the semantic comparison. Bun demonstrates the intended install-cache improvement. Both alphas fix the inherited-background state mutation failure reproduced on stable.

Old static assets correctly receive changed backend defaults and keep working across same-schema upgrades. Adding a new backend state with old frontend assets fails consistently on every train; a matching rebuild passes. Ordinary history navigation/reconnect passes; actual BFCache restoration was not observed and remains unverified. A pure externally supplied cache=False inventory control passes40 comparisons and does not justify broadening coordinator N-016 beyond its demonstrated side-effectful case.

Full logs/console/network/websocket records are retained, largely gzip-compressed; each subtree documents canceled-request, driver-focus/protocol, HMR hook-error, or warning anomalies without counting them as new regressions. All owned browser/cache servers, browser instances and process groups were cleaned up. Parent reviewed the evidence and harnesses, corrected result-exit propagation where needed, and ran fatal Ruff checks, isolated formatting and Git whitespace checks. No framework source changed. Timing claims are deferred to the separate claimed statemgr_perf item.

An initial deployment fixture put a random default in the same state as deterministic defaults (forcing full-state fallback), and its same-origin help link used SPA navigation. It was discarded as insufficient coverage. The final fixture separates the random state, asserts a real external help document, and captures history restore type. It does not call ordinary back/forward navigation a BFCache restoration unless `pageshow.persisted` is true.
