#!/bin/bash
# Part 2 F-002: a1 positive control (prod) then a5 prod, a5 dev, a5 prod+Redis -- back to back.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_hydration_router
O=$W/results/p2; mkdir -p $O
$W/scripts/run_f002.sh alpha prod a1prod 3140 3140 > $O/f002_a1prod.txt 2>&1
$W/scripts/run_f002.sh a5 prod a5prod 3140 3140 > $O/f002_a5prod.txt 2>&1
$W/scripts/run_f002.sh a5 dev a5dev 3142 8142 > $O/f002_a5dev.txt 2>&1
redis-server --port 8149 --save '' --appendonly no > $W/logs/redis-8149-f002.log 2>&1 &
RP=$!
for i in $(seq 1 20); do redis-cli -p 8149 ping 2>/dev/null | grep -q PONG && break; sleep 0.5; done
$W/scripts/run_f002.sh a5 prod a5prodredis 3144 3144 REFLEX_REDIS_URL=redis://localhost:8149 > $O/f002_a5prodredis.txt 2>&1
kill $RP; wait $RP 2>/dev/null
echo P2_F002_DONE >> $O/f002_a5prodredis.txt
