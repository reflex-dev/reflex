#!/bin/bash
# Edit the app 25 times under a live `reflex run` and sample every reflex python
# process's RSS after each reload. Usage: hot_edit_rss.sh <app_dir> <out.csv> [n]
set -u
APP="$1"; OUT="$2"; N="${3:-25}"
F="$APP/memoapp/common.py"
cp "$F" "$F.orig"
echo "iter,pid,rss_kb,etime,note" > "$OUT"
sample() {
  local it="$1" note="$2"
  ps -eo pid,rss,etime,cmd --no-headers \
    | grep "[r]eflex run --frontend-port" | grep -v "/bin/bash" \
    | while read -r pid rss etime rest; do echo "$it,$pid,$rss,$etime,$note" >> "$OUT"; done
}
sample 0 baseline
for i in $(seq 1 "$N"); do
  python3 - "$F" "$i" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); i = sys.argv[2]
s = p.read_text()
marker = '    label: str = "'
lines = s.splitlines(True)
for n, ln in enumerate(lines):
    if ln.startswith(marker):
        lines[n] = f'    label: str = "shared{i}"\n'
        break
p.write_text("".join(lines))
PY
  sleep 6
  sample "$i" edit
done
cp "$F.orig" "$F"; rm -f "$F.orig"
sleep 6
sample 999 restored
