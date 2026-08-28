"""Script-level check for #6830: state manager instances get isolated locks.

Run with any venv's python that has the reflex under test installed, from a
cwd OUTSIDE the /home/user/reflex checkout:

    <venv>/bin/python check_lock_isolation.py

Pre-#6830 the dataclass field used ``default=asyncio.Lock()`` -- one Lock
object shared by every instance of the class (and created at import time on
whatever loop was current). Post-fix it is ``default_factory=asyncio.Lock``.
"""

import dataclasses
import importlib.metadata

from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.redis import StateManagerRedis

print("reflex version:", importlib.metadata.version("reflex"))

failures = []
for cls in (StateManagerMemory, StateManagerDisk, StateManagerRedis):
    field = next(
        f for f in dataclasses.fields(cls) if f.name == "_state_manager_lock"
    )
    uses_factory = field.default_factory is not dataclasses.MISSING
    print(f"{cls.__name__}._state_manager_lock uses default_factory: {uses_factory}")
    if not uses_factory:
        failures.append(f"{cls.__name__} shares a class-level lock (pre-#6830)")

a = StateManagerMemory()
b = StateManagerMemory()
isolated = a._state_manager_lock is not b._state_manager_lock
print("two StateManagerMemory instances have distinct locks:", isolated)
if not isolated:
    failures.append("StateManagerMemory instances share one lock object")

if failures:
    print("FAIL:", failures)
    raise SystemExit(1)
print("PASS")
