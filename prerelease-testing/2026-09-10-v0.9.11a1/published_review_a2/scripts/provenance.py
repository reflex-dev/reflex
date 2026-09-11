"""Record exactly what an environment is, before any reproduction runs.

Usage: python provenance.py <label> <out.json>
"""

import importlib
import importlib.metadata as md
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

label, out = sys.argv[1], sys.argv[2]
info = {
    "label": label,
    "recorded_at_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
    "sys_executable": sys.executable,
    "python_version": sys.version,
    "sys_path": sys.path,
    "platform": platform.platform(),
    "env_PYTHONPATH": os.environ.get("PYTHONPATH"),
}

dists = {}
local_origins = []
for d in md.distributions():
    name = d.metadata["Name"]
    if not name or not (name.startswith("reflex") or name in {"granian", "starlette", "starlette-admin", "redis", "pyright", "opentelemetry-sdk"}):
        continue
    dists[name] = d.version
    du = d.read_text("direct_url.json")
    if du:
        local_origins.append({name: json.loads(du)})
info["distributions"] = dict(sorted(dists.items()))
info["direct_url_json"] = local_origins

mods = {}
for m in ("reflex", "reflex_base", "reflex_components_moment", "reflex_components_radix"):
    try:
        mods[m] = importlib.import_module(m).__file__
    except Exception as e:  # noqa: BLE001
        mods[m] = f"<{type(e).__name__}: {e}>"
info["module_files"] = mods

prefix = sys.prefix
info["all_modules_under_env"] = all(
    isinstance(f, str) and f.startswith(prefix) for f in mods.values() if not f.startswith("<")
)
info["env_prefix"] = prefix

for tool, cmd in (("node", ["node", "--version"]), ("bun_system", ["bun", "--version"]),
                  ("redis", ["redis-server", "--version"]), ("chromium", ["/opt/pw-browsers/chromium", "--version"])):
    try:
        info[tool] = subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()[:120]
    except Exception as e:  # noqa: BLE001
        info[tool] = f"<{type(e).__name__}>"

# the Bun that reflex actually manages
try:
    from reflex_base import constants  # noqa: PLC0415

    bun_path = getattr(getattr(constants, "Bun", None), "DEFAULT_PATH", None)
    info["reflex_managed_bun_path"] = str(bun_path)
    if bun_path and Path(bun_path).exists():
        info["reflex_managed_bun_version"] = subprocess.run([str(bun_path), "--version"], capture_output=True, text=True).stdout.strip()
except Exception as e:  # noqa: BLE001
    info["reflex_managed_bun_path"] = f"<{type(e).__name__}: {e}>"

Path(out).write_text(json.dumps(info, indent=1))
print(json.dumps({k: info[k] for k in ("label", "sys_executable", "distributions", "all_modules_under_env",
                                       "direct_url_json", "node", "reflex_managed_bun_version")}, indent=1)[:1400])
