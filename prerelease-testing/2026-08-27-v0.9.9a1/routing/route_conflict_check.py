"""Compile-time route-conflict checks for #6953 (no server needed).

Run from inside a reflex app dir (rxconfig.py present):
    <venv>/bin/python route_conflict_check.py

Each check runs in a fresh subprocess (one rx.App per process, portable
across reflex 0.9.8 and 0.9.9). Checks:
  1. /posts/[id] added first, then /posts/all/[x]  -> must NOT raise (6953)
  2. /posts/all/[x] added first, then /posts/[id]  -> must NOT raise (6953)
  3. /posts/[id] + /posts/[foo]                    -> MUST raise (real conflict)
  4. /posts/[id] + /posts/[[...splat]]             -> MUST raise (real conflict)
  5. /posts/all + /posts/[id] (no-bracket static sibling, both orders) -> no raise
"""

import subprocess
import sys

CHECKS = [
    ("dynamic-first", ["/posts/[id]", "/posts/all/[x]"], False),
    ("static-first", ["/posts/all/[x]", "/posts/[id]"], False),
    ("real-conflict-names", ["/posts/[id]", "/posts/[foo]"], True),
    ("real-conflict-catchall", ["/posts/[id]", "/posts/[[...splat]]"], True),
    ("static-sibling-nobracket-1", ["/posts/all", "/posts/[id]"], False),
    ("static-sibling-nobracket-2", ["/posts/[id]", "/posts/all"], False),
]


def run_single(routes: list[str]) -> None:
    """Add and compile routes in order in this process; used as subprocess body.

    Args:
        routes: The routes to add in order.
    """
    import reflex as rx

    def page_a():
        return rx.text("a")

    def page_b():
        return rx.text("b")

    app = rx.App()
    try:
        for i, route in enumerate(routes):
            app.add_page(page_a if i == 0 else page_b, route=route, title=f"t{i}")
        # The conflict check runs when pages are compiled, in order.
        for route in routes:
            app._compile_page(route.removeprefix("/"))
    except Exception as e:  # noqa: BLE001
        print(f"RAISED::{type(e).__name__}: {e}")
        return
    print("OK::no error")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        run_single(sys.argv[2:])
        sys.exit(0)

    failures = 0
    for name, routes, expect_raise in CHECKS:
        proc = subprocess.run(
            [sys.executable, __file__, "--single", *routes],
            capture_output=True,
            text=True,
            timeout=120,
        )
        line = next(
            (
                ln
                for ln in proc.stdout.splitlines()
                if ln.startswith(("OK::", "RAISED::"))
            ),
            f"NO-OUTPUT (rc={proc.returncode}, stderr tail: {proc.stderr[-300:]})",
        )
        raised = line.startswith("RAISED::")
        ok = raised == expect_raise and not line.startswith("NO-OUTPUT")
        failures += 0 if ok else 1
        status = "PASS" if ok else "FAIL"
        print(f"{status} {name}: routes={routes} expect_raise={expect_raise} got={line}")

    import importlib.metadata

    print(f"reflex version: {importlib.metadata.version('reflex')}")
    sys.exit(1 if failures else 0)
