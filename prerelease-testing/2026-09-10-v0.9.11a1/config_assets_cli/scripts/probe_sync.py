"""Probe which lockfile sync reports a change (that deletes the install cache)."""
from pathlib import Path

import reflex  # noqa: F401
assert "/envs/" in reflex.__file__, reflex.__file__
from reflex.utils import frontend_skeleton as fs  # noqa: E402

print("reflex:", reflex.__file__)
print("cache exists before:", Path(".web/reflex.install_frontend_packages.cached").exists())
for name in fs.LOCKFILE_NAMES:
    print(f"  sync_root_lockfile_to_web({name!r}) ->", fs.sync_root_lockfile_to_web(name))
print("  sync_root_package_json_to_web() ->", fs.sync_root_package_json_to_web())
print("  again sync_root_package_json_to_web() ->", fs.sync_root_package_json_to_web())
