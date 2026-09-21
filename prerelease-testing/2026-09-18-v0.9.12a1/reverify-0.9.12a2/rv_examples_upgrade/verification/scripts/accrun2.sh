set -u
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_examples_upgrade-verify
cd $W
teardown() {
  $SB/envs/driver/bin/python $W/killtree.py "$@" || true
  extra=$(python3 $SB/bin/ports.py 3763 8763 | sed -n 's/.*pids=\([0-9,]*\).*/\1/p' | tr ',' ' ')
  if [ -n "$extra" ]; then echo "leftover pids: $extra"; $SB/envs/driver/bin/python $W/killtree.py $extra || true; fi
  python3 $SB/bin/ports.py 3763 8763 && echo "PORTS CLEAR"
}
for pair in "a1 shared" "a2 a2"; do
  set -- $pair
  tag=$1; venv=$2
  out=$(bash run2.sh $W/apps/acc_$tag $SB/envs/$venv 3763 8763 $W/logs/acc_$tag.log)
  echo "START $tag: $out"
  pid=$(echo "$out" | sed -n 's/^PID=//p')
  if echo "$out" | grep -q "UP after"; then
    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive.py "http://localhost:3763/" acc.json $W/shots/acc_$tag > $W/logs/drive_acc_$tag.txt 2>&1
    echo "DRIVE $tag done"
  fi
  teardown $pid
done
echo ALLDONE2
