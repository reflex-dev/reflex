"""Component-level integration tests for the frontend inspector."""

from __future__ import annotations

import pytest
from reflex_base.inspector import capture, state

import reflex as rx


@pytest.fixture
def enabled_inspector():
    capture.reset()
    state.set_enabled(True)
    yield
    state.set_enabled(False)
    capture.reset()


def _props_for(component: rx.Component) -> list[str]:
    rendered = component.render()
    if isinstance(rendered, dict):
        return list(rendered.get("props", []))
    return []


def test_create_attaches_inspector_id_when_enabled(enabled_inspector):
    box = rx.box("hello")
    assert box._inspector_id is not None
    info = capture.snapshot()[box._inspector_id]
    assert info.component == "Box"


def test_create_skips_id_when_disabled():
    capture.reset()
    state.set_enabled(False)
    box = rx.box("hello")
    assert box._inspector_id is None
    assert all("data-rx" not in p for p in _props_for(box))


def test_render_emits_data_rx(enabled_inspector):
    text = rx.text("hi")
    rendered_props = _props_for(text)
    assert any('"data-rx"' in p for p in rendered_props), rendered_props


def test_render_skips_fragment(enabled_inspector):
    from reflex_components_core.base.fragment import Fragment

    frag = Fragment.create()
    # Fragment is intentionally excluded so React does not warn about an
    # unknown attribute on a non-DOM node.
    rendered_props = _props_for(frag)
    assert all("data-rx" not in p for p in rendered_props)


def test_each_component_gets_distinct_id(enabled_inspector):
    a = rx.box("a")
    b = rx.box("b")
    assert a._inspector_id != b._inspector_id
