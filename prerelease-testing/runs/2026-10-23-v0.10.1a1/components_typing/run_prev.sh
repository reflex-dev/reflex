#!/bin/bash
# Stop prod (new), start the 0.10.0 baseline dev server on 3242/8242, drive all pages, stop it.
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
cd $SB/apps/components_typing
./killtree.sh logs/prod_new.pid
echo "prod stopped; listeners on 3241: $(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3241/ 2>/dev/null)"
rm -rf prevapp && mkdir prevapp && cp -r ctapp/rxconfig.py ctapp/ctapp ctapp/assets prevapp/
cd prevapp
EXPECT_VENV=components_typing-prev REFLEX_TELEMETRY_ENABLED=false $SB/envs/components_typing-prev/bin/reflex run --frontend-port 3242 --backend-port 8242 --loglevel debug > ../logs/dev_prev.log 2>&1 &
echo $! > ../logs/dev_prev.pid
cd ..
for i in $(seq 1 90); do
  if curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3242/ 2>/dev/null | grep -q 200; then echo "prev dev up after ${i}x5s"; break; fi
  sleep 5
done
sleep 5
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
$SB/envs/driver/bin/python drive_ct.py --base http://localhost:3242 --out results/drive_dev_prev.json --shots shots/dev_prev > logs/drive_dev_prev.log 2>&1
echo "PREV DRIVE DONE rc=$?"
./killtree.sh logs/dev_prev.pid
echo "prev stopped"
