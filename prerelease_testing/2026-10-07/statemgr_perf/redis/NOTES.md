# Redis browser concurrency, pool validation, and substate writes

Status: complete, including the validation-only confirmation.
Scope: `statemgr_perf/redis/` only. Frontend 3268, backend 8268, dedicated Redis 8269.
Host: macOS 26.6.2 (25G83), arm64. Chromium 153.0.8010.12, Playwright WebKit 26.6.
Only published alpha2, alpha1, and stable environments are imported. The app and
metadata probe assert their package origin. No framework files or shared envs changed.

## Real app and browser workload

`app/` defines one dashboard state and twenty separately serialized child states.
The page displays every child, a session identity, foreground/background counts,
and completion status. Each run starts a dedicated Redis with persistence disabled,
then one Reflex dev server against that Redis. No other Redis database is touched.

The driver creates three Chromium and three WebKit contexts. Each supplies a
distinct session identity. Before concurrent work, the first Chromium session
updates all twenty children in a single event while Redis MONITOR is recording.
Its twenty children must become 1; the other five sessions must remain at 0.

All six sessions then start a background event with twenty separate locked state
updates and concurrently send twenty foreground clicks each. Every session must
show foreground=20, background=20, finished=true, its own identity, and its expected
twenty child values. Reloading all six pages must preserve the identities, foreground
and background counts, and twenty child values. This checks
120 foreground events, 120 background increments, session isolation, and persistence
per release; it is not a latency benchmark or a guaranteed pool-exhaustion test.

Alpha2 and alpha1 use `REFLEX_REDIS_MAX_CONNECTIONS=3`,
`REFLEX_REDIS_POOL_TIMEOUT=500ms`, `REFLEX_SOCKET_INTERVAL=2m`, and
`REFLEX_SOCKET_TIMEOUT=10s`. The same configuration factory reports
`BlockingConnectionPool`, max_connections=3, timeout=0.5. Stable has no cap feature:
the probe reports `ConnectionPool`, max_connections=2147483648, timeout=null.
Stable receives numeric socket durations 120/10 because suffix parsing is new.

| Published release | Six concurrent sessions | Reload persistence | Socket handshake |
| --- | --- | --- | --- |
| 0.10.0a2 | All pass | All pass | 120000 ms interval / 10000 ms timeout |
| 0.10.0a1 | All pass | All pass | 120000 ms interval / 10000 ms timeout |
| 0.9.12 | All pass | All pass | 120000 ms interval / 10000 ms timeout |

The socket values are observed from actual Engine.IO opening frames in every
browser, before and after reload. This verifies the values used by the connection,
rather than relying only on a parser or generated config inspection.

No pool-timeout, lost-event, lock-expiration, or session-mixing failure appears.
All sessions have zero uncaught page errors and zero HTTP errors. WebKit records
unused module-preload warnings and six canceled preload requests per context
(the same three module URLs across initial load and reload), on all three versions.
Stable logs the pre-existing nonfatal `Dashboard.rename` payload transformation
warning. Framework plugin/deprecation and frontend peer-dependency warnings are
also retained in the gzip logs. None prevent correct final state.

## Redis command evidence

The driver brackets one `update_all` event with `ECHO QA_BATCH_START` / `END` on its
own Redis. `batch.monitor.log.gz` contains the complete marked capture. The JSON
summary distinguishes client-origin commands from `[0 lua]` commands and preserves
line references. Both alpha releases have identical counts:

| Origin / command | 0.10.0a2 | 0.10.0a1 | 0.9.12 |
| --- | ---: | ---: | ---: |
| Client SET | 1 | 1 | 22 |
| Client MGET | 1 | 1 | 0 |
| Client GET | 0 | 0 | 44 |
| Client PTTL | 0 | 0 | 22 |
| Client EVAL | 1 | 1 | 0 |
| Client MULTI / EXEC | 0 / 0 | 0 / 0 | 1 / 1 |
| Client GETDEL | 1 | 1 | 1 |
| Lua SET | 21 | 21 | 0 |
| Lua GET / PTTL | 1 / 1 | 1 / 1 | 0 / 0 |

The common client SET acquires the lock. Stable's other 21 SETs save the dashboard
and twenty changed children individually. Each alpha's single client EVAL performs
the lock check and all 21 saves inside Redis, matching the published fenced-save
implementation. This confirms the one-command save improvement for this real event.
Do not interpret total MONITOR command count as network round trips: stable's reads
are pipelined in MULTI/EXEC, and Lua-internal commands do not cross the client network.
No wall-clock speedup claim is made while other local campaign workloads run.

## Invalid configuration behavior

The driver separately starts the real backend with a cap of 2, then with a pool
timeout of 11s against the default 10s state-lock expiration. Both alphas print
the expected precise `EnvironmentVarValueError`: cap must be at least 3; timeout
must be positive and shorter than the lock expiration. The worker exits, but the
CLI supervisor and resource tracker remain alive past the bounded observation.
The harness then terminates their process group. A final returncode of 0 reflects
that graceful termination, **not** successful startup.

Alpha1 `results/alpha-1/results.json` records `timed_out: true`, wait_seconds=15,
and the still-running PIDs before cleanup for both invalid cases. The first alpha2
driver waited 60 seconds but omitted its timeout flag from the final JSON; its
error logs and cleanup are preserved. `results/alpha2-validation/results.json`
confirms both errors and explicitly records timed_out=true, wait_seconds=15, and
live CLI/resource-tracker PIDs before successful cleanup. The issue reproduces in alpha1;
it is not a new alpha2 regression. Stable lacks these pool settings, so there is
no equivalent 0.9.12 pool-validation test here.

## Reproduce and inspect

```sh
export SB=/private/tmp/reflex-prerelease-macos-pass2
export UV_CACHE_DIR="$SB/uv-cache"
export ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/statemgr_perf/redis
cd "$SB"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env alpha2
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env stable
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env alpha
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env alpha2 --attempt validation --validation-only --validation-wait 15
```

Run sequentially. The script refuses existing scratch app directories; choose a
new `--attempt` for a repeat. It requires `/opt/homebrew/bin/redis-server` and
`redis-cli`, and campaign Playwright Chromium/WebKit. Logs are compressed after
the case, and JSON retains console, page errors, failed requests, HTTP errors,
bounded websocket frames, actual socket handshakes, metadata, command counts,
and cleanup. Representative screenshots show the changed Chromium session and
an isolated WebKit session after reload. Every owned process group and all three
reserved listeners must be empty before finishing; other campaign processes are
never signaled.
