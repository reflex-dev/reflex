#!/bin/bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_hydration_router; cd $W
date; echo "### h4 a4 prod"; $W/scripts/run_h4.sh a4 prod a4prod 3148 3148 -
date; echo "### h4 a4 prod+redis"
redis-server --port 8149 --save '' --appendonly no > $W/logs/redis-8149.log 2>&1 & RP=$!
for i in $(seq 1 40); do redis-cli -p 8149 ping 2>/dev/null | grep -q PONG && break; sleep 0.25; done
$W/scripts/run_h4.sh a4 prod a4prodredis 3148 3148 C1,C2,C3,C4,C7,C10 REFLEX_REDIS_URL=redis://localhost:8149
kill $RP; for i in $(seq 1 40); do lsof -iTCP:8149 -sTCP:LISTEN -P -n > /dev/null 2>&1 || break; sleep 0.5; done
date; echo "### local-auth a4 dev"; $W/scripts/run_la.sh a4_hydration-tp-a4 dev a4dev 3153 8153
date; echo "### google-auth a4 dev seed4"; $W/scripts/run_gauth.sh a4_hydration-tp-a4 dev a4dev-s4 3142 8142 4
date; echo "### done"
