A second review round, all reproduced before fixing.

An arrival to a past-deadline parent is now refused as `expired` on every store. Previously `record_arrival` accepted it everywhere while the atomic path diverged — Postgres refused, Memory and SQLite resolved the join — so the same fan-out behaved differently depending on the store behind it. A conformance check covers both paths.

A new schedule is seeded from store time rather than worker time. The seed was captured when the kernel was constructed, before the first clock sync, so a worker whose machine ran slow backfilled occurrences from before the deployment existed. It is taken at the end of the first recovery pass instead, which is still "when this worker started" but on the store's clock.

An empty run id is refused instead of matching every run. `reflex workflows cancel "$RUN_ID"` with the variable unset arrived as an empty string, which is a prefix of everything; with exactly one run in the database it resolved to that run, cancelled it, and reported success.

A second Postgres deadlock is gone. Recovery locked step rows and then updated their runs, while `commit` locks the run and then the step — the store's own invariant is run-first, and recovery was the one path inverting it. A probe measured 56 aborted transactions across 30 rounds; it now sees none in 60. Fixed by lock ordering, like the first one.

Forced-failure error payloads face the same strict serialization as results. The prefix scan no longer disables itself when a database holds exactly the scan limit. Missed-occurrence counts are counted rather than sampled, so a long outage is not undercounted by the bound meant for catch-up.

Postgres now runs in CI. The conformance suite tests every store it can reach, and without a server the Postgres rows skipped silently — which is how store-specific divergences reached review in the first place.
