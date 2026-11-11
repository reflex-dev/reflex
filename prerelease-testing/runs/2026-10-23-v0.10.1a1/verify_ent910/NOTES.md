# verify_ent910 — reflex-enterprise 0.9.10a1 (user-supplied offline wheel) on reflex 0.10.1a1

Venv `$SB/envs/ent910`: `reflex[db]==0.10.1a1` from PyPI (`--only-binary :all:`) + the offline wheel
`reflex_enterprise-0.9.10a1-0offline` (not committed). Fixes in this build: rxe #279 (REST client IPs from the
framework's `trusted_proxy_hops`), rxe #282 (ag_grid edits deep copies of state rows, cached per list).
Controls: `new-ent` (reflex 0.10.1a1 + rxe 0.9.8), `prev-ent` (reflex 0.10.0 + rxe 0.9.8).

## R101-01 (stale memoized consumers after an AG Grid edit) — FIXED
App `gridfix/` (`./run.sh <venv> <dev|prod> <label> [chart=1]`, ports 3611/8611): one `GS.rows` list (with a nested
`addr.city`) bound to grid A (stores the edit), grid C (clamps to 100), grid R (rejects), a read-only grid B, an
`@rx.memo` view, the unmemoized store text and `rx.foreach`. Y = view shows the backend value.

| step | rxe 0.9.10a1 dev / prod / +recharts | rxe 0.9.8 on 0.10.1a1 (control) | 0.10.0 + rxe 0.9.8 |
|---|---|---|---|
| A price → 777 (stored as typed) | all Y | **memo, C, R, B stale** | all Y |
| A nested addr.city → paris | all Y | **memo, C, R, B stale** | all Y |
| C → 500, clamped to 100 | all Y | all Y | all Y |
| R → 5, rejected (state keeps 777) | all Y except grid R shows its typed 5 | store, foreach, C, R wrong (AG Grid wrote 5 into the store) | store, foreach, R wrong |
| after reload, A → 778 | all Y | **memo, C, R, B stale** | all Y |

The rejected-edit case is the limitation rxe #282 accepts (the rejecting grid keeps its edited copy until the next list
arrives); it is strictly better than 0.10.0, where the rejected value leaked into the store and every unmemoized view.
Explorer's original `own/gridshare` suite: 45/45 on 0.9.10a1 (44/45 on 0.9.8). 0 page errors, 0 server tracebacks.

## R101-22 (recharts deep-freeze blocks AG Grid edits) — FIXED as a side effect
`GF_CHART=1` (bar chart of the same rows): 0.9.10a1 edits work, all views correct; 0.9.8 throws `Cannot assign to read
only property 'price'` on every edit (the grid now writes into its own copies, not recharts-frozen store objects).

## R101-07 (REST event API client_ip) — FIXED
`own/xff_run.sh ent910 <reflex hops> <label>` (+ `XFF_RXE_HOPS`), outputs `out/xff_ent910-*.txt`:

| config | REST `client_ip` for none / `6.6.6.6` / `6.6.6.6, 7.7.7.7` / junk | websocket |
|---|---|---|
| reflex `trusted_proxy_hops=0` | 127.0.0.1 ×4 (0.9.8: 6.6.6.6 / 6.6.6.6 / junk) | 127.0.0.1 ×3 |
| reflex `trusted_proxy_hops=1` | 127.0.0.1 / 6.6.6.6 / 7.7.7.7 / junk verbatim | identical |
| reflex 0, deprecated `EventHandlerAPIPlugin(trusted_proxy_hops=1)` | as hops=1 | 127.0.0.1 (reflex 0) |

REST and websocket now agree whenever the depth is set in the config. Token-grant rate limit (limit 3,
`hnet_rl` variant): hops 0 → rotating spoofed XFF `200 200 200 429 429 429`; hops 1 behind an appending proxy
(`<spoof>, 9.9.9.9`) → `200 200 200 429 429`; hops 1 with direct rotating XFF → all 200 (expected: a declared proxy
that is not there is the documented misconfiguration).
Residual notes (not blockers): with hops ≥ 1 the selected token is not validated as an IP — same as reflex core
(R101-09); the deprecated plugin-only setting makes REST and websocket disagree (documented precedence; the hnet
fixture always passes the plugin argument, so the deprecation notice could not be isolated from that run).
