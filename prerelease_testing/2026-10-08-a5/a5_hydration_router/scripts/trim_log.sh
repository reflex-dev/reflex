#!/bin/bash
# trim_log.sh <log> -> $W/trimmed/<basename>.trimmed.log : startup head, warnings/errors/tracebacks, H4TRACE lines (max 400), tail
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a5_hydration_router
L=$1; O=$W/trimmed/$(basename $L .log).trimmed.log; mkdir -p $W/trimmed
{ echo "### head"; grep -v "^Debug" $L | head -25; echo "### warnings/errors (deduped, with counts)"; grep -E "WARN|Warning|ERROR|Error|Traceback|panicked|Exception" $L | sed 's/[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f-]*/<TOKEN>/g' | sort | uniq -c | sort -rn | head -60;
  echo "### H4TRACE (first 400)"; grep "H4TRACE" $L | head -400; echo "### tail"; tail -30 $L; } > $O
echo "$O $(wc -c < $O) bytes"
