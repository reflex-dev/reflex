"""Record immutable build asset identities and independent gzip estimates."""

import gzip
import hashlib
import json
import sys
from pathlib import Path

app, out = map(Path, sys.argv[1:])
root = app / ".web/build/client"
assets = []
for path in sorted(root.rglob("*")):
    if path.is_file():
        raw = path.read_bytes()
        assets.append(
            {
                "path": str(path.relative_to(root)),
                "bytes": len(raw),
                "gzip_estimate_bytes": len(gzip.compress(raw, mtime=0)),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
package_json = json.loads((app / ".web/package.json").read_text())
actual = {}
for name in package_json.get("dependencies", {}):
    p = app / ".web/node_modules" / name / "package.json"
    if p.exists():
        actual[name] = json.loads(p.read_text()).get("version")
result = {
    "app": str(app),
    "asset_root": str(root),
    "assets": assets,
    "package_json": package_json,
    "actual_frontend_versions": actual,
}
for kind in (".js", ".css"):
    entries = [a for a in assets if a["path"].endswith(kind)]
    result[kind] = {
        "files": len(entries),
        "raw_bytes": sum(a["bytes"] for a in entries),
        "gzip_estimate_bytes": sum(a["gzip_estimate_bytes"] for a in entries),
    }
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=1))
print(json.dumps({k: result[k] for k in (".js", ".css")}))
