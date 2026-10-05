# rv_render_state — render_ctx_statemgr + memo_aschild regression sweep on 0.9.12a2 (the fixes touched deltas, metaclass, app wraps)
Ports: frontend 3180-3199 / backend 8180-8199 (redis: 8199). Scratch: $SB/reverify/rv_render_state/. Notes dir: reverify-0.9.12a2/rv_render_state/.
Venv under test: `$SB/envs/a2`; baseline `envs/prev`; a1 `envs/shared`. Campaign material: `render_ctx_statemgr/`
(renderapp, diskapp, drivers, `## VERIFICATION`), `memo_aschild/` (its app, drivers, `verification/`).

Checks:
1. `render_ctx_statemgr/renderapp` render-count suite on a2 dev (memory): the A/B/dual on_load counts halved by #6181
   must match the campaign's a1 numbers; every other scenario unchanged; prod replays with half the dev counts
   (StrictMode) — run prod once. Zero console errors.
2. StateManagerDisk probes (`diskapp`, `#7159`): debounced flush of the latest instance, `modify_state` from an API
   route persists, state survives a hot reload, shutdown flush — same results as the campaign. FINDING-025 (`.states/`
   wiped at startup) and FINDING-024 (`modify_state` legacy token 500) are pre-existing: confirm unchanged, do not
   re-report.
3. FINDING-023 latch (pre-existing): re-run `scripts/drive_mismatch.py` once on a2 to confirm the behaviour is unchanged
   (not a fix target); note only.
4. State managers × deltas after #7216: with the campaign's apps, exercise dev/memory, dev/redis (single worker) and
   prod/redis (2 workers) for a few event rounds each: substate deltas, uncached vars, `rx._x.client_state`,
   background tasks with `async with self`, event chains — compare websocket deltas/keys with the a1 recordings where
   they exist; any stale value, duplicated frame, missing key, or pickling error is a finding.
5. `memo_aschild`: re-run its drivers on a2 dev and prod — #6850 Slot transparency / `as_child`, #7176 memo app-wraps
   (the page that crashed on 0.9.11.post1 must render), #6708 svg memo, #7122 shared event chains; FINDING-008
   (dropdown trigger swallows on_click) is pre-existing — confirm unchanged. Because #7218 changed how the badge wrap
   nests, ALSO check in prod on a2 that every app wrap the memo_aschild app registers (toaster, default overlay, any
   custom `extra_app_wraps`) is present in the DOM together with the badge, and that the toaster still shows toasts.
Write the pass/fail table in NOTES.md and return it in the structured result.
