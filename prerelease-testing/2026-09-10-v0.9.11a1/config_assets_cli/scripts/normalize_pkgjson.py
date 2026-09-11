"""Write .web/package.json in exactly the form sync_root_package_json_to_web()
renders, so the frontend-install cache is not invalidated by pure formatting."""
from pathlib import Path

import reflex  # noqa: F401
assert "/envs/" in reflex.__file__, reflex.__file__
from reflex.utils import frontend_skeleton as fs  # noqa: E402

p = Path(".web/package.json")
before = p.read_text()
rendered = fs._compile_package_json()
p.write_text(rendered)
print("changed:", before != rendered)
