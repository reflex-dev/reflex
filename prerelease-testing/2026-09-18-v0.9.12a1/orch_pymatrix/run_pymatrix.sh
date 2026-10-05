#!/bin/bash
# Python version matrix for the published 0.9.12a1 train: install, import, lazy-loader path, dev server + browser page load.
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
P=$SB/apps/orch_pymatrix; DRV=$SB/envs/driver/bin/python; DRIVE=/home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py
export REFLEX_TELEMETRY_ENABLED=false UV_SYSTEM_CERTS=1; unset UV_NATIVE_TLS
SPECS="reflex==0.9.12a1 reflex-components-core==0.9.10a1 reflex-components-radix==0.9.10a1 reflex-components-code==0.9.6a1 reflex-components-dataeditor==0.9.3a1 reflex-components-gridjs==0.9.2a1 reflex-components-markdown==0.9.4a1 reflex-components-plotly==0.9.7a1 reflex-components-recharts==0.9.4a1 reflex-components-sonner==0.9.4a1"
i=0
for py in 3.10 3.14 3.15; do
  i=$((i+1)); FP=$((3052+i)); BP=$((8052+i)); V=$SB/envs/py$py; A=$P/app$py
  echo "=============== python $py (ports $FP/$BP) ==============="
  cd $SB && uv venv $V --python $py >/dev/null 2>&1 || { echo "[$py] venv creation FAILED"; continue; }
  if ! uv pip install --python $V/bin/python --prerelease=allow $SPECS > $P/logs/install_$py.log 2>&1; then echo "[$py] INSTALL FAILED:"; grep -iE "error|no solution|because|failed" $P/logs/install_$py.log | head -8; continue; fi
  echo "[$py] installed: $(uv pip freeze --python $V/bin/python | grep -E '^reflex==|^reflex-base==|^pydantic==|^granian==' | tr '\n' ' ')"
  $V/bin/python - <<'PY' 2>&1 | sed "s/^/[$py] /"
import sys, time, reflex
assert "/envs/py" in reflex.__file__, reflex.__file__
print("python", sys.version.split()[0], "reflex", reflex.constants.Reflex.VERSION)
import reflex_base.utils.lazy_loader as ll
print("lazy_loader native PEP 810 path:", getattr(ll, "_NATIVE_LAZY_IMPORTS", "n/a"))
t=time.perf_counter(); reflex.text; first=time.perf_counter()-t
t=time.perf_counter()
for _ in range(1_000_000): reflex.text
print(f"rx.text first access {first*1e3:.2f} ms; 1e6 repeated accesses {time.perf_counter()-t:.3f} s")
class S(reflex.State):
    n: int = 0
    @reflex.var
    def double(self) -> int: return self.n * 2
print("State subclass + computed var OK:", S.double)
PY
  rm -rf $A && mkdir -p $A && cd $A && $V/bin/reflex init --template blank --name pyapp > $P/logs/init_$py.log 2>&1; echo "[$py] init exit=$?"
  setsid $V/bin/reflex run --loglevel debug --frontend-port $FP --backend-port $BP > $P/logs/dev_$py.log 2>&1 &
  n=0; until curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$FP/ 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 300 ] && { echo "[$py] TIMEOUT waiting for dev server"; break; }; sleep 1; done; echo "[$py] frontend 200 after ${n}s"
  sleep 2
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $DRV $DRIVE http://localhost:$FP/ --actions '[{"wait":2000},{"expect_text":"Welcome to Reflex"}]' --report $P/logs/drive_$py.json > $P/logs/drive_$py.txt 2>&1; echo "[$py] drive exit=$? :: $(grep -E 'RESULT|expect_text' $P/logs/drive_$py.txt | tr '\n' ' ')"
  curl -s --noproxy '*' http://localhost:$BP/ping; echo " <- ping"
  grep -nE 'Traceback|Error|error' $P/logs/dev_$py.log | grep -viE 'npmmirror|exit code 143|errorBoundaries|error_boundary|onerror' | head -5 | sed "s/^/[$py] devlog: /"
  for p in $(python3 $SB/bin/ports.py $FP $BP | grep -oE 'pids=[0-9,]+' | cut -d= -f2 | tr ',' ' '); do pkill -KILL -P $p 2>/dev/null; kill -KILL $p 2>/dev/null; done; sleep 1
  python3 $SB/bin/ports.py $FP $BP >/dev/null && echo "[$py] ports free"
  rm -rf $A/.web
done
echo "PYMATRIX DONE"
