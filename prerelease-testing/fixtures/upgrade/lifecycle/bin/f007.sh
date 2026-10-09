#!/usr/bin/env bash
# F-007: `reflex run` under npm ignores SIGTERM without a TTY on Linux (orphaned node keeps the frontend port); bun exits.
# Usage: f007.sh [venv-name]  (default $NEW). Runs npm then bun on FP/BP (3512/8512) in fresh blank apps under lifecycle/run/.
# Expected (0.9.12 .. 0.10.0a2, Linux, still open): npm -> "RESULT: reflex CLI STILL RUNNING 30s after SIGTERM", bun -> "RESULT: reflex CLI exited".
set -u; . "$(dirname "$0")/../../bin/env.sh"; L=$(cd "$(dirname "$0")/.." && pwd); V=${1:-$NEW}; FP=${FP:-3512}; BP=${BP:-8512}
mkdir -p "$L/logs"
for npm in 1 0; do
  "$L/bin/npm_sigterm_repro.sh" "$SB/envs/$V" "$L/run/f007-$V-npm$npm" $FP $BP $npm "$L/logs/f007-$V-npm$npm.log" | grep -E '^(###|RESULT|  ports free|.*:'$FP')'
done
