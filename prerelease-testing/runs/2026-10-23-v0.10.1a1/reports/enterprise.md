# enterprise — agent report (summary)

reflex-enterprise 0.9.8 on 0.10.1a1 behaves like on 0.10.0 across auth (N-032 dev + prod, deep links, a4 matrix 36/36,
MCP OAuth + anonymous MCP), AG Grid (N-025), demos (dnd / mantine / flow / map dev + prod) and HYD-15; positive controls
valid (0.10.0a2 / rxe 0.9.6 reproduce N-032 / N-025).
Findings:
- EN-1 (medium, REGRESSION) #7273 structural sharing: a second `rxe.ag_grid` (index row ids) bound to the same state
  list stays stale after a cell edit in a sibling grid (A with row_id_key) — 3/3 on 0.10.1a1, 0/2 on 0.10.0. Every
  button-driven in-place op updates both. Mechanism (hypothesis): AG Grid mutates the shared row object in the browser
  before the event; the returning delta carries the same value; structural sharing keeps the old reference, so grid B's
  rowData prop never changes. Repro: enterprise/own/gridshare, own_run.sh new-ent gridshare dev new.
- EN-2 (= HN-1, medium, not a regression, rxe tracker) rxe 0.9.8 REST event API sets router.session.client_ip from the
  leftmost XFF regardless of reflex trusted_proxy_hops (websocket honours #7614). No rxe security decision keys on it
  (rate limiters use their own hops; audit has no IP); user handlers reading client_ip over REST get a spoofable value.
- EN-3 (low, rxe-side, not a regression) intermittent MCP OAuth consent race on Redis (lands on /login); same on 0.10.0.
Passed: rxe import sweep 112/113 + deprecated shims; hook ordering with rxe's deprecated `VarData(position=)` (dnd,
combobox) — 0 use-before-declare, deprecation warning names the rxe file once per compiling process; #7614 websocket;
rxe 0.9.8 #277 pending-login driver; AG Grid demo prod; HYD-15 across forked dev hot reload.
Re-verified: ENT-30, ENT-29, ENT-16/DOC-14, HYD-15/CMP-05, ENT-01/02/CLI-03 fixed; CMP-51 (N-028) now fixed by #7587;
ENT-07 (N-033, rxe#262) and ENT-31 (N-026, rxe#269) unchanged; ENT-27 (rxe#245) not re-run.
Observation: REST responses carry the caller's own raw cookie header in rx_router_headers (both versions, same caller).
Not covered: expiry matrix, prod_suite / bglive, vauthx / vea, mapsapp, highcharts / tickets / rxeapp, azure auth,
lazy bundled libraries, react_compiler with rxe, rxe#245 re-check.
