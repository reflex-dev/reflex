"""Rewrite .web/package.json exactly as sync_root_package_json_to_web() renders it."""
from pathlib import Path

import reflex

assert "/envs/" in reflex.__file__, reflex.__file__
from reflex.utils import frontend_skeleton as fs  # noqa: E402

p = Path(".web/package.json")
before = p.read_text()
rendered = fs._compile_package_json()
p.write_text(rendered)
print("reflex:", reflex.__file__)
print("rewrote (was different):", before != rendered)
