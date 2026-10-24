"""STATE-05 / #7626: BaseStateMeta contract and reflex-enterprise imports.

Run: cd $W && EXPECT_VENV=<venv> CI=true $SB/envs/<venv>/bin/python -I probe_state05_meta.py
"""

import importlib
import os
import pkgutil
import warnings

import reflex as rx
from reflex_base.vars.base import BaseStateMeta

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__

print("type(rx.State) is BaseStateMeta:", type(rx.State) is BaseStateMeta, type(rx.State))
print("type(rx.ComponentState):", type(rx.ComponentState))


class MyMeta(BaseStateMeta):
    created = []

    def __new__(mcs, name, bases, ns, **kw):
        cls = super().__new__(mcs, name, bases, ns, **kw)
        MyMeta.created.append((name, kw))
        return cls


try:

    class Plugged(rx.State, metaclass=MyMeta):
        x: int = 1

        @rx.event
        def bump(self):
            self.x += 1

    class SubPlugged(Plugged):
        y: str = "y"

    inst = SubPlugged(_reflex_internal_init=True)
    print("custom metaclass OK:", type(Plugged), MyMeta.created, "instance x/y:", inst.x, inst.y, "root:", Plugged._reflex_state_root)
except Exception as e:  # noqa: BLE001
    print("custom metaclass FAILED:", type(e).__name__, e)

try:

    class Mix(rx.State, mixin=True):
        shared: int = 5

        @rx.var
        def doubled(self) -> int:
            return self.shared * 2

    class UsesMix(Mix, rx.State):
        own: int = 0

    print("mixin=True:", Mix._mixin, "UsesMix fields:", sorted(k for k in UsesMix.get_fields() if not k.startswith("_") and "rx_state" not in k))
    try:
        Mix(_reflex_internal_init=True)
        print("mixin instantiation: ALLOWED (unexpected)")
    except Exception as e:  # noqa: BLE001
        print("mixin instantiation rejected:", type(e).__name__, str(e)[:120])
except Exception as e:  # noqa: BLE001
    print("mixin FAILED:", type(e).__name__, e)

try:
    from reflex_base.vars.base import BaseState as _BS

    class Root2(_BS, state_root=True):
        r: int = 0

    class Leaf2(Root2):
        l: int = 1

    print("state_root=True:", Root2._reflex_state_root is Root2, Leaf2._reflex_state_root is Root2, "rx.State root:", rx.State._reflex_state_root)
except Exception as e:  # noqa: BLE001
    print("state_root FAILED:", type(e).__name__, e)

try:

    class Bad(rx.State):
        _reflex_state_root = None  # reserved name

    print("reserved _reflex_state_root assignment: accepted, root now", Bad._reflex_state_root)
except Exception as e:  # noqa: BLE001
    print("reserved _reflex_state_root assignment rejected:", type(e).__name__, str(e)[:160])

try:
    import reflex_enterprise  # noqa: F401
except ImportError as e:
    print("reflex_enterprise not installed:", e)
else:
    bad = []
    n = 0
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        for m in pkgutil.walk_packages(reflex_enterprise.__path__, "reflex_enterprise."):
            if ".demos" in m.name or "cli" in m.name.split(".")[-1]:
                continue
            n += 1
            try:
                importlib.import_module(m.name)
            except Exception as e:  # noqa: BLE001
                bad.append((m.name, f"{type(e).__name__}: {str(e)[:100]}"))
    print(f"rxe modules imported: {n}, failed: {len(bad)}")
    for b in bad:
        print("   FAIL", b)
    dep = sorted({str(x.message)[:140] for x in w if "eprecat" in x.category.__name__})
    print("deprecation warnings during rxe import:", len(dep))
    for d in dep[:12]:
        print("   ", d)
    try:
        import reflex_enterprise as rxe

        class EntState(rxe.State if hasattr(rxe, "State") else rx.State):
            v: int = 0

        print("rxe State subclass OK:", type(EntState))
    except Exception as e:  # noqa: BLE001
        print("rxe State subclass FAILED:", type(e).__name__, e)
