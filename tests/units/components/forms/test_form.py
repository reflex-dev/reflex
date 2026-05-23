from reflex_base.event import EventChain, prevent_default
from reflex_base.vars.base import Var
from reflex_components_core.el.elements.forms import (
    AUTO_HEIGHT_JS,
    ENTER_KEY_SUBMIT_JS,
    Textarea,
)
from reflex_components_radix.primitives.form import Form

from reflex.compiler.utils import _root_only_custom_code


def test_render_on_submit():
    """Test that on_submit event chain is rendered as a separate function."""
    submit_it = Var(
        _js_expr="submit_it",
        _var_type=EventChain,
    )
    f = Form.create(on_submit=submit_it)
    exp_submit_name = f"handleSubmit_{f.handle_submit_unique_name}"  # pyright: ignore [reportAttributeAccessIssue]
    assert f"onSubmit:{exp_submit_name}" in f.render()["props"]


def test_render_no_on_submit():
    """A form without on_submit should render a prevent_default handler."""
    f = Form.create()
    assert isinstance(f.event_triggers["on_submit"], EventChain)
    assert len(f.event_triggers["on_submit"].events) == 1
    assert f.event_triggers["on_submit"].events[0] == prevent_default


def test_textarea_enter_key_submit_emits_helper():
    """`enter_key_submit=True` must inject the onKeyDown helper into the page."""
    ta = Textarea.create(enter_key_submit=True)
    assert ENTER_KEY_SUBMIT_JS in _root_only_custom_code(ta)


def test_textarea_auto_height_emits_helper():
    """`auto_height=True` must inject the onInput helper into the page."""
    ta = Textarea.create(auto_height=True)
    assert AUTO_HEIGHT_JS in _root_only_custom_code(ta)


def test_textarea_without_features_emits_no_helpers():
    """A bare textarea should not pull in either helper snippet."""
    collected = _root_only_custom_code(Textarea.create())
    assert ENTER_KEY_SUBMIT_JS not in collected
    assert AUTO_HEIGHT_JS not in collected
