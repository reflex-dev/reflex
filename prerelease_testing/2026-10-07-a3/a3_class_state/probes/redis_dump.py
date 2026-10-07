"""Dump every redis key's pickle (schema hash + top-level state keys) without importing reflex classes. Usage: redis_dump.py <port>"""
import io, pickle, sys
import redis

class Stub:
    def __setstate__(self, state):
        self.__dict__["_state"] = state

class U(pickle.Unpickler):
    def find_class(self, module, name):
        if module in ("builtins", "collections", "copyreg", "datetime", "decimal", "uuid"):
            return super().find_class(module, name)
        return type(f"{module}.{name}", (Stub,), {})

r = redis.Redis(port=int(sys.argv[1]))
for k in sorted(r.keys("*")):
    t = r.type(k).decode()
    if t != "string":
        print(f"{k.decode()[:90]} ({t})")
        continue
    v = r.get(k)
    try:
        schema, st = U(io.BytesIO(v)).load()
        state = st.__dict__.get("_state", st.__dict__)
        print(f"{k.decode()[:90]}: schema={schema} keys={sorted(state)} values={ {kk: state[kk] for kk in sorted(state) if not kk.startswith('router')} }"[:400])
    except Exception as e:  # noqa: BLE001
        print(f"{k.decode()[:90]}: <{type(e).__name__}: {e}> len={len(v)}")
