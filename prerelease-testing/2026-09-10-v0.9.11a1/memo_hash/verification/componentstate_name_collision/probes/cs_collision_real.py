"""Independent verification: two same-named rx.ComponentState subclasses in
two REAL on-disk modules (regular import, no exec/types.ModuleType tricks).

Usage: <venv>/bin/python probes/cs_collision_real.py <venv-name>
"""

import sys

import reflex

VENV = sys.argv[1] if len(sys.argv) > 1 else "smoke"
assert f"/envs/{VENV}/" in reflex.__file__, reflex.__file__
print("reflex", reflex.constants.Reflex.VERSION, reflex.__file__)

from pkg_one.widget import Counter as CounterOne  # noqa: E402
from pkg_two.widget import Counter as CounterTwo  # noqa: E402

print("modules:", CounterOne.__module__, CounterTwo.__module__)
print("qualnames:", CounterOne.__qualname__, CounterTwo.__qualname__)
print("distinct classes:", CounterOne is not CounterTwo)

for label, klass in (("one", CounterOne), ("two", CounterTwo)):
    try:
        c = klass.create()
        print(f"{label:4s} ok  -> {c.State.get_full_name()}")
    except Exception as e:  # noqa: BLE001
        print(f"{label:4s} ERR {type(e).__name__}: {e}")
