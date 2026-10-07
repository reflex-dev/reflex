"""T-1 blast radius: when a class-level default patch leaks, whose default is changed?"""
import os, types
import pytest
import reflex as rx
assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version
print("reflex", version("reflex"))


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


def dflt(cls, name):
    try:
        return cls.get_fields()[name].default
    except Exception as e:  # noqa: BLE001
        return f"<{type(e).__name__}>"


def leak(label, patch_cls, name, others):
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(patch_cls, name, 99)
    except Exception as e:  # noqa: BLE001
        print(f"  {label}: patch raised {type(e).__name__}")
        return
    try:
        mp.undo()
    except Exception:  # noqa: BLE001
        pass
    row = {c.__name__: dflt(c, name) for c in [patch_cls, *others]}
    print(f"  {label}: after teardown defaults = {row}")


class Mix(rx.State, mixin=True):
    _v: int = 5


class UsesA(Mix, rx.State):
    pass


class UsesB(Mix, rx.State):
    pass


print("mixin: patch UsesA._v -> do UsesB / the mixin itself change?")
leak("mixin users", UsesA, "_v", [UsesB, Mix])


class Parent(rx.State):
    _v: int = 5


class ChildA(Parent):
    pass


class ChildB(Parent):
    pass


print("substates: patch ChildA._v (declared on Parent) -> Parent / ChildB change?")
leak("substates", ChildA, "_v", [Parent, ChildB])

print("substates: patch Parent._v -> children see it (inherit)?")
leak("parent patch", Parent, "_v", [ChildA, ChildB])


def mk_cs(tag):
    def body(ns):
        ns["__module__"] = __name__
        ns["__annotations__"] = {"_v": int}
        ns["_v"] = 5
        ns["get_component"] = classmethod(lambda cls, **p: rx.box())
    return types.new_class(f"BlastCS{tag}", (rx.ComponentState,), {}, body)


CS = mk_cs("1")
c1, c2 = CS.create(), CS.create()
print("ComponentState: patch generated state of component 1 -> template / component 2 change?")
leak("componentstate", c1.State, "_v", [c2.State, CS])
