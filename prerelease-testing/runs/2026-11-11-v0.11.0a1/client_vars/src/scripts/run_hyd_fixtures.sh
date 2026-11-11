#!/usr/bin/env bash
# Re-verify HYD-08/HYD-09 (sync=True storms) with the hydration fixtures on the client_vars ports.
# Control first (0.10.0a3 must storm), then the version under test.
export SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
export WORK=$SB/apps/client_vars/hyd PORT_RANGES="3260-3279 8260-8279" REDIS_PORT=8279
F=/home/user/reflex/prerelease-testing/fixtures/hydration
CTRL=${CTRL:-client_vars-ctrl-a3}; NEW=${NEW:-new}
cd "$WORK" || exit 1
for V in $CTRL $NEW; do
  n=3; [ "$V" = "$CTRL" ] && n=2
  echo "=== storm $V dev"
  "$F/scripts/run_storm.sh" "$V" dev $n 3264 8264 S 6
  "$SB/envs/driver/bin/python" "$F/scripts/summ_s.py" "$WORK/results/sync/storm_${V}_dev_S_6_"
  echo "=== stamp $V dev"
  nc=1; [ "$V" = "$CTRL" ] && nc=0
  "$F/scripts/run_stamp2.sh" "$V" dev 3264 8264 $n $nc 6
done
echo "=== storm $NEW prod"
"$F/scripts/run_storm.sh" "$NEW" prod 3 3265 3265 S 6
"$SB/envs/driver/bin/python" "$F/scripts/summ_s.py" "$WORK/results/sync/storm_${NEW}_prod_S_6_"
echo "=== stamp $NEW prod"
"$F/scripts/run_stamp2.sh" "$NEW" prod 3265 3265 3 1 6
echo "=== done"
