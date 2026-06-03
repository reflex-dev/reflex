"""Tests for reflex/utils/misc.py."""

from __future__ import annotations

import reflex as rx
from reflex.utils.misc import google_font


def _props(component: rx.Component) -> list[str]:
    """Return the rendered prop strings of a component.

    Args:
        component: The component to render.

    Returns:
        The list of ``name:value`` prop strings.
    """
    return component.render()["props"]


def test_google_font_exported():
    """google_font is exposed as rx.google_font."""
    assert rx.google_font is google_font


def test_google_font_default():
    """google_font returns preconnects plus a swap stylesheet with a wght axis."""
    first, second, sheet = (_props(c) for c in google_font("Inter", weights=[700, 400]))

    assert 'rel:"preconnect"' in first
    assert 'href:"https://fonts.googleapis.com"' in first
    assert 'rel:"preconnect"' in second
    assert 'crossOrigin:"anonymous"' in second

    href = "https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap"
    assert 'rel:"stylesheet"' in sheet
    assert f'href:"{href}"' in sheet


def test_google_font_italic_and_spaces():
    """google_font encodes spaces and builds the ital,wght axis when italic=True."""
    sheet = google_font("Open Sans", weights=[400, 700], italic=True)[-1]
    href = (
        "https://fonts.googleapis.com/css2?family=Open+Sans:"
        "ital,wght@0,400;0,700;1,400;1,700&display=swap"
    )
    assert f'href:"{href}"' in _props(sheet)


def test_google_font_display_override():
    """google_font respects a custom font-display strategy."""
    sheet = google_font("Roboto", display="optional")[-1]
    assert "&display=optional" in "".join(_props(sheet))
