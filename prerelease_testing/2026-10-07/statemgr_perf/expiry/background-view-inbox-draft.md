ITEM: statemgr_perf
KIND: new
REF: -
TITLE: Background event completing after expiry leaves untouched browser state stale until reload
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: unknown
REPRO: Follow expiry/NOTES clean bootstrap and run_case invocation, selecting --scenario jobs --expiration 5. Initial root/child/component counts are2/3/2/1. A normal held-lock event and queued click bring root to13. The background event releases async-with-self during seven seconds of external work, reacquires after expiry, increments fresh root by10 and finishes. Public get_state inspection sees10/0/0/0, but immediately after completion the saved DOM is10/3/2/1. Reload restores10/0/0/0. Ordinary post-idle foreground click updates the entire DOM correctly, so scope is the released background completion path.
EVIDENCE: expiry/runs/{alpha2,stable}-{memory,disk}-jobs-*/chromium-results.json.gz fields after_job_visible and expired-background-reacquire-server; full chromium-frames.json.gz; SUMMARY.json.background_visible_anomalies. All four version/manager combinations agree.
ROOT_CAUSE_GUESS: The background completion sends a partial delta for its changed state after reacquiring a new expired-session tree, while the client retains untouched values from the old tree. Inference from wire/DOM/backend comparisons; no framework changes applied. Parent assigns independent verification and decides board submission.
