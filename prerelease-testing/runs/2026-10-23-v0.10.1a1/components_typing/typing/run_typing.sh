#!/bin/bash
# Run pyright and ty on the typing modules under both venvs; outputs go to results/typing_*.txt
# usage: run_typing.sh  (from any cwd; SB must be set)
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/../results
mkdir -p "$OUT"
cd "$HERE"
NEW_ENV=${NEW_ENV:-components_typing-new}
PREV_ENV=${PREV_ENV:-components_typing-prev}
ENVS=${ENVS:-"new prev"}
for env in $ENVS; do
  case $env in new) V=$SB/envs/$NEW_ENV;; prev) V=$SB/envs/$PREV_ENV;; esac

  for mod in typing_user.py typing_new_api.py; do
    base=${mod%.py}
    echo "== pyright $env $mod"
    "$V/bin/pyright" --pythonpath "$V/bin/python" --outputjson "$mod" > "$OUT/typing_pyright_${env}_${base}.json" 2>/dev/null
    "$V/bin/python" - "$OUT/typing_pyright_${env}_${base}.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
for x in d["generalDiagnostics"]:
    print(f"  {x['severity']:8} L{x['range']['start']['line']+1}: {x['message'].splitlines()[0]}  [{x.get('rule','')}]")
s = d["summary"]; print(f"  summary: errors={s['errorCount']} warnings={s['warningCount']}")
EOF
    echo "== ty $env $mod"
    "$V/bin/ty" check --python "$V" --output-format concise "$mod" > "$OUT/typing_ty_${env}_${base}.txt" 2>&1
    sed 's/^/  /' "$OUT/typing_ty_${env}_${base}.txt"
  done
done
