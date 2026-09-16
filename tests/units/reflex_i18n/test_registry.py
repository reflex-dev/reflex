"""Tests for the compile-time message registry."""

import pytest
from reflex_i18n.registry import (
    MessageKey,
    clear_messages,
    collected_messages,
    register,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Isolate the message registry per test.

    Yields:
        None
    """
    clear_messages()
    yield
    clear_messages()


def test_register_same_key_twice_is_idempotent():
    register(MessageKey("Hello"))
    register(MessageKey("Hello"))
    assert collected_messages() == (MessageKey("Hello"),)


def test_register_rejects_singular_and_plural_of_same_msgid():
    register(MessageKey("item"))
    with pytest.raises(ValueError, match="either singular or plural"):
        register(MessageKey("item", plural="items"))
    # The conflicting key is not recorded.
    assert collected_messages() == (MessageKey("item"),)


def test_register_rejects_two_plurals_of_same_msgid():
    register(MessageKey("item", plural="items"))
    with pytest.raises(ValueError, match="either singular or plural"):
        register(MessageKey("item", plural="item(s)"))


def test_register_context_disambiguates():
    register(MessageKey("item"))
    register(MessageKey("item", plural="items", context="cart"))
    assert len(collected_messages()) == 2


def test_clear_messages_forgets_plural_forms():
    register(MessageKey("item"))
    clear_messages()
    register(MessageKey("item", plural="items"))
    assert collected_messages() == (MessageKey("item", plural="items"),)
