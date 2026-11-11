#!/bin/bash
# Usage: run_rtr_redis.sh <venv> <label> [driver flags...]  -- prod + Redis (redis-server on $REDIS_PORT) multi-worker run
# of src/rtr via run_rtr.sh (app 3146 one port, header proxy 3147).
. "$(dirname "$0")/env.sh"
redis_up || exit 1
"$F/scripts/run_rtr.sh" "$1" prod "$2" 3146 3146 3147 "${@:3}" -- REFLEX_REDIS_URL=redis://localhost:$REDIS_PORT
redis-cli -p "$REDIS_PORT" --scan | head -3; echo "redis keys: $(redis-cli -p "$REDIS_PORT" dbsize)"
redis_down
