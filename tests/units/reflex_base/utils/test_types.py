"""Tests for reflex_base.utils.types."""

from reflex_base.utils.types import ASGIApp, Message, Receive, Scope, Send
from typing_extensions import TypeAliasType


def test_asgi_aliases_keep_their_names():
    """The ASGI type aliases are TypeAliasTypes so docs render them by name, not expanded."""
    for alias in (Scope, Message, Receive, Send, ASGIApp):
        assert isinstance(alias, TypeAliasType)

    assert Scope.__name__ == "Scope"
    assert Message.__name__ == "Message"
    assert Receive.__name__ == "Receive"
    assert Send.__name__ == "Send"
    assert ASGIApp.__name__ == "ASGIApp"
