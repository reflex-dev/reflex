"""Does rx.Model / rx.session work on a fresh reflex[db] install?  Usage: <venv>/bin/python gl_probe.py <venv-name>"""
import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print("reflex", version("reflex"), "sqlalchemy", version("sqlalchemy"), "sqlmodel", version("sqlmodel"))
for label, code in [
    ("rx.Model", "rx.Model"),
    ("import reflex.model", "__import__('reflex.model')"),
    ("rx.session", "rx.session"),
    ("import sqlmodel; plain SQLModel table", "__import__('sqlmodel')"),
]:
    try:
        eval(code)
        print(f"{label:40} OK")
    except Exception as e:  # noqa: BLE001
        print(f"{label:40} {type(e).__name__}: {str(e)[:160]}")
