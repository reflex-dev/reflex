import sys
import traceback

import reflex

assert "site-packages" in reflex.__file__ and "/envs/" in reflex.__file__, reflex.__file__
print(f"### reflex.__file__ = {reflex.__file__}")
import reflex as rx  # noqa: E402

print(f"### version = {rx.constants.Reflex.VERSION}")

sys.path.insert(0, ".")
from badser.badser import app  # noqa: E402

try:
    app._compile()
    print("COMPILE: no error")
except BaseException as e:  # noqa: BLE001
    tb = traceback.format_exc()
    real = "p.why" in tb or "serialize_point" in tb or "'why'" in tb
    print(f"COMPILE ERROR: {type(e).__module__}.{type(e).__name__}: {e}")
    print(f"COMPILE __cause__={e.__cause__!r} __context__={e.__context__!r}")
    print(f"COMPILE real_bug_visible={real}")
    print("---- traceback ----")
    print(tb.rstrip())
