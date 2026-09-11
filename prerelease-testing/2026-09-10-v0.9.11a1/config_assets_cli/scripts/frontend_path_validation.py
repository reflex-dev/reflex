"""#7044: rx.Config must reject frontend_path segments that are not plain
directory names, and keep accepting the legitimate ones."""
import sys

import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__

BAD = ["../x", "a\\b", "C:foo", "..", "/..", "/a/../b", "/a\\b", "/C:/x", "/.", "//x",
       "/\\\\server\\share", "/a/./b"]
GOOD = ["/myapp", "/a/b", "/", "", "/my-app", "/my.app", "/v1.2", "/a b"]

print("=== expected-invalid ===")
for fp in BAD:
    try:
        c = rx.Config(app_name="t", frontend_path=fp)
    except Exception as e:  # noqa: BLE001
        print(f"REJECTED {fp!r}: {type(e).__name__}: {e}")
    else:
        print(f"ACCEPTED {fp!r} -> {c.frontend_path!r}  <-- not rejected")
print("=== expected-valid ===")
for fp in GOOD:
    try:
        c = rx.Config(app_name="t", frontend_path=fp)
    except Exception as e:  # noqa: BLE001
        print(f"REJECTED {fp!r}: {type(e).__name__}: {e}  <-- unexpected")
    else:
        print(f"ACCEPTED {fp!r} -> {c.frontend_path!r}")
