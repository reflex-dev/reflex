"""Version-independent docs-sample runner: execute every ```python block of the given Markdown pages, in page order, in one
namespace per page (as the docs site does for `exec` blocks), and print one line per block: OK or the exception.

Point it at the docs of the version under test and of the previous release and diff the two outputs; a block that turns
from OK to EXC (or a new EXC) is a docs/behaviour drift to look at. probes/probe_docs.py holds the hand-checked statements.
Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I docs_blocks.py <page.md>...
  e.g. <docs>/vars/base_vars.md <docs>/state_structure/component_state.md <docs>/changelog/upgrading/upgrading-to-0-10.md
"""

import os
import re
import sys
import traceback

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__

FENCE = re.compile(r"^```python([^\n]*)\n(.*?)^```", re.M | re.S)

for page in sys.argv[1:]:
    text = open(page, encoding="utf-8").read()
    ns = {"rx": rx, "__name__": f"docs_{os.path.basename(page).replace('-', '_').removesuffix('.md')}"}
    print(f"== {page}")
    for i, m in enumerate(FENCE.finditer(text), 1):
        line = text.count("\n", 0, m.start()) + 1
        tags, code = m.group(1).strip() or "-", m.group(2)
        try:
            exec(compile(code, f"{page}:{line}", "exec"), ns)  # noqa: S102
            res = "OK"
        except BaseException as e:  # noqa: BLE001
            # the last frame inside the block: its line relative to the block
            rel = [f.lineno for f in traceback.extract_tb(e.__traceback__) if f.filename == f"{page}:{line}"]
            msg = str(e).splitlines()[0][:200] if str(e) else ""
            res = f"EXC {type(e).__name__}: {msg}" + (f" (block line {rel[-1]})" if rel else "")
        print(f"BLOCK {i:>2} line {line:>4} [{tags}] {res}", flush=True)
