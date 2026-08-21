import reflex as rx


def _make_accordion(**props):
    return rx.ui.accordion(
        rx.ui.accordion.item(
            rx.ui.accordion.trigger("Question 1"),
            rx.ui.accordion.content("Answer 1"),
        ),
        rx.ui.accordion.item(
            rx.ui.accordion.trigger("Question 2"),
            rx.ui.accordion.content("Answer 2"),
        ),
        **props,
    )


def test_accordion_renders_native_details_and_summary() -> None:
    """Accordion items are native details/summary elements."""
    rendered = str(_make_accordion())

    assert rendered.count('jsx("details"') == 2
    assert rendered.count('jsx("summary"') == 2


def test_exclusive_accordion_shares_a_group_name() -> None:
    """By default all items share a generated details group name."""
    rendered = str(_make_accordion())

    assert rendered.count('name:"accordion-') == 2


def test_multiple_accordion_has_no_group_name() -> None:
    """multiple=True leaves items ungrouped so several can stay open."""
    rendered = str(_make_accordion(multiple=True))

    assert 'name:"accordion-' not in rendered


def test_accordion_trigger_includes_indicator_icon() -> None:
    """The trigger appends a rotating chevron icon."""
    rendered = str(_make_accordion())

    assert "group-open:rotate-180" in rendered
    assert 'jsx("svg"' in rendered


def test_accordion_item_explicit_name_wins() -> None:
    """An explicit item name is not overwritten by the root."""
    rendered = str(
        rx.ui.accordion(
            rx.ui.accordion.item(
                rx.ui.accordion.trigger("Q"),
                rx.ui.accordion.content("A"),
                name="custom-group",
            )
        )
    )

    assert 'name:"custom-group"' in rendered
