"""Regression coverage for stable property-control identities."""


def test_prop_ids_do_not_depend_on_evaluation_order():
    """Partial page compiles must reuse the same state variable names."""
    from reflex_docs.pages.docs.component import get_id

    first = get_id("module.Button.size")
    other = get_id("module.Text.size")
    expanded = get_id("module.Button.size.expanded")
    assert get_id("module.Button.size") == first
    assert len({first, other, expanded}) == 3


def test_repeated_prop_controls_reuse_their_state_variable():
    """The same component documented twice can share its stable control ID."""
    from typing import Literal

    import reflex as rx
    from reflex_components_radix.themes.components.button import Button
    from reflex_docgen import PropDocumentation

    from reflex_docs.pages.docs.component import prop_docs, render_select

    prop = PropDocumentation(
        name="size",
        type=rx.Var[Literal["1", "2", "3"]],
        description="Long description " * 20,
        default_value="1",
    )
    first = {}
    second = {}
    render_select(prop, Button, first)
    render_select(prop, Button, second)
    assert str(first["size"]) == str(second["size"])
    assert prop_docs(prop, Button)[2] == prop_docs(prop, Button)[2]
