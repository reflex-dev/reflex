#!/usr/bin/env bash
# Upgrade-guide statements, Python level (probes/guide_probe.py: class reads of backend vars -> Field, BackendVarFormatError,
# changing defaults by class assignment, mutable defaults, background-task inherited handlers, undeclared attribute; dt_probe.py:
# tables.md datetime / sqlmodel >= 0.0.45 claims). Usage: probe.sh [venv ...] (default "$NEW $PREV"); writes guide/logs/probe-<venv>-<mode>.txt
# Expected on 0.10.x: every statement of docs/changelog/upgrading/upgrading-to-0-10.md holds (see README); on 0.9.12 the 0.9 claims hold.
set -u; . "$(dirname "$0")/../../bin/env.sh"; G=$(cd "$(dirname "$0")/.." && pwd); mkdir -p "$G/logs"; cd "$SB"
for v in ${@:-$NEW $PREV}; do
  for m in dev prod; do REFLEX_ENV_MODE=$m "$SB/envs/$v/bin/python" -I "$G/probes/guide_probe.py" "$v" > "$G/logs/probe-$v-$m.txt" 2>&1; echo "$v $m: $(wc -l < "$G/logs/probe-$v-$m.txt") lines, $(grep -c ' -> EXC' "$G/logs/probe-$v-$m.txt") EXC"; done
  "$SB/envs/$v/bin/python" -I "$G/probes/dt_probe.py" "$v" > "$G/logs/dt-$v.txt" 2>&1; echo "$v dt_probe: $(tail -1 "$G/logs/dt-$v.txt" | cut -c1-160)"
done
