#!/usr/bin/env bash
# cli_seq.sh <venv-key> <appdir> <cmd>...   each cmd is "reflex:<args>" or "alembic:<args>"; prints output (trimmed) + rc
. "$(dirname "$0")/env.sh"; K=$1; A=$2; shift 2
for c in "$@"; do
  tool=${c%%:*}; args=${c#*:}; echo "### $tool $args"
  if [ $tool = reflex ]; then rx $K $A $args; else al $K $A $args; fi 2>&1 | grep -v -E 'alembic.runtime.plugins|^\s+File |^\s+\^|^\s{4}' | cut -c1-260 | tail -${TAILN:-12}
done
ls $A/alembic $A/alembic/versions 2>/dev/null | tr '\n' ' '; echo
