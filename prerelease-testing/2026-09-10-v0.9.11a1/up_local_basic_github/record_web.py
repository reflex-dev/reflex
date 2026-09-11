"""Dump a version-diffable snapshot of an app's compiled `.web` tree (no server needed).

usage: record_web.py <app_dir> <out_dir>

Writes into <out_dir>:
  package.json                 copy of .web/package.json
  installed_versions.json      name -> version from .web/node_modules/<pkg>/package.json
  web_tree.txt                 sorted relative paths of .web/{app,public,utils} (excl. node_modules)
  public_files.txt             sorted listing of .web/public plus sha256 of each file
  memo_modules.txt             sorted list of generated memo modules + their exported names
  asset_imports.txt            every compiled import that points at /public/
  lockfile_version.txt         lockfileVersion of every bun.lock found (app + reflex.lock)
"""

import hashlib
import json
import re
import sys
from pathlib import Path

APP = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
WEB = APP / ".web"

pkg = WEB / "package.json"
if pkg.exists():
    (OUT / "package.json").write_text(pkg.read_text())

versions = {}
nm = WEB / "node_modules"
if nm.is_dir():
    for name in sorted(p.name for p in nm.iterdir() if not p.name.startswith(".")):
        cands = (
            [nm / name]
            if not name.startswith("@")
            else sorted(p for p in (nm / name).iterdir() if p.is_dir())
        )
        for c in cands:
            pj = c / "package.json"
            if pj.exists():
                try:
                    versions[str(c.relative_to(nm))] = json.loads(pj.read_text()).get("version")
                except Exception:  # noqa: BLE001
                    versions[str(c.relative_to(nm))] = "?"
(OUT / "installed_versions.json").write_text(json.dumps(versions, indent=2, sort_keys=True))

tree, public, memos, assets = [], [], [], []
for sub in ("app", "app_components", "components", "public", "utils", "styles"):
    root = WEB / sub
    if not root.is_dir():
        continue
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(WEB))
            tree.append(rel)
            if sub == "public":
                public.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()[:16]}  {rel}")
            if p.suffix in (".js", ".jsx", ".ts", ".tsx"):
                text = p.read_text(errors="replace")
                for m in re.finditer(r"""from\s+["']([^"']*\/public\/[^"']*)["']""", text):
                    assets.append(f"{rel}: {m.group(1)}")
                if rel.startswith("app_components/") or rel.startswith("components/"):
                    names = sorted(set(re.findall(r"export\s+(?:function|const)\s+(\w+)", text)))
                    memos.append(f"{rel}: {','.join(names)}")
(OUT / "web_tree.txt").write_text("\n".join(tree) + "\n")
(OUT / "public_files.txt").write_text("\n".join(public) + "\n")
(OUT / "memo_modules.txt").write_text("\n".join(sorted(memos)) + "\n")
(OUT / "asset_imports.txt").write_text("\n".join(sorted(assets)) + "\n")

locks = []
for lock in sorted(APP.rglob("bun.lock")):
    if "node_modules" in str(lock):
        continue
    try:
        first = lock.read_text(errors="replace")[:400]
        m = re.search(r'"lockfileVersion"\s*:\s*(\d+)', first)
        locks.append(f"{lock.relative_to(APP)}: lockfileVersion={m.group(1) if m else '?'}")
    except Exception as e:  # noqa: BLE001
        locks.append(f"{lock}: {e}")
mm = WEB / ".memo-manifest.json"
if mm.exists():
    (OUT / "memo-manifest.json").write_text(mm.read_text())
(OUT / "lockfile_version.txt").write_text("\n".join(locks) + "\n")
print(f"recorded {APP} -> {OUT}: {len(tree)} files, {len(versions)} node packages, {len(memos)} memo modules")
