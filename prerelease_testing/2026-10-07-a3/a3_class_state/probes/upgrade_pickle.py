"""a3 loads pickles written by 0.9.12 / 0.10.0a2 (schema_matrix saves): instance dict, dirty tracking, re-serialization.
Usage (cwd = orig/rc_scripts/schema for schema_mod): SCHEMA_DEFAULT=0 <venv>/bin/python -I upgrade_pickle.py <venv> <file>..."""
import os, sys
sys.path.insert(0, os.getcwd())
import reflex as rx
assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version
import schema_mod
print("reflex", version("reflex"))
for path in sys.argv[2:]:
    s = schema_mod.SchemaState._deserialize(open(path, "rb").read())
    inst = sorted(vars(s))
    print(f"{os.path.basename(path)}: count={s.count} _secret={s._secret!r} dirty_vars={set(s.dirty_vars)} dirty_substates={set(s.dirty_substates)} instance-dict keys={inst}")
    s.count += 1
    s._secret = "changed"
    print(f"   after mutation dirty_vars={set(s.dirty_vars)}")
    data = s._serialize()
    print(f"   re-serialized: stale keys present={[k for k in ('dirty_vars', 'dirty_substates', '_backend_vars', '_reflex_internal_links', 'router_data', '_replaced_defaults') if k.encode() in data]}")
    s2 = schema_mod.SchemaState._deserialize(data)
    print(f"   reload: count={s2.count} _secret={s2._secret!r}")
