#!/bin/bash
# pyright + ty on fd_probe.py / fd_probe2.py for one venv: run_probes.sh <venv-name>
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
V=$SB/envs/$1; cd "$(dirname "$0")"
for f in fd_probe.py fd_probe2.py; do
  echo "== pyright $1 $f"; $V/bin/pyright --pythonpath $V/bin/python $f 2>&1 | grep -E "error|information" | sed "s/^.*$f://" | cut -c1-220
  echo "== ty $1 $f"; $V/bin/ty check --python $V --output-format concise $f 2>&1 | grep -E "error|revealed" | sed "s/^.*$f://" | cut -c1-220
done
