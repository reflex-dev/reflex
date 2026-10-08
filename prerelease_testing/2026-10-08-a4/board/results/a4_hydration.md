(structured report of the a4_hydration agent, 2026-10-08; full detail in ../../a4_hydration/NOTES.md)

REVERIFIED: A3-11 fixed (a3 positive control stormed first, back to back, same load: explorer dev 5/8 -> a4 0/8, prod
1/5 -> 0/5; 100 ms RTT raw3 dev 3/3 -> 0/3, prod+Redis 9 workers 2/3 -> 0/3, restore7 2/2 -> 0/2; race hit in every a4
run; all tabs + localStorage end on the user's last value). A3-12 fixed (/stamp 6 tabs dev 3/3 -> 0/4, prod 2/2 -> 0/3;
background /doc tabs 2/2 -> 0/2 dev and prod+Redis; dev backend reload 2/2 -> 0/2; one value, 0 frames afterwards).
F-002 / F-003 stay fixed. #7505 hunt (h4mix: sync=True/False LS, SS, cookie max_age, substate, ComponentState,
sanitising get_delta override, on_load, background task, yield chains, ""/unicode/JSON/6 KB values; 1-3 tabs; dev, prod,
prod+Redis; vs a3 and 0.9.12): no functional regression; the review bug (sync=False handler write) stays fixed;
a3's stale-echo loss of yield-chain updates is gone on a4. reflex-local-auth 36/38 (known demo pitfall) + 14/14 storage,
google-auth bogus-token clearing = a3.
ISSUES (pending verification): (1) two tabs writing a sync=True var within ~1 RTT converge on the value STORED last, not
the user's last write (a4 c8 5/5; a3 c9 after a short ping-pong; 0.9.12 c9 3/4, c5 1/4 after a long ping-pong) — low,
behaviour change vs a3, not a regression vs 0.9.12.
ANOMALY (pre-existing a3/a4/0.9.12): rx.remove_local_storage of a synced key makes the other tab sync null into a str var;
a computed var then raises TypeError (len(None)) and that tab keeps the old value.
