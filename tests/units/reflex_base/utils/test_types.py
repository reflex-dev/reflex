"""Tests for reflex_base.utils.types."""

from collections.abc import Callable

from reflex_base.utils.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
    resolve_type_alias,
)
from typing_extensions import ParamSpec, TypeAliasType, TypeVarTuple, Unpack

P = ParamSpec("P")
Ts = TypeVarTuple("Ts")
Handlers = TypeAliasType(
    "Handlers", tuple[Callable[P, int], Unpack[Ts]], type_params=(P, Ts)
)


def test_asgi_aliases_keep_their_names():
    """The ASGI type aliases are TypeAliasTypes so docs render them by name, not expanded."""
    for alias in (Scope, Message, Receive, Send, ASGIApp):
        assert isinstance(alias, TypeAliasType)

    assert Scope.__name__ == "Scope"
    assert Message.__name__ == "Message"
    assert Receive.__name__ == "Receive"
    assert Send.__name__ == "Send"
    assert ASGIApp.__name__ == "ASGIApp"


def test_resolve_type_alias_substitutes_param_spec():
    """A ParamSpec is substituted even next to a TypeVarTuple.

    That combination falls back to manual substitution on 3.10 and 3.11, which
    has to treat a ParamSpec as a type parameter too.
    """
    resolved = resolve_type_alias(Handlers[[str], bool, float])
    assert resolved == tuple[Callable[[str], int], bool, float]
