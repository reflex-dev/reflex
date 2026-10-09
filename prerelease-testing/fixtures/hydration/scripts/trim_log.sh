#!/bin/bash
# trim_log.sh <log> -> $W/trimmed/<basename>.trimmed.log : startup head, warnings/errors/tracebacks (deduped, counts),
# H4TRACE lines (max 400), tail.
. "$(dirname "$0")/env.sh"
L=$1; O=$W/trimmed/$(basename "$L" .log).trimmed.log; mkdir -p "$W/trimmed"
{ echo "### head"; grep -v "^Debug" "$L" | head -25; echo "### warnings/errors (deduped, with counts)"; grep -E "WARN|Warning|ERROR|Error|Traceback|panicked|Exception" "$L" | sed 's/[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f-]*/<TOKEN>/g' | sort | uniq -c | sort -rn | head -60;
  echo "### H4TRACE (first 400)"; grep "H4TRACE" "$L" | head -400; echo "### tail"; tail -30 "$L"; } > "$O"
echo "$O $(wc -c < "$O") bytes"
