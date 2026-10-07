"""reflex-dynoselect 0.1.0: build the component, print the first failure.

Usage: <venv>/bin/python derive_a_dynoselect.py <expected-venv-name>
"""

import sys
import traceback
import warnings

warnings.simplefilter("ignore")
import reflex as rx  # noqa: E402

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
import reflex_dynoselect  # noqa: E402

try:
    comp = reflex_dynoselect.dynoselect(options=[{"label": "A", "value": "a"}])
    print("built:", type(comp).__name__, str(comp)[:120])
except Exception as e:  # noqa: BLE001
    tb = traceback.extract_tb(e.__traceback__)
    frame = next((f for f in reversed(tb) if "reflex_dynoselect" in f.filename), tb[-1])
    print(f"EXC {type(e).__name__}: {str(e)[:220]}\n  at {frame.filename.split('site-packages/')[-1]}:{frame.lineno}: {frame.line}")
