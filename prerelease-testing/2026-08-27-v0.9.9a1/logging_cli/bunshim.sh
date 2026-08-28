#!/bin/bash
LOG=/tmp/claude-0/-home-user-reflex/20b6ffc8-8244-5bac-b158-8501871b3811/scratchpad/apps/logging_cli/logs/bunshim.log
{
  echo "=== bun invocation: $(date +%T) pid=$$ ppid=$PPID"
  echo "args: $*"
  echo "cwd: $(pwd)"
} >> "$LOG"
/root/.bun/bin/bun "$@" 2> >(tee -a "$LOG" >&2)
rc=$?
echo "=== rc=$rc" >> "$LOG"
exit $rc
