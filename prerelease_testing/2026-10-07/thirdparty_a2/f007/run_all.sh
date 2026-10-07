#!/bin/bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/thirdparty_a2
cd $W/f007
run() { # label venv npm
  $W/f007/npm_sigterm_repro.sh $SB/envs/$2 $W/f007/app_$1 3501 8501 $3 $W/logs/f007-$1.log > /dev/null 2>&1
  echo "== $1 (venv $2 npm=$3)"; grep -E "^### |RESULT|ports free|listeners on|node|defunct" $W/logs/f007-$1.log | cut -c1-170 | head -12
}
run a2-npm thirdparty_a2-a2 1
run a2-bun thirdparty_a2-a2 0
run a1-npm thirdparty-alpha 1
run s0912-npm thirdparty-stable 1
