(structured report of the a5_hydration_router agent; full detail in ../../a5_hydration_router/NOTES.md)

#7360: no functional regression and the security claim holds. Backend self.router view in every on_load flavour
(single, list, chains, returned events, background task, redirects, dynamic + catch-all routes, client nav, back/forward,
reload, two tabs, reconnect) field-for-field identical a4 vs a5 in dev (37 steps), prod (35) and prod + Redis 9 workers
(35); the server still sees cookies (incl. HttpOnly) and credential headers after a Redis round trip on another worker.
Browser: a4 (positive control) leaks all 10 test secrets into websocket frames and the DOM; a5 0 occurrences in frames,
prerendered HTML, DOM and console in dev, prod, prod + Redis. Deprecated State.router.headers.cookie renders "" and warns
in the compile log once per call site. local-auth 36/38 (known) + 14/14 storage; google-auth bogus token cleared.
REVERIFIED: F-002 fixed (a1 control writes 8 keys; a5 nothing), F-003 fixed (a1 control bad; a5 cvstore = a3
baselines), A3-11 fixed (a3 3/4 dev + 3/3 prod storms; a5 0/5 + 0/4), A3-12 fixed (a3 2/2 + 2/2; a5 0/3 + 0/3).
ISSUES: none attributable to a5. Pre-existing (0.9.12 / a4 / a5): an app package without __init__.py breaks every state
update with a misleading "no dispatch function" console error.
