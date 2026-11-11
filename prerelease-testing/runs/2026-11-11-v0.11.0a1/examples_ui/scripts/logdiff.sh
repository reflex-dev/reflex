#!/usr/bin/env bash
# logdiff.sh <a.log> <b.log>: server-log lines (joined rich-wrapped, timestamps/paths/hashes/ports/pids normalized)
# present in b but not in a.  Used to list NEW messages a user sees after the upgrade.
norm() { tr '\n' '\001' < "$1" | sed -E 's/\x01(Debug:|Info:|Warning:|Error:|DeprecationWarning|\[|─|\x01)/\n\1/g; s/\x01/ /g' \
  | sed -E 's/[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?//g; s#/tmp/claude-0/[^ ]*scratchpad#<SB>#g; s/[0-9a-f]{32}/<h>/g; s/[0-9a-f]{8}-[0-9a-f-]{27}/<tok>/g; s/pid[= ][0-9]+/pid/g; s/ +/ /g; s/[0-9]+(\.[0-9]+)?(ms|s)\b/<t>/g' \
  | grep -vE '^\s*$' | sort -u; }
comm -13 <(norm "$1") <(norm "$2")
