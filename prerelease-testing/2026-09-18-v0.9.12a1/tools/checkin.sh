#!/bin/bash
# Campaign check-in helper: workflow journal summary, live servers with ports, disk, leaked processes.
WF=${1:-/root/.claude/projects/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/subagents/workflows}
echo "=== $(date -u +%H:%M:%SZ) load: $(cut -d' ' -f1-3 /proc/loadavg)  mem free: $(free -g | awk '/Mem/{print $7}')G  disk avail: $(df -h /tmp | awk 'NR==2{print $4}')"
for j in $WF/*/journal.jsonl; do
  [ -f "$j" ] || continue
  echo "--- $(basename $(dirname $j)): $(grep -c '"type":"started"' $j) started, $(grep -c '"type":"result"' $j) results, $(grep -c '"type":"error"' $j) errors"
  jq -r --slurpfile all $j 'select(.type=="result") | .agentId as $id | "  done  " + (([$all[] | select(.type=="started" and .agentId==$id) | .label][0]) // "?") + "  tests=" + ((.result.tests // []) | length | tostring) + " issues=" + ((.result.issues // []) | length | tostring) + " verdicts=" + ((.result.verdicts // []) | length | tostring)' $j 2>/dev/null
  comm -23 <(jq -r 'select(.type=="started") | .agentId + " " + .label' $j | sort) <(jq -r --slurpfile all $j 'select(.type=="result" or .type=="error" or .type=="skipped") | .agentId as $id | .agentId + " " + (([$all[] | select(.type=="started" and .agentId==$id) | .label][0]) // "?")' $j | sort) | cut -d' ' -f2- | sed 's/^/  running  /'
done
echo "--- live servers (pid etimes rss cmd port):"
python3 /tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/bin/ports.py | sed 's/^/  /'
echo "--- reflex-ish processes: $(ps -eo args | grep -cE '^[^ ]*(python|node|bun)[^ ]* .*(reflex run|granian|vite|react-router)' )"
echo "--- redis: $(pgrep -a redis-server | cut -c1-80 | tr '\n' ';')"
echo "--- apps disk: $(du -sh /tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/apps 2>/dev/null | cut -f1)  envs: $(du -sh /tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/envs 2>/dev/null | cut -f1)"
echo "--- artifacts dirs: $(ls /home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/ | tr '\n' ' ')"
