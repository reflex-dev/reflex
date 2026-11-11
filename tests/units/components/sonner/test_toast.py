"""Sonner toast component tests."""

from reflex_components_sonner.toast import Toaster


def test_toaster_hotkey_accepts_key_list():
    """Sonner reads `hotkey` as an array of KeyboardEvent keys and codes."""
    toaster = Toaster.create(hotkey=["altKey", "KeyT"])
    assert 'hotkey:["altKey", "KeyT"]' in str(toaster)
