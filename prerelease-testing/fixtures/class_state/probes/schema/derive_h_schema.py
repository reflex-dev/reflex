"""Save/load a state across processes and reflex versions to check the saved-state schema.

Usage: SCHEMA_DEFAULT=<n> <venv>/bin/python derive_h_schema.py <expected-venv-name> save|load <file>
"""

import sys

import reflex as rx

assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

import schema_mod  # noqa: E402

mode, path = sys.argv[2], sys.argv[3]
cls = schema_mod.SchemaState
tag = f"reflex {version('reflex')} default={cls.get_fields()['count'].default}"
if mode == "save":
    s = rx.State(_reflex_internal_init=True).get_substate(cls.get_full_name().split(".")[1:])
    s.count = 42
    s.label = "saved"
    open(path, "wb").write(s._serialize())
    print(f"{tag}: saved count=42 schema={s._to_schema()}")
else:
    try:
        s = cls._deserialize(open(path, "rb").read())
        print(f"{tag}: LOADED count={s.count} label={s.label!r} _secret={s._secret!r}")
    except Exception as e:  # noqa: BLE001
        print(f"{tag}: {type(e).__name__}: {e}")
