"""Dev guard: a locally defined state renamed by _handle_local_def (name clash) still accepts its own mangled names."""
import os
import reflex as rx
assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version
print("reflex", version("reflex"), os.environ.get("REFLEX_ENV_MODE"))


def make():
    class Loc(rx.State):
        def w(self):
            self.__z = 1
            return self.__z
    return Loc


for i in range(3):
    L = make()
    try:
        r = L(_reflex_internal_init=True).w()
    except Exception as e:  # noqa: BLE001
        r = f"{type(e).__name__}: {str(e)[:100]}"
    print(f"#{i}: __name__={L.__name__} __original_name__={L.__dict__.get('__original_name__')} -> {r}")
