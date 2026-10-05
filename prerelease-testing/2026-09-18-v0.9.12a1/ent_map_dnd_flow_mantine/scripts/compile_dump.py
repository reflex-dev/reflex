"""Compile an app's frontend pages offline (no bun, no licence gate) and copy the JS out.

Usage: python compile_dump.py <app_dir> <out_dir> <expected_venv_marker>
"""

import os
import shutil
import sys
from pathlib import Path

app_dir, out_dir, marker = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ["CI"] = "true"
os.environ["REFLEX_TELEMETRY_ENABLED"] = "false"
os.chdir(app_dir)
sys.path.insert(0, app_dir)

import reflex  # noqa: E402

assert marker in reflex.__file__, reflex.__file__
print("REFLEX", reflex.__file__)

from reflex.compiler.compiler import compile_app  # noqa: E402
from reflex.utils.prerequisites import get_and_validate_app  # noqa: E402

app = get_and_validate_app(reload=False).app
app._apply_decorated_pages()
compile_app(app, use_rich=False)

web = Path(app_dir) / ".web"
out = Path(out_dir)
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
for sub in ("pages", "utils", "components"):
    src = web / sub
    if src.exists():
        shutil.copytree(src, out / sub, ignore=shutil.ignore_patterns("node_modules"))
print("WROTE", out)
