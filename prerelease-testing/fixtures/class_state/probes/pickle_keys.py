"""Inspect a saved-state pickle WITHOUT reflex: which keys does the state dict carry?

Usage: <any python> -I pickle_keys.py <file.bin> [...]
Every class the pickle references is replaced by a stub that records its __setstate__ dict, so the output shows exactly
what a worker of any version would receive (schema hash + top-level keys + values repr).
"""
import io
import pickle
import sys


class Stub:
    def __setstate__(self, state):
        self.__dict__["_state"] = state


class U(pickle.Unpickler):
    def find_class(self, module, name):
        if module in ("builtins", "collections", "copyreg", "datetime", "decimal", "uuid"):
            return super().find_class(module, name)
        return type(f"{module}.{name}", (Stub,), {})


for path in sys.argv[1:]:
    data = open(path, "rb").read()
    schema, st = U(io.BytesIO(data)).load()
    state = st.__dict__.get("_state", st.__dict__)
    print(f"{path}: schema={schema} class={type(st).__name__}")
    for k in sorted(state):
        print(f"   {k!r:24} = {state[k]!r:.80}")
    for bad in ("dirty_vars", "dirty_substates", "_backend_vars", "_replaced_defaults"):
        print(f"   contains {bad!r}: {bad.encode() in data}")
