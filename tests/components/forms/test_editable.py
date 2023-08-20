import reflex as rx


class S(rx.State):
    """Example state for debounce tests."""

    value: str = ""

    def on_change(self, v: str):
        """Dummy on_change handler.

        Args:
            v: The changed value.
        """
        pass


def test_full_control_implicit_debounce_editable():
    """DebounceInput is used when value and on_change are used together."""
    tag = rx.editable(
        value=S.value,
        on_change=S.on_change,
    )._render()
    assert tag.props["debounceTimeout"].name == "50"
    assert len(tag.props["onChange"].events) == 1
    assert tag.props["onChange"].events[0].handler == S.on_change
    assert tag.contents == ""


def test_full_control_explicit_debounce_editable():
    """DebounceInput is used when user specifies `debounce_time`."""
    tag = rx.editable(
        on_change=S.on_change,
        debounce_timeout=33,
    )._render()
    assert tag.props["debounceTimeout"].name == "33"
    assert len(tag.props["onChange"].events) == 1
    assert tag.props["onChange"].events[0].handler == S.on_change
    assert tag.contents == ""


def test_editable_no_debounce():
    """DebounceInput is not used for regular editable."""
    tag = rx.editable(
        placeholder=S.value,
    )._render()
    assert "debounceTimeout" not in tag.props
    assert tag.contents == ""
