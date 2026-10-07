#!/bin/bash
# Usage: prod.sh <venv> <tag-for-log> [extra env assignments via env]   -- starts fleet_<venv> in prod on 3600 with redis 8603
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/verify_core_a2
V=$1; TAG=$2
FLEET_API_URL=http://localhost:3600 REFLEX_REDIS_URL=redis://localhost:8603 PIDTAG=prod \
  $W/bin/start_app.sh $V $W/fleet_$V 3600 3600 $W/logs/fleet-$TAG.log --env prod --loglevel debug
$W/bin/wait_up.sh http://localhost:3600/ 420 $W/pids/prod.pid
