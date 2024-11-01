from reflex.components.radix.primitives.form import Form
from reflex.event import EventChain, prevent_default
from reflex.vars.base import Var


def test_render_on_submit():
    """Test that on_submit event chain is rendered as a separate function."""
    submit_it = Var(
        _js_expr="submit_it",
        _var_type=EventChain,
    )
    f = Form.create(on_submit=submit_it)
    exp_submit_name = f"handleSubmit_{f.handle_submit_unique_name}"  # type: ignore
    assert f"onSubmit={{{exp_submit_name}}}" in f.render()["props"]


def test_render_no_on_submit():
    """A form without on_submit should render a prevent_default handler."""
    f = Form.create()
    assert f.event_triggers["on_submit"] == prevent_default
