#!/bin/bash
# Usage: run_probe.sh <venv-name> <dev|prod>   (each check runs in its own interpreter)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
V=$1; M=$2
cd "$(dirname "$0")"
CHECKS="shadowed_get_fields init_override slots_state undeclared_assignment compile_time_setvar_backend_name late_supersedes_marker background_marker_without_read self_handler_instance_access telemetry_walk_then_late_marker"
for n in items dict reset router setvar get_state substates parent_state dirty_vars get_value is_hydrated event_handlers vars fields; do CHECKS="$CHECKS var_named_$n"; done
for c in $CHECKS; do
  REFLEX_TELEMETRY_ENABLED=false timeout 120 $SB/envs/$V/bin/python state_api_probe.py $V $M $c 2>&1 | grep '^{' || echo "{\"check\": \"$c\", \"venv\": \"$V\", \"mode\": \"$M\", \"error\": \"no output\"}"
done
