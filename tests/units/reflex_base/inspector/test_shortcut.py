"""Tests for the keyboard-shortcut parser."""

from __future__ import annotations

import pytest
from reflex_base.inspector.shortcut import Shortcut, parse_shortcut
from reflex_base.utils.exceptions import ConfigError


def test_parse_simple_shortcut():
    assert parse_shortcut("alt+x") == Shortcut(key="x", alt=True)


def test_parse_normalises_modifier_aliases():
    assert parse_shortcut("Cmd+Shift+I") == Shortcut(key="i", meta=True, shift=True)
    assert parse_shortcut("option+/") == Shortcut(key="/", alt=True)
    assert parse_shortcut("Control+Super+k") == Shortcut(key="k", ctrl=True, meta=True)


def test_parse_lower_cases_key():
    assert parse_shortcut("Alt+X").key == "x"


def test_parse_rejects_empty_input():
    with pytest.raises(ConfigError):
        parse_shortcut("")
    with pytest.raises(ConfigError):
        parse_shortcut("   ")


def test_parse_rejects_only_modifiers():
    with pytest.raises(ConfigError):
        parse_shortcut("alt+")


def test_parse_rejects_unknown_modifier():
    with pytest.raises(ConfigError):
        parse_shortcut("hyper+x")
