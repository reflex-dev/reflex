set -u
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_examples_upgrade-verify
cd $W
teardown() {
  fp=$1; bp=$2; shift 2
  $SB/envs/driver/bin/python $W/killtree.py "$@" || true
  extra=$(python3 $SB/bin/ports.py $fp $bp | sed -n 's/.*pids=\([0-9,]*\).*/\1/p' | tr ',' ' ')
  if [ -n "$extra" ]; then echo "leftover: $extra"; $SB/envs/driver/bin/python $W/killtree.py $extra || true; fi
  python3 $SB/bin/ports.py $fp $bp && echo "PORTS $fp $bp CLEAR"
}
# A) accordion probe in PROD on a2 (React production build strips the dev warning?)
out=$(bash run2.sh $W/apps/acc_prod $SB/envs/a2 3760 3760 $W/logs/acc_a2_prod.log --env prod)
echo "START accprod: $out"; pid=$(echo "$out" | sed -n 's/^PID=//p')
if echo "$out" | grep -q "UP after"; then
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive.py "http://localhost:3760/" acc.json $W/shots/acc_a2_prod > $W/logs/drive_acc_a2_prod.txt 2>&1
  echo "DRIVE accprod done"
fi
teardown 3760 3760 $pid
# B) dynroute probe in DEV on a2 (control: is the 404 prod-only?)
out=$(bash run2.sh $W/apps/dyn_dev $SB/envs/a2 3761 8761 $W/logs/dyn_a2_dev.log)
echo "START dyndev: $out"; pid=$(echo "$out" | sed -n 's/^PID=//p')
if echo "$out" | grep -q "UP after"; then
  for u in / /item/7 /item/abc /nope; do
    echo "DEV $u -> $(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3761$u)"
  done
fi
teardown 3761 8761 $pid
echo EXTRASDONE
