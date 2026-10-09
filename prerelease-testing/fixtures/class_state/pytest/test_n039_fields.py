"""N-039 under #7516: patching a var's FIELD round-trips for many var kinds and 4 mechanisms, plus the class-level
spellings now raise and leave nothing behind. With DOWNSTREAM=1 also patches reflex-local-auth / google-auth / magic-link
state vars through their fields.

Run: EXPECT_VENV=<venv> [DOWNSTREAM=1] $SB/envs/<venv>/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -q -rA test_n039_fields.py
"""
import dataclasses
import os
from typing import Optional
from unittest import mock

import pytest

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


class Base(rx.State):
    inh: int = 1


class Mx(rx.State, mixin=True):
    mx: int = 2


@dataclasses.dataclass
class DC:
    a: int = 1


class K(Mx, Base):
    i: int = 3
    s: str = "s"
    f: float = 1.5
    b: bool = False
    lst: list[int] = [1]
    dct: dict[str, int] = {"a": 1}
    opt: Optional[int] = None
    fld: rx.Field[int] = rx.field(4)
    fldf: rx.Field[list[str]] = rx.field(default_factory=lambda: ["x"])
    dc: DC = DC()
    ls: str = rx.LocalStorage("l", name="n039_ls")
    ck: str = rx.Cookie("c", name="n039_ck", max_age=60)
    ss: str = rx.SessionStorage("s", name="n039_ss")
    _bi: int = 5
    _bl: list[int] = [6]


VARS = {"i": 30, "s": "S", "f": 2.5, "b": True, "lst": [9], "dct": {"z": 9}, "opt": 7, "fld": 40, "fldf": ["y"],
        "dc": DC(9), "ls": rx.LocalStorage("L", name="n039_ls"), "ck": rx.Cookie("C", name="n039_ck", max_age=60),
        "ss": rx.SessionStorage("S2", name="n039_ss"), "_bi": 50, "_bl": [60], "inh": 10, "mx": 20}


def fresh(name, cls=K):
    v = getattr(cls(_reflex_internal_init=True), name)
    return v.__wrapped__ if hasattr(v, "__wrapped__") else v


DECLARED = {n: fresh(n) for n in VARS}


def field_of(name):
    return K.__fields__[name]


MECHS = ["monkeypatch", "mock", "mocker", "factory", "set_default", "set_default_factory"]


@pytest.mark.parametrize("mech", MECHS)
@pytest.mark.parametrize("name", list(VARS))
def test_patch_field(name, mech, monkeypatch, mocker):
    new = VARS[name]
    f = field_of(name)
    if mech == "monkeypatch":
        monkeypatch.setattr(f, "default", new)
        assert fresh(name) == new
    elif mech == "mock":
        with mock.patch.object(f, "default", new):
            assert fresh(name) == new
    elif mech == "mocker":
        mocker.patch.object(f, "default", new)
        assert fresh(name) == new
    elif mech in ("set_default", "set_default_factory"):  # a5 API, restored by hand afterwards
        saved = (f.default, f.default_factory)
        try:
            if mech == "set_default":
                f.set_default(new)
            else:
                f.set_default(default_factory=lambda: new)
            assert fresh(name) == new
        finally:
            f.default, f.default_factory = saved
    else:  # default_factory: needs default MISSING while patched
        monkeypatch.setattr(f, "default", dataclasses.MISSING)
        monkeypatch.setattr(f, "default_factory", lambda: new)
        assert fresh(name) == new


@pytest.mark.parametrize("name", list(VARS))
def test_after_all_patches_declared(name):
    assert fresh(name) == DECLARED[name]


@pytest.mark.parametrize("spelling", ["assign", "setattr", "monkeypatch", "mock"])
@pytest.mark.parametrize("name", list(VARS))
def test_class_spellings_raise(name, spelling, monkeypatch):
    with pytest.raises(TypeError, match=r"is a state var of (K;|\w+, inherited by K;)"):
        if spelling == "assign":
            exec(f"K.{name} = VARS[name]")
        elif spelling == "setattr":
            setattr(K, name, VARS[name])
        elif spelling == "monkeypatch":
            monkeypatch.setattr(K, name, VARS[name])
        else:
            with mock.patch.object(K, name, VARS[name]):
                pass


@pytest.mark.parametrize("name", list(VARS))
def test_after_class_spellings_declared(name):
    assert fresh(name) == DECLARED[name]
    assert type(K.__fields__[name]).__name__ == "Field"


DOWN = []
if os.environ.get("DOWNSTREAM") == "1":
    import reflex_google_auth as ga
    import reflex_local_auth as la
    import reflex_magic_link_auth as ml

    DOWN = [(la.LocalAuthState, "auth_token"), (la.LoginState, "error_message"), (la.RegistrationState, "new_user_id"),
            (ga.GoogleAuthState, "token_response_json"), (ga.GoogleAuthState, "refresh_token"),
            (ml.MagicLinkAuthState, "session_token")]


@pytest.mark.skipif(not DOWN, reason="DOWNSTREAM=1 not set")
@pytest.mark.parametrize("cls,name", DOWN, ids=[f"{c.__name__}.{n}" for c, n in DOWN])
def test_downstream_field_patch(cls, name):
    from reflex.compiler.utils import _compile_client_storage_recursive

    def inst():
        root = rx.State(_reflex_internal_init=True)
        return getattr(root.get_substate(cls.get_full_name().split(".")[1:]), name)

    declared = inst()
    storage_before = _compile_client_storage_recursive(rx.State)
    f = cls.__fields__[name]
    new = type(f.default)("patched", **vars(f.default)) if hasattr(f.default, "__dict__") and vars(f.default) else (
        -7 if isinstance(f.default, int) else "patched")
    with mock.patch.object(f, "default", new):
        assert inst() == new
    assert inst() == declared
    assert _compile_client_storage_recursive(rx.State) == storage_before
    with pytest.raises(TypeError):
        setattr(cls, name, new)
    assert inst() == declared
