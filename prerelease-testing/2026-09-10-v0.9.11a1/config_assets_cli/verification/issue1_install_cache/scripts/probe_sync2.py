"""After normalizing .web/package.json, does sync still report a change?"""
from pathlib import Path
import reflex
assert "/envs/" in reflex.__file__, reflex.__file__
from reflex.utils import frontend_skeleton as fs  # noqa: E402

print("reflex:", reflex.__file__)
p = Path(".web/package.json")
p.write_text(fs._compile_package_json())
for name in fs.LOCKFILE_NAMES:
    print(f"  sync_root_lockfile_to_web({name!r}) ->", fs.sync_root_lockfile_to_web(name))
print("  sync_root_package_json_to_web() ->", fs.sync_root_package_json_to_web())
print("  sync_root_lockfiles_to_web()   ->", fs.sync_root_lockfiles_to_web())
