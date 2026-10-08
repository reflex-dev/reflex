#!/bin/bash
# N-004 e2e: one Redis (8309), c4e2e prod on 3303 alternating a3 -> a4 -> a3 -> a4 on one session token.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a4_class_state
OUT=$W/logs/n004/redis_chain.txt; : > $OUT; TOK=$W/out/e2e/n004-token.txt; redis-cli -p 8309 flushall >/dev/null
i=0
for V in a3 a4 a3 a4; do
  i=$((i+1)); MODE=resume; [ $i = 1 ] && MODE=new
  rm -rf $W/run/e2e/n004-$V; cp -r $W/apps/c4e2e $W/run/e2e/n004-$V
  [ -d $W/run/e2e/n004-$V-web ] && mv $W/run/e2e/n004-$V-web $W/run/e2e/n004-$V/.web
  C4_API_URL=http://localhost:3303 REFLEX_REDIS_URL=redis://localhost:8309 PIDTAG=n004 $W/bin/start_app.sh a4_class_state-$V $W/run/e2e/n004-$V 3303 3303 $W/logs/e2e/n004-$i-$V.raw.log --env prod > /dev/null
  $W/bin/wait_up.sh http://localhost:3303/ 500 $W/pids/n004.pid > /dev/null || { echo "phase $i $V not up" >> $OUT; break; }
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/bin/drive_resume.py http://localhost:3303 $TOK $MODE "$i:$V" >> $OUT 2>&1
  echo "   server log errors: $(grep -i -E 'traceback|mismatch|error' $W/logs/e2e/n004-$i-$V.raw.log | grep -v -E 'react-error-boundary|errorBoundaries|Unexpected exit from worker' | head -3 | tr '\n' ' ')" >> $OUT
  $W/bin/stop_app.sh $W/pids/n004.pid > /dev/null
  mv $W/run/e2e/n004-$V/.web $W/run/e2e/n004-$V-web 2>/dev/null
done
cat $OUT
