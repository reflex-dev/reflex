#!/bin/bash
# Usage: run_rtr_redis.sh <venv> <label>  -- prod + Redis (redis-server on 8149) multi-worker run of src/rtr via run_rtr.sh (3146 app, 3147 proxy)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_hydration_router
for i in $(seq 1 40); do redis-cli -p 8149 ping >/dev/null 2>&1 || break; sleep 0.5; done
redis-server --port 8149 --save '' --appendonly no > $W/logs/redis-8149-$2.log 2>&1 &
RP=$!
for i in $(seq 1 20); do redis-cli -p 8149 ping 2>/dev/null | grep -q PONG && break; sleep 0.5; done
$W/scripts/run_rtr.sh $1 prod $2 3146 3146 3147 "${@:3}" -- REFLEX_REDIS_URL=redis://localhost:8149
redis-cli -p 8149 --scan | head -3; echo "redis keys: $(redis-cli -p 8149 dbsize)"
kill $RP; wait $RP 2>/dev/null
