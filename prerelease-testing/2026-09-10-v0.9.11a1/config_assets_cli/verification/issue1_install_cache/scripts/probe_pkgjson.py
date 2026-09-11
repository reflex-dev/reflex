"""Show why the frontend install cache is dropped: rendered vs on-disk .web/package.json."""
import json
from pathlib import Path

import reflex

assert "/envs/" in reflex.__file__, reflex.__file__
from reflex.utils import frontend_skeleton as fs  # noqa: E402

print("reflex:", reflex.__file__)
disk = Path(".web/package.json").read_text()
rendered = fs._compile_package_json()
print("text identical      :", disk == rendered)
print("JSON-equal          :", json.loads(disk) == json.loads(rendered))
print("disk    len/lines   :", len(disk), disk.count("\n") + 1)
print("rendered len/lines  :", len(rendered), rendered.count("\n") + 1)
print("rendered head       :", rendered[:120])
print("cache file exists   :", Path(".web/reflex.install_frontend_packages.cached").exists())
