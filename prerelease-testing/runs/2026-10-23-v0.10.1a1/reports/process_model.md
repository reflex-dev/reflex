# process_model — agent report (summary)

Finding:
- PM-1 (medium, REGRESSION for `reflex run --env prod --backend-only` on 3.12 and any prod run on 3.14): #7079 fork
  preload imports the app once in the supervisor, so import-time threads (incl. a logging `QueueListener`) are dead in
  every forked worker (0/30 worker log records reach a queued log file) and module-level random/uuid values and user
  `random.Random()` instances are identical across workers. 0.10.0 imported per worker there (9/9 alive, 9 distinct).
  Documented trade-off (`REFLEX_BACKEND_START_METHOD=spawn`) but silent, and PRNG/constant sharing is undocumented.
  Repro: process_model/NOTES.md ISSUE-1, scripts/probe_run.sh new new-be-fork prod-be 8201 vs prev.

Passed: worker cap 8 + GRANIAN_WORKERS override; EVT-04 6/6 cross-worker; sqlite pooled pre-fork conn under 8 workers;
redis pre-fork client; lifespan tasks; clean SIGTERM/SIGINT (no "Unexpected exit"); start methods incl. invalid value;
PSS 205 MB vs 238 MB, startup 8 s vs 13 s; dev hot reload (fork, Redis, 3.14); #7453 exports serialized; #7052 no
corruption (prev crashes with JSONDecodeError); #7304 no-__init__ app works (prev fails: positive control).
Re-verified: CLI-16 fixed, EVT-04 fixed, STATE-36 fixed, CLI-26/A3-07 fixed, CLI-09 fixed; CLI-27/A3-08 and
CLI-15/F-007 still broken (filed, unchanged).
Context (same on 0.10.0): kill -9 of one prod worker shuts the whole server down; rxconfig edits not hot-reloaded;
`reflex export --zip-dest-dir <missing>` traceback. During add-page hot reload the #7553/#7435 warnings show transiently.

## Verifier (verify_pm1/NOTES.md): RECLASSIFIED → low
Regression scope confirmed exactly: `--backend-only` prod on Linux (3.12; 3.11/3.13 by mechanism) and both prod modes on
3.14. Full-stack prod on 3.12 is NOT a regression (0.10.0 already forked from the compiling CLI). Only module-level
constants and user `random.Random()` instances are shared; the global `random` is reseeded at fork, uuid4/secrets fresh
per request. Real patterns: QueueListener loses all worker records and its queue grows per worker; APScheduler reports
running but its job runs only in the supervisor. reflex-otel 0.2.0 + OTel SDK UNAFFECTED (register_at_fork hooks).
CPython's multi-threaded-fork DeprecationWarning is hidden by default. Spawn fully restores 0.10.0 behaviour (~3x memory).
Recommendation: behaviour-change note in the changelog naming the changed cases + examples; optionally a fork-time log
line listing extra supervisor threads with the spawn hint.
