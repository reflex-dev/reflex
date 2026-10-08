(structured report of the a4_upgrade_ent agent, 2026-10-08; full detail in ../../a4_upgrade_ent/NOTES.md)

No new issue; every check equals the a3 pass back to back. Upgrades in place: form-designer (reflex[db] + local-auth),
github-stats, twitter prod+Redis 0.9.12 -> a4, twitter prod+Redis a3 -> a4 (only reflex + reflex-base move,
.web/package.json unchanged; 0.9.12- and a3-pickled Redis sessions load); cold rebuilds equal. No reflex-examples app and
nothing in enterprise a5 assigns a state var through its class (0 TypeError in any log). Third-party sweep 22/22 = a3;
local-auth 36/38 dev/prod/prod+Redis, magic-link 10/11, google-auth 12/13 (known failures only).
REVERIFIED: N-032 stays fixed (vauth stale/away/xtab 3/3 dev+Redis and prod 1 worker; entauth suites ALL_PASSED; auth
matrix 36/36 + MCP). N-025 stays fixed (entv s1-s13 = a3 prod; aggrid_min 4/4). dnd 27/27, mantine 23/23, map 4/4,
flow 20-21/22 (N-026 timing race on both versions).
#7505 visible effect (intended): the enterprise token hash (sync=True) is no longer rewritten with the same value on each
boot (0 writes per boot vs 1 on a3). O-2: a protected sync=True var's SECOND identical boot delta (A3-13's re-send) is
still written with the same value (the first is skipped as the echo).
