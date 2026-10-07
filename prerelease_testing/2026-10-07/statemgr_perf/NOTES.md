# State-manager and performance follow-up (complete)

Owner: `codex-macos-pass2-01a11520`; all runtime packages are the published PyPI stable0.9.12, alpha0.10.0a1 and alpha2 0.10.0a2 graphs in `/private/tmp/reflex-prerelease-macos-pass2/envs`. No checkout installation or framework fixes. This follows the completed browser_cache_bundle cluster and the original statemgr_perf brief.

- `expiry/`: memory/disk real-browser expiration, root/substate/ComponentState correctness, persistence across backend worker reload, explicit full-CLI reset behavior, debounce and duration parsing/deprecation, active locks/background jobs crossing short TTL. Ports3260–3267/8260–8267. Default manager is disk; actual shared expiration setting is REFLEX_REDIS_TOKEN_EXPIRATION (integer seconds), correcting placeholder names in the brief. Bookkeeping observers are read-only and do not keep tokens alive.
- `redis/`: poolcap3, six Chromium/WebKit contexts with foreground/background work, identities/reload persistence, invalid settings, duration handshake fields, and marked20-substate-event Redis command capture. App ports3268–3273/8268–8273; Redis8269. MONITOR distinguishes client commands from Lua-internal writes, so command counts are not automatically labeled network round trips.
- `performance/`: same-source Var/compile, state attribute/proxy, large dataclass event and SharedState-defined-unused comparisons. Ports3274–3279/8274–8279. Timing ran after other campaign runtimes stopped; warm/cold stages and package-install work are reported separately. No benchmark result is inferred from concurrent correctness runs.
- `verify_expiry/`: independently authored export-workspace app and browser driver, comparing background completion after expiry with ordinary foreground recovery on stable/alpha2, memory/disk and both browser engines. Ports3266/8266, used only after expiry/performance cleanup.

All three trains pass six-session Redis correctness/load/reload. Each alpha's marked event uses one MGET and one EVAL client command for reading/writing the state tree; stable records multiple writes/reads, including a read pipeline. Memory/disk browser and duration coverage includes 1,200 successful short-lived production browser sessions. Alpha2 disk returns its expired state/lock counts to zero; stable disk retains 301 locks after the warm-up plus 300 sessions. Both preserve disk state across worker reload and explicitly reset it on a full CLI restart.

An independent second app confirms the pre-existing partial browser refresh after a background job outlives its session TTL in all eight version/manager/browser combinations; all eight ordinary foreground controls pass. The demonstrated issue is low severity: stale untouched display values, without evidence of corruption or cross-user leakage. Shortened TTL and simulated external I/O are explicit limitations. See `../board/findings-inbox/statemgr_perf-1.md`.

Serial performance measurements began only after correctness servers, browsers and Redis were stopped. All 600 measured clicks pass. Alpha2 reduces this 5,000-row handler's CPU by about 35%, accelerates scalar reads 4.4–4.7 times and writes 8.7–10.9 times, and reduces full Python compilation from 0.726 to 0.640 seconds. No tested alpha2 median is more than 20% slower. These compare published dependency graphs on one host; they do not isolate individual commits or establish production throughput. Detailed repeated samples, exact timing boundaries and dependency differences are in `performance/REPORT.md`.

All owned subprocess groups, browser contexts and Redis were stopped, with per-run and final cleanup audits. Exact commands, frozen graphs and complete console/network/server evidence are retained by each subtask. The structured result is `../board/results/statemgr_perf.md`. The coordinator's separate release blockers still preclude a blanket readiness statement.

## Clean published environment setup

The four exact existing graphs are also frozen in the completed neighboring artifact. To recreate them from PyPI in a new neutral root (never run Python from the checkout):

```sh
export SB=/private/tmp/reflex-statemgr-replay
ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07
mkdir -p "$SB"
cd "$SB"
export UV_CACHE_DIR="$SB/uv-cache"
for version in alpha2 alpha stable driver; do
  uv --no-config venv --python 3.12 "$SB/envs/$version"
  uv --no-config pip install --python "$SB/envs/$version/bin/python" --prerelease=allow -r "$ART/browser_cache_bundle/deploy_cache/evidence/$version-freeze.txt"
done
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" playwright install chromium webkit
```

Follow each subdirectory's commands after that setup. Redis cases additionally require the host's `redis-server` and `redis-cli`; their actual versions/commands are recorded separately. Benchmarks must run alone after all correctness servers and browsers are stopped. Backend/frontend build environments must not inherit client-only NO_PROXY overrides. Production and development runs are identified separately in results.
