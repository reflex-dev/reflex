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
