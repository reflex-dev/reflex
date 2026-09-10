"""#6929: attribute probes on vars must not trigger ForwardRef resolution of unrelated annotations.

Imports the app's FwdState (its `Weighted` dataclass has a TYPE_CHECKING-only annotation) and
runs unittest.mock.patch.object / inspect.iscoroutinefunction against its vars while capturing
logging warnings. Run with cwd = the app dir (hp_app) so `hp_app` is importable.
"""
import inspect, logging, sys, io
from unittest import mock
import reflex
print("python", sys.version.split()[0], "reflex", reflex.__file__)

buf = io.StringIO()
handler = logging.StreamHandler(buf)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.WARNING)
# reflex may install its own handlers; also capture the reflex_base logger explicitly
for lg in ("reflex_base.utils.types", "reflex_base", "reflex"):
    logging.getLogger(lg).addHandler(handler)

from hp_app.fwd_state import FwdState, Weighted  # noqa: E402

def section(title):
    print(f"\n== {title}")

section("inspect.iscoroutinefunction(FwdState.weighted)  [ObjectVar over unresolvable dataclass]")
try:
    print("->", inspect.iscoroutinefunction(FwdState.weighted))
except Exception as e:  # noqa: BLE001
    print("-> RAISED", type(e).__name__, str(e)[:200])

section("inspect.iscoroutinefunction(FwdState.items) / FwdState.current / FwdState.banner")
for v in (FwdState.items, FwdState.current, FwdState.banner):
    try:
        print("->", type(v).__name__, inspect.iscoroutinefunction(v))
    except Exception as e:  # noqa: BLE001
        print("-> RAISED", type(e).__name__, str(e)[:200])

section("mock.patch.object(FwdState, 'weighted') / 'items' / 'add' / 'async_add'")
for attr in ("weighted", "items", "add", "async_add"):
    try:
        with mock.patch.object(FwdState, attr) as m:
            print(f"-> patched {attr}: {type(m).__name__}")
    except Exception as e:  # noqa: BLE001
        print(f"-> {attr} RAISED", type(e).__name__, str(e)[:200])

section("FwdState.weighted.name  [annotated attr on unresolvable dataclass -- expected to warn]")
try:
    print("->", FwdState.weighted.name)
except Exception as e:  # noqa: BLE001
    print("-> RAISED", type(e).__name__, str(e)[:200])

section("FwdState.current.name / .tag.label  [resolvable later-defined forward ref]")
try:
    print("->", FwdState.current.name, "|", FwdState.current.tag.label)
except Exception as e:  # noqa: BLE001
    print("-> RAISED", type(e).__name__, str(e)[:200])

if sys.version_info >= (3, 14):
    section("3.14 lazy annotations: LazyState probes")
    from hp_app.fwd_lazy_state import LazyState
    for fn in (lambda: inspect.iscoroutinefunction(LazyState.weighted),
               lambda: inspect.iscoroutinefunction(LazyState.items),
               lambda: LazyState.items[0].name,
               lambda: LazyState.items[0].tag.label,
               lambda: LazyState.weighted.name):
        try:
            print("->", fn())
        except Exception as e:  # noqa: BLE001
            print("-> RAISED", type(e).__name__, str(e)[:200])

handler.flush()
print("\n== captured warnings:")
print(buf.getvalue() or "<none>")
