#!/bin/bash
# Re-drive cbg+de on the running dev server, stop it, then start prod (new) on port 3241 and drive all pages.
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
cd $SB/apps/components_typing
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
$SB/envs/driver/bin/python drive_ct.py --base http://localhost:3240 --out results/drive_dev_new3.json --shots shots/dev_new3 --pages cbg,de > logs/drive_dev_new3.log 2>&1
unset NO_PROXY no_proxy
kill $(cat logs/dev_new.pid) 2>/dev/null; sleep 3
pkill -P $(cat logs/dev_new.pid) 2>/dev/null; sleep 2
for p in $(ss -ltnp 2>/dev/null | grep -E ":3240|:8240" | grep -oE "pid=[0-9]+" | cut -d= -f2 | sort -u); do kill $p 2>/dev/null; done
sleep 2
echo "dev stopped: $(ss -ltn | grep -cE ':3240|:8240') listeners left"
cd ctapp
EXPECT_VENV=new REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=http://localhost:3241 $SB/envs/new/bin/reflex run --env prod --frontend-port 3241 --backend-port 3241 --loglevel debug > ../logs/prod_new.log 2>&1 &
echo $! > ../logs/prod_new.pid
cd ..
for i in $(seq 1 120); do
  if curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3241/ 2>/dev/null | grep -q 200; then echo "prod up after ${i}x5s"; break; fi
  sleep 5
done
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
$SB/envs/driver/bin/python drive_ct.py --base http://localhost:3241 --out results/drive_prod_new.json --shots shots/prod_new > logs/drive_prod_new.log 2>&1
echo "PROD DRIVE DONE rc=$?"
