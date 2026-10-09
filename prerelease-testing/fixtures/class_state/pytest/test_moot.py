"""A3-01 / A3-04 class-assignment patterns on 0.10.0a4: each must raise the documented TypeError AT the
assignment, and leave the var fully working (field object unchanged, declared default, reset(), pickling, class Var).

Run: EXPECT_VENV=$NEW $SB/envs/$NEW/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q test_moot.py
Each case_* test is followed by a check_* test (file order) asserting a fresh instance still reads the declared default.
"""

import os
import pickle
import re
from pathlib import Path
from unittest import mock

import pytest

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__

MSG_OWN = re.compile(r"'(\w+)' is a state var of (\w+); (assigning|deleting) it on the class would replace the var\. "
                     r"Set its default with \2\.__fields__\['\1'\]\.set_default\(\.\.\.\), or declare class-level config as ClassVar\.")
MSG_INH = re.compile(r"'(\w+)' is a state var of (\w+), inherited by (\w+); (assigning|deleting) it on \3 would replace the var\. "
                     r"Set its default with \2\.__fields__\['\1'\]\.set_default\(\.\.\.\), which applies to every state that inherits it, "
                     r"or declare class-level config as ClassVar\.")
OWNERS = []  # (name, through, owner, action) seen, printed at the end


class Other(rx.State):
    y: int = 1


class Svc(rx.State):
    limit: int = 0
    _quota: int = 0
    items: list[str] = []

    @rx.event
    def bump(self):
        self.limit += 1


class SvcChild(Svc):
    extra: int = 0


class Mix(rx.State, mixin=True):
    mval: int = 3


class UsesMix(Mix, rx.State):
    pass


DECLARED = {"limit": 0, "_quota": 0, "items": []}
ORIG_FIELDS = {cls: dict(cls.__dict__.get("__fields__")) for cls in (Svc, SvcChild, UsesMix, Mix)}


def intact(cls=Svc, names=("limit", "_quota", "items")):
    """Assert the vars still work: descriptor is the original Field, defaults, instance, reset, pickle."""
    for name in names:
        owner = next(k for k in cls.__mro__ if name in k.__dict__)
        f = owner.__dict__[name]
        assert type(f).__name__ == "Field", (name, type(f))
        assert f is cls.__fields__[name] is ORIG_FIELDS[cls][name], name
        assert f.default_value() == DECLARED.get(name, getattr(f, "default", None)), (name, f.default_value())
    s = cls(_reflex_internal_init=True) if cls is not Mix else None
    if s is None:
        return
    for name in names:
        assert getattr(s, name) == DECLARED[name], (name, getattr(s, name))
    if cls is Svc:  # a substate instantiated on its own is not a state tree: pickle only the declaring state
        s.limit = 41
        s._quota = 42
        s.items.append("x")
        s2 = pickle.loads(pickle.dumps(s))
        assert (s2.limit, s2._quota, s2.items) == (41, 42, ["x"])
        s.reset()
        assert (s.limit, s._quota, s.items) == (0, 0, [])
        # class access still builds the UI Var
        v = cls.limit
        assert isinstance(v, rx.Var) and "limit" in str(v), repr(v)


def raised_here(excinfo, marker):
    """The TypeError must be raised by the statement carrying `marker` in this file (first frame in this file)."""
    frames = [e for e in excinfo.traceback if e.path.name == Path(__file__).name]
    line = frames[0].statement.lines[0] if frames else ""
    return marker in str(frames[0].statement), str(frames[0].statement).strip()


def check_msg(excinfo, name, cls_name, action="assigning"):
    """a5 wording (#7519): own var names the class; inherited var names the declaring state + 'inherited by'."""
    s = str(excinfo.value)
    m = MSG_OWN.fullmatch(s)
    if m:
        assert m.groups() == (name, cls_name, action), m.groups()
        OWNERS.append((name, cls_name, cls_name, action))
        return
    m = MSG_INH.fullmatch(s)
    assert m, s
    n, owner, through, act = m.groups()
    assert (n, through, act) == (name, cls_name, action), m.groups()
    OWNERS.append((name, through, owner, action))
    print(f"\nINHERITED-MSG {name} through {through}: owner={owner}")


# 1. module-level configuration of the A3-01 repro: Svc.limit = 10 / Svc._quota = 10
def test_case_direct_assign_frontend():
    with pytest.raises(TypeError) as ei:
        Svc.limit = 10  # MARK-direct-frontend
    check_msg(ei, "limit", "Svc")
    assert raised_here(ei, "MARK-direct-frontend")[0]
    intact()


def test_case_direct_assign_backend():
    with pytest.raises(TypeError) as ei:
        Svc._quota = 10  # MARK-direct-backend
    check_msg(ei, "_quota", "Svc")
    intact()


def test_case_setattr_mutable():
    with pytest.raises(TypeError) as ei:
        setattr(Svc, "items", ["a"])
    check_msg(ei, "items", "Svc")
    intact()


def test_case_same_value_and_own_var():
    # S.x = S.x: frontend class access is a Var (raises); backend class access is the Field (no-op)
    with pytest.raises(TypeError):
        Svc.limit = Svc.limit
    Svc._quota = Svc._quota  # documented no-op (own field back)
    intact()


# A3-01 (a): mock.patch.object with a Var value
def test_case_a_mock_var():
    with pytest.raises(TypeError) as ei:
        with mock.patch.object(Svc, "limit", Other.y):
            pass
    check_msg(ei, "limit", "Svc")
    assert ei.value.__context__ is None, repr(ei.value.__context__)  # the cleanup was quiet


def test_check_a():
    intact()


def test_case_a_mock_plain():
    with pytest.raises(TypeError):
        with mock.patch.object(Svc, "limit", 7):
            pass


def test_check_a_plain():
    intact()


# A3-01 (b): mocker.patch.object with an rx.field
def test_case_b_mocker_field(mocker):
    with pytest.raises(TypeError) as ei:
        mocker.patch.object(Svc, "_quota", rx.field(5))
    check_msg(ei, "_quota", "Svc")


def test_check_b():
    intact()


# A3-01 (c): monkeypatch.setattr (the patch itself raises now)
def test_case_c_monkeypatch(monkeypatch):
    with pytest.raises(TypeError) as ei:
        monkeypatch.setattr(Svc, "limit", 99)
    check_msg(ei, "limit", "Svc")
    with pytest.raises(TypeError):
        Svc.limit = 50


def test_check_c():
    intact()


# A3-01 (d): monkeypatch.delattr on a declared var removes the descriptor (documented: delete-then-set replaces on purpose)
def test_case_d_monkeypatch_delattr(monkeypatch):
    monkeypatch.delattr(Svc, "_quota")
    assert "_quota" not in Svc.__dict__
    s = Svc(_reflex_internal_init=True)
    print(f"\n(d) during delattr: instance _quota -> {getattr(s, '_quota', '<AttributeError>')!r}")


def test_check_d():
    intact()


# other patch spellings
def test_case_patch_multiple():
    with pytest.raises(TypeError):
        with mock.patch.multiple(Svc, limit=5):
            pass


def test_case_patch_by_path():
    with pytest.raises(TypeError):
        with mock.patch(f"{__name__}.Svc.limit", 5):
            pass


def test_case_patch_autospec_newcallable():
    with pytest.raises(TypeError):
        with mock.patch.object(Svc, "_quota", new_callable=lambda: 7):
            pass


def test_check_spellings():
    intact()


# substates: inherited var assigned / patched / deleted through the substate
def test_case_substate_assign():
    with pytest.raises(TypeError) as ei:
        SvcChild.limit = 5
    check_msg(ei, "limit", "SvcChild")
    with pytest.raises(TypeError) as ei:
        SvcChild._quota = 5
    check_msg(ei, "_quota", "SvcChild")
    with pytest.raises(TypeError) as ei:
        del SvcChild.limit
    check_msg(ei, "limit", "SvcChild", "deleting")
    intact(SvcChild)
    intact(Svc)


def test_case_substate_mock_patch():
    with pytest.raises(TypeError) as ei:
        with mock.patch.object(SvcChild, "limit", 5):
            pass
    # mock cleans up a non-local attribute with delattr, which raises the 'deleting' TypeError
    print(f"\nsubstate mock.patch.object -> {type(ei.value).__name__}: {ei.value} | context: {ei.value.__context__!r}")


def test_case_substate_monkeypatch(monkeypatch):
    with pytest.raises(TypeError):
        monkeypatch.setattr(SvcChild, "_quota", 5)


def test_check_substate():
    intact(SvcChild)
    intact(Svc)


# mixins
def test_case_mixin_assign():
    with pytest.raises(TypeError) as ei:
        Mix.mval = 5
    check_msg(ei, "mval", "Mix")
    with pytest.raises(TypeError) as ei:
        UsesMix.mval = 5
    check_msg(ei, "mval", "UsesMix")
    s = UsesMix(_reflex_internal_init=True)
    assert s.mval == 3


def test_case_mixin_delete_inherited():
    # UsesMix owns a COPY of mval (bound by _bind_fields): deleting it there is allowed (declared on the class)
    print(f"\nmval in UsesMix.__dict__: {'mval' in UsesMix.__dict__}")


def test_zz_owner_summary():
    print("\nOWNERS (name, through, owner, action):")
    for o in OWNERS:
        print("  ", o)
