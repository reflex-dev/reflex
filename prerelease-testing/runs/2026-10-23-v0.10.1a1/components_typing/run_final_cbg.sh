#!/bin/bash
# Wait for the prev chain to exit, then restart new dev (existing .web), drive cbg with the final driver, stop it.
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
cd $SB/apps/components_typing
while kill -0 $(cat logs/run_prev.pid) 2>/dev/null; do sleep 5; done
./killtree.sh logs/dev_prev.pid
cd ctapp
EXPECT_VENV=new REFLEX_TELEMETRY_ENABLED=false $SB/envs/new/bin/reflex run --frontend-port 3240 --backend-port 8240 --loglevel debug > ../logs/dev_new_final.log 2>&1 &
echo $! > ../logs/dev_new.pid
cd ..
for i in $(seq 1 60); do
  if curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3240/ 2>/dev/null | grep -q 200; then echo "new dev up after ${i}x5s"; break; fi
  sleep 5
done
sleep 5
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
$SB/envs/driver/bin/python drive_ct.py --base http://localhost:3240 --out results/drive_dev_new_cbg_final.json --shots shots/dev_new_final --pages cbg,de > logs/drive_dev_new_cbg_final.log 2>&1
echo "FINAL CBG DRIVE DONE rc=$?"
./killtree.sh logs/dev_new.pid
echo "new dev stopped"
