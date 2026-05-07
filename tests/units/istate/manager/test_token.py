"""Tests for StateToken, BaseStateToken, and from_legacy_token."""

import io
import pickle

import pytest

from reflex.istate.manager.token import BaseStateToken, StateToken


def test_state_token_str():
    """__str__ encodes ident and cls into 'ident/module.Class' format."""
    token = StateToken(ident="abc-123", cls=int)
    assert str(token) == "abc-123/builtins.int"


def test_state_token_str_escapes_slashes():
    """Slashes in ident or cls name are percent-encoded."""
    token = StateToken(ident="a/b", cls=int)
    result = str(token)
    assert "%2F" in result
    assert "/" in result


def test_state_token_with_cls():
    """with_cls returns a new token with updated cls, leaving the original unchanged."""
    token = StateToken(ident="tok", cls=int)
    new = token.with_cls(bool)
    assert new.cls is bool
    assert new.ident == "tok"
    assert token.cls is int


def test_state_token_serialize_deserialize_roundtrip():
    """serialize/deserialize with data= round-trips through pickle."""
    value = {"key": [1, 2, 3]}
    data = StateToken.serialize(value)
    assert isinstance(data, bytes)
    assert StateToken.deserialize(data=data) == value


def test_state_token_deserialize_from_fp():
    """Deserialize with fp= reads from a file-like object."""
    value = "hello"
    buf = io.BytesIO(pickle.dumps(value))
    assert StateToken.deserialize(fp=buf) == value


def test_state_token_deserialize_neither_raises():
    """Deserialize with neither data nor fp raises ValueError."""
    with pytest.raises(ValueError, match="At least one"):
        StateToken.deserialize()


def test_state_token_deserialize_both_raises():
    """Deserialize with both data and fp raises ValueError."""
    with pytest.raises(ValueError, match="Only one"):
        StateToken.deserialize(data=b"data", fp=io.BytesIO())


def test_state_token_get_and_reset_touched_state():
    """Default implementation always returns True."""
    assert StateToken.get_and_reset_touched_state("anything") is True


def test_base_state_token_str(clean_registration_context):
    """__str__ uses 'ident_full_name' format.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class TokState(BaseState):
        pass

    token = BaseStateToken(ident="client-abc", cls=TokState)
    result = str(token)
    assert result.startswith("client-abc_")
    assert TokState.get_full_name() in result


def test_base_state_token_with_cls(clean_registration_context):
    """with_cls returns a BaseStateToken (not a plain StateToken).

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class A(BaseState):
        pass

    class B(BaseState):
        pass

    token = BaseStateToken(ident="tok", cls=A)
    new = token.with_cls(B)
    assert isinstance(new, BaseStateToken)
    assert new.cls is B


def test_base_state_token_serialize_deserialize(clean_registration_context):
    """BaseStateToken serialization uses BaseState._serialize/_deserialize.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class SerState(BaseState):
        x: int = 42

    state = SerState()
    data = BaseStateToken.serialize(state)
    assert isinstance(data, bytes)
    restored = BaseStateToken.deserialize(data=data)
    assert isinstance(restored, SerState)
    assert restored.x == 42


def test_base_state_token_get_and_reset_touched(clean_registration_context):
    """get_and_reset_touched_state returns the touched flag and resets it.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class TouchState(BaseState):
        x: int = 0

    state = TouchState()
    state._was_touched = True
    assert BaseStateToken.get_and_reset_touched_state(state) is True
    assert state._was_touched is False
    assert BaseStateToken.get_and_reset_touched_state(state) is False


def test_from_legacy_token(clean_registration_context):
    """from_legacy_token parses 'ident_state.path' into a BaseStateToken.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class LegacyRoot(BaseState):
        pass

    full_name = LegacyRoot.get_full_name()
    legacy_str = f"my-client-token_{full_name}"

    token = BaseStateToken.from_legacy_token(legacy_str, root_state=LegacyRoot)
    assert token.ident == "my-client-token"
    assert token.cls is LegacyRoot


def test_from_legacy_token_substate(clean_registration_context):
    """from_legacy_token resolves a substate path.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class LegRoot(BaseState):
        pass

    class LegChild(LegRoot):
        pass

    full_name = LegChild.get_full_name()
    legacy_str = f"tok_{full_name}"

    token = BaseStateToken.from_legacy_token(legacy_str, root_state=LegRoot)
    assert token.ident == "tok"
    assert token.cls is LegChild


def test_from_legacy_token_none_root_raises():
    """from_legacy_token with root_state=None raises ValueError."""
    with pytest.raises(ValueError, match="Root state must be provided"):
        BaseStateToken.from_legacy_token("tok_some.state", root_state=None)
