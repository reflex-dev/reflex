"""Load a pickle saved by another reflex version while ignoring the schema hash, to see whether the hash is the ONLY incompatibility.

Usage: SCHEMA_DEFAULT=<n> <venv>/bin/python bypass_hash.py <expected-venv> <file>   (cwd = scripts/schema so schema_mod imports)
"""
import pickle
import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

import schema_mod  # noqa: E402

h, s = pickle.loads(open(sys.argv[2], "rb").read())
cls = schema_mod.SchemaState
print(f"reflex {version('reflex')}: stored hash={h} my _to_schema={cls._to_schema()} -> state loaded ignoring hash: count={s.count} label={s.label!r} _secret={s._secret!r} dirty_vars={getattr(s, 'dirty_vars', '?')}")
s.count += 1
s._secret = "changed"
print("  mutate ok: count", s.count, "dirty", getattr(s, "dirty_vars", "?"), "| re-serialize ok:", len(s._serialize()), "bytes")
