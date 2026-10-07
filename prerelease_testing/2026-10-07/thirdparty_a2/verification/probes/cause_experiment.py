"""Cause experiment (in-process, no files modified): is the in-place mutation (aliasing) a co-cause of the leak?

Hypothetical 'fix A' = BaseStateMeta.__setattr__ treats assigning the declared Field object back to itself as a no-op
(this is what silencing the 'A Field cannot overwrite another field' error for monkeypatch/mock restores would amount to).
We install it as a wrapper and re-run the monkeypatch round trip.  If the default is STILL 99 afterwards, the aliasing
(snapshot object == live, already-mutated Field) is an independent cause of the leak.
"""
import os
import pytest
import reflex as rx
import reflex_base.vars.base as base

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


class Svc(rx.State):
    _limit: int = 5


def roundtrip(label):
    mp = pytest.MonkeyPatch()
    mp.setattr(Svc, "_limit", 99)
    try:
        mp.undo()
        err = None
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {str(e)[:70]}"
    print(f"{label:<62} undo_error={err!s:<82} field.default={Svc.get_fields()['_limit'].default!r}  new instance reads {inst(Svc)._limit!r}")
    # reset for the next experiment
    Svc.get_fields()["_limit"].default = 5


# what monkeypatch actually snapshots:
snap = Svc.__dict__["_limit"]
print("snapshot object is the live Field:", snap is Svc.get_fields()["_limit"], "| snapshot.default before patch:", snap.default)
Svc._limit = 99
print("snapshot.default AFTER the patch (aliasing proof; same object mutated in place):", snap.default)
Svc._limit = 5

roundtrip("stock a2 BaseStateMeta.__setattr__")

orig = base.BaseStateMeta.__setattr__


def relaxed(cls, name, value):
    declared = cls.__fields__.get(name)
    if declared is not None and value is declared:
        return  # hypothetical fix A: assigning the declared Field back to itself is a no-op
    return orig(cls, name, value)


base.BaseStateMeta.__setattr__ = relaxed
try:
    roundtrip("hypothetical fix A (identity no-op), in-place mutation kept")
finally:
    base.BaseStateMeta.__setattr__ = orig
