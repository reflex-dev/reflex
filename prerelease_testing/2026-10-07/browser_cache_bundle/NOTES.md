# Browser cache and payload follow-up (in progress)

Owner: `codex-macos-pass2-01a11520`, macOS arm64. Claimed after the user requested deeper release diligence. The coordinator won the `events` claim race; this item does not duplicate that suite.

All runtime tests use published PyPI environments in `/private/tmp/reflex-prerelease-macos-pass2/envs`; the checkout is never installed/imported. Exact original environment freezes and bootstrap are in `../dataeditor/de/`. Each subdirectory records its own final rerun instructions. Findings here are provisional until baselined and independently checked.

- `bundle/`: same modular production app on stable/a1/a2, actual browser cold/warm navigation payloads plus static raw/gzip asset sizes; optional lazy-library setting. Ports 3700–3709 / 8700–8709.
- `reload_cache/`: retained `.web`, imported-module edits, memo bodies/defaults/styles/events, dependency addition/removal, package formatting-only changes, warm restarts and production rebuilds. Ports 3710–3719 / 8710–8719.
- `state_cache/`: realistic nested order/inventory state, cached/uncached/transitive values, mutations through iteration/aliases, background updates and session isolation. Ports 3720–3729 / 8720–8729.
- `deploy_cache/`: old exported frontend assets against backend defaults and state-schema changes, backend-only production workers, Unicode/space project paths, browser history, persistent settings and factory defaults. Ports 3730/8730.

We do not make wall-clock performance claims while other agents are active. Static bundle bytes, actual HTTP transfer bytes, and websocket JSON payload bytes are separate measurements. Current release blockers elsewhere remain relevant: this cluster cannot establish whole-train readiness on its own.

Interim observations: alpha2 modular routes load heavy features on demand and warm route returns transfer no new content; alpha2 reload/cache sequence passes in both browser engines. A nested `dict.values()`/`items()` mutation dirty-tracking lead is being compared with stable. Adding an entirely new backend state while serving an old frontend causes an explicit state-mismatch console error; unchanged schemas with changed defaults have passed. Baselines and matching-build controls are pending.

An initial deployment fixture put a random default in the same state as deterministic defaults (forcing full-state fallback), and its same-origin help link used SPA navigation. It was discarded as insufficient coverage. The final fixture separates the random state, asserts a real external help document, and captures history restore type. It does not call ordinary back/forward navigation a BFCache restoration unless `pageshow.persisted` is true.
