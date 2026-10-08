(structured report of the a5_upgrade_ent agent; full detail in ../../a5_upgrade_ent/NOTES.md)
No new or regressed issue. N-032, N-025, N-001, F-005, F-006, F-014 fixed; auth matrix 36/36 + MCP; deep-link login and
client nav keep redirect_to; reflex-azure-auth on_load callback OK; upgrades 0.9.12 -> a5 and a4 -> a5 = a4 pass;
22-package sweep = a4; local-auth / magic-link / google-auth known results only. Only a4 -> a5 difference: the intended
#7360 fix (HttpOnly _oidc_* token cookies no longer reach the browser in rx_router_headers; server-side reads work).
