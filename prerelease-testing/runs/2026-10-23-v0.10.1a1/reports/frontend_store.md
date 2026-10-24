# frontend_store — agent report (summary)

No regression. Every targeted fix reproduces as broken on 0.10.0 (positive controls) and works on 0.10.1a1.
Findings (both low, not regressions):
- FS-1 Removing a configured TailwindV4Plugin leaves a stale `.web/postcss.config.js` referencing the pruned
  `@tailwindcss/postcss` → vite overlay on every page until `.web` is deleted (same on 0.10.0).
- FS-2 React Compiler (`react_compiler=True`) silently skips every component that renders an element with `id=`
  (hoisted `refs["ref_x"] = ...` → "This value cannot be modified" / "Cannot access refs during render"), so page route
  modules are never compiled (0 `_c(` in routes; app_components compiled). Docs claim it covers `app/` JSX. Experimental flag.

Passed: #7273 48 structural-sharing ops DOM == State.dict() (dev, prod, compiler on/off); unchanged memo cards no longer
re-render. #7441 substates / ComponentState / memo / client_state / dynamic routes; 1500 substates render (0.10.0: stack
overflow); StateContexts removal breaks no published package (rxe imports only ColorModeContext). #7586 hook order fixed
(0.10.0: ReferenceError) with deprecation warning for `VarData(position=)`. #7553 schema hash: no false mismatches
(export + backend-only, restart, 3 forked/spawned workers, default-only change); real skew → one reload then banner,
no loop. #7435 unknown substate skipped once per connection. #7645 package.json diff exactly the 4 bumps. #7565, #7518,
#7573, #7405, #7544, #7587 all fixed vs 0.10.0.
Re-verified: reflex#7429 fixed, #7247/#7435 fixed, #7407 fixed.
Not covered: data_editor/plotly under structural sharing, mixed-version load balancer, cooldown-expiry second swap.
