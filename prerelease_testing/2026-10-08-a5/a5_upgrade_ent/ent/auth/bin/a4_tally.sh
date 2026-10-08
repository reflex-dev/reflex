#!/usr/bin/env bash
# Usage: a4_tally.sh <label>  -- pass counts per a4-matrix driver log + server-log tracebacks
A=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a5_upgrade_ent/ent/auth/a4auth/logs/$1
for f in auth-full reload-repeat auth-min-default iframe-repeat auth-min-extra; do
  p=$(grep -c '"passed": true' $A/$f-driver.log 2>/dev/null); n=$(grep -c '"passed": ' $A/$f-driver.log 2>/dev/null); echo "$f: $p/$n"
done
tail -n1 $A/mcp-oauth-driver.log; tail -n1 $A/mcp-anonymous-driver.log
for f in $A/*server.log; do echo "$(basename $f): tracebacks=$(grep -c Traceback $f)"; done
