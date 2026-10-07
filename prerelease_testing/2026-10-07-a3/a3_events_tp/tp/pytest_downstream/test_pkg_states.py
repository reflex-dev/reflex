"""N-039 from the downstream angle: a user's test suite patches the State classes of INSTALLED third-party packages.

None of the packages ships a test suite that touches State (checked: sdists of all 22 packages, GitHub repos of
reflex-local-auth, -magic-link-auth, -google-auth, -chat, -global-hotkey, -clerk), so this file plays the downstream
app's test suite: it patches package vars (incl. LocalStorage-backed ones, a ComponentState list and inherited vars
through a substate) with monkeypatch / mock.patch.object / pytest-mock / plain assignment + restore, and every
`*_pristine` test that follows checks that nothing leaked: the default, the storage wrapper (type, name, sync), the
compiled client-storage entry and a fresh instance's value.

Run from this directory (never from a checkout), one venv per version:
  EXPECT_VENV=a3_events_tp-all $SB/envs/a3_events_tp-all/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q test_pkg_states.py
(same with a3_events_tp-a2 and a3_events_tp-s912). Tests are order-dependent on purpose (patch test, then pristine test).
"""

from __future__ import annotations

import json
import os
from unittest import mock

import pytest

import reflex as rx

_V = os.environ.get("EXPECT_VENV", "")
assert _V and f"/scratchpad/envs/{_V}/" in rx.__file__, (rx.__file__, _V)

from reflex.compiler.utils import _compile_client_storage_recursive  # noqa: E402
from reflex_chat.chat import Chat  # noqa: E402
from reflex_google_auth.state import GoogleAuthState  # noqa: E402
from reflex_local_auth.local_auth import LocalAuthState  # noqa: E402
from reflex_local_auth.login import LoginState  # noqa: E402
from reflex_local_auth.registration import RegistrationState  # noqa: E402
from reflex_magic_link_auth.state import MagicLinkAuthState  # noqa: E402


def inst(cls):
    """A fresh instance of `cls` inside a fresh root state."""
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(cls.get_full_name().split(".")[1:])


def field_snapshot(cls, name):
    """Default, storage wrapper type and options of a declared var."""
    f = cls.get_fields()[name]
    d = f.default
    return {
        "type": type(d).__name__,
        "value": str(d),
        "name": getattr(d, "name", None),
        "sync": getattr(d, "sync", None),
        "factory": f.default_factory is not None,
    }


def compiled_storage(cls):
    """Client-storage entries compiled for `cls` (what the frontend will read/write)."""
    cookies, local, session = _compile_client_storage_recursive(cls)
    return {"cookies": cookies, "local": local, "session": session}


# snapshot taken at import, before anything patches
BASE = {
    "auth_token": field_snapshot(LocalAuthState, "auth_token"),
    "session_token": field_snapshot(MagicLinkAuthState, "session_token"),
    "token_response_json": field_snapshot(GoogleAuthState, "token_response_json"),
    "redirect_to": field_snapshot(LoginState, "redirect_to"),
    "new_user_id": field_snapshot(RegistrationState, "new_user_id"),
    "messages": field_snapshot(Chat, "messages"),
}
BASE_STORAGE = {
    "local_auth": compiled_storage(LocalAuthState),
    "login": compiled_storage(LoginState),
    "magic": compiled_storage(MagicLinkAuthState),
    "google": compiled_storage(GoogleAuthState),
}
print("BASE", json.dumps(BASE), json.dumps(BASE_STORAGE, default=str))


def assert_pristine():
    now = {
        "auth_token": field_snapshot(LocalAuthState, "auth_token"),
        "session_token": field_snapshot(MagicLinkAuthState, "session_token"),
        "token_response_json": field_snapshot(GoogleAuthState, "token_response_json"),
        "redirect_to": field_snapshot(LoginState, "redirect_to"),
        "new_user_id": field_snapshot(RegistrationState, "new_user_id"),
        "messages": field_snapshot(Chat, "messages"),
    }
    assert now == BASE
    storage = {
        "local_auth": compiled_storage(LocalAuthState),
        "login": compiled_storage(LoginState),
        "magic": compiled_storage(MagicLinkAuthState),
        "google": compiled_storage(GoogleAuthState),
    }
    assert storage == BASE_STORAGE
    assert inst(LocalAuthState).auth_token == ""
    assert inst(LoginState).auth_token == ""
    assert inst(LoginState).redirect_to == ""
    assert inst(MagicLinkAuthState).session_token == ""
    assert inst(GoogleAuthState).token_response_json == ""
    assert inst(RegistrationState).new_user_id == -1


def test_00_pristine_at_start():
    assert_pristine()


# 1. "pretend the user is logged in": monkeypatch the LocalStorage-backed token on the package base state
def test_01_monkeypatch_local_auth_token(monkeypatch):
    monkeypatch.setattr(LocalAuthState, "auth_token", "test-token")
    assert inst(LocalAuthState).auth_token == "test-token"
    assert inst(LoginState).auth_token == "test-token"  # inherited by the substate
    print("PATCHED local_auth storage", compiled_storage(LocalAuthState))


def test_01_pristine():
    assert_pristine()


# 2. mock.patch.object context manager on a LocalStorage(sync=True) var
def test_02_mock_patch_magic_session_token():
    with mock.patch.object(MagicLinkAuthState, "session_token", "sess-1"):
        assert inst(MagicLinkAuthState).session_token == "sess-1"
        snap = field_snapshot(MagicLinkAuthState, "session_token")
        print("PATCHED magic session_token", snap)
    assert_pristine()


def test_02_pristine():
    assert_pristine()


# 3. pytest-mock on google-auth's token, with a JSON id_token
def test_03_mocker_google_token(mocker):
    mocker.patch.object(GoogleAuthState, "token_response_json", json.dumps({"id_token": "x.y.z"}))
    i = inst(GoogleAuthState)
    assert json.loads(i.token_response_json)["id_token"] == "x.y.z"


def test_03_pristine():
    assert_pristine()


# 4. patch an INHERITED storage var through the subclass (LoginState inherits auth_token from LocalAuthState)
def test_04_monkeypatch_inherited_through_substate(monkeypatch):
    monkeypatch.setattr(LoginState, "auth_token", "sub-token")
    assert inst(LoginState).auth_token == "sub-token"


def test_04_pristine():
    assert_pristine()


# 5. plain vars on package substates, decorator form
@mock.patch.object(LoginState, "redirect_to", "/after-login")
@mock.patch.object(RegistrationState, "new_user_id", 42)
def test_05_decorator_plain_vars():
    assert inst(LoginState).redirect_to == "/after-login"
    assert inst(RegistrationState).new_user_id == 42


def test_05_pristine():
    assert_pristine()


# 6. ComponentState list default of reflex-chat
def test_06_monkeypatch_chat_messages(monkeypatch):
    monkeypatch.setattr(Chat, "messages", [{"role": "assistant", "content": "seeded"}])
    print("PATCHED chat messages", field_snapshot(Chat, "messages"))


def test_06_pristine():
    assert_pristine()


# 7. manual save/assign/restore by hand (the pre-pytest idiom)
def test_07_manual_assign_restore():
    saved = LocalAuthState.__dict__.get("auth_token", None)
    LocalAuthState.auth_token = "manual"
    try:
        assert inst(LocalAuthState).auth_token == "manual"
    finally:
        if saved is not None:
            LocalAuthState.auth_token = saved
    assert_pristine()


def test_07_pristine():
    assert_pristine()


# 8. several patches stacked in one test (user fixture + test-level patch), restored in LIFO order
def test_08_stacked(monkeypatch, mocker):
    monkeypatch.setattr(LocalAuthState, "auth_token", "outer")
    mocker.patch.object(LocalAuthState, "auth_token", "inner")
    assert inst(LoginState).auth_token == "inner"


def test_08_pristine():
    assert_pristine()


# 9. the patched value reaches a handler-like method that reads the storage var on an instance
def test_09_value_used_by_package_logic(monkeypatch):
    monkeypatch.setattr(GoogleAuthState, "token_response_json", json.dumps({"id_token": "abc"}))
    i = inst(GoogleAuthState)
    # GoogleAuthState.id_token_json is a computed var reading token_response_json
    assert json.loads(i.id_token_json) == {"credential": "abc"}


def test_09_pristine():
    assert_pristine()
