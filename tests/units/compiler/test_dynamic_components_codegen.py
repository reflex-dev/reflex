"""Code generation tests for dynamic components."""

from pathlib import Path

from reflex_base.utils import serializers

import reflex as rx
from reflex.state import State

STATE_JS_TEMPLATE = (
    Path(__file__).parents[3]
    / "packages/reflex-base/src/reflex_base/.templates/web/utils/state.js"
)


def test_dynamic_component_codegen_wires_event_handlers() -> None:
    """Dynamic component codegen should preserve backend event handlers."""
    state = State(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    component = rx.el.div(
        rx.el.button("hydrate", on_click=State.set_is_hydrated(True)),
        rx.el.span(state.is_hydrated),
        rx.el.button("unhydrate", on_click=State.set_is_hydrated(False)),
    )
    code = serializers.serialize(component)

    assert isinstance(code, str)
    assert code.startswith("//__reflex_evaluate")
    assert "const {Fragment,useContext,useEffect}" in code
    assert "const {EventLoopContext} = window['__reflex'][\"$/utils/context\"]" in code
    assert (
        "const {ReflexEvent,applyEventActions} = window['__reflex'][\"$/utils/state\"]"
        in code
    )
    assert "const [addEvents, connectErrors] = useContext(EventLoopContext);" in code
    assert code.count("onClick:") == 2
    assert code.count("addEvents(") == 2
    assert code.count("ReflexEvent(") == 2
    assert (
        'ReflexEvent("reflex___state____state.set_is_hydrated", '
        '({ ["value"] : true }), ({  }))'
    ) in code
    assert (
        'ReflexEvent("reflex___state____state.set_is_hydrated", '
        '({ ["value"] : false }), ({  }))'
    ) in code


def test_dynamic_component_codegen_wires_state_var_counter_events() -> None:
    """Dynamic component codegen should preserve stateful counter event handlers."""

    class DynamicCounterCodegenState(rx.State):
        count: int = 0

        @rx.event
        def set_count(self, count: int):
            """Set the counter value.

            Args:
                count: The new counter value.
            """
            self.count = count

        @rx.var
        def counter_ui(self) -> rx.Component:
            """Get a dynamic counter component.

            Returns:
                The dynamic counter component.
            """
            return rx.hstack(
                rx.button(
                    "-",
                    on_click=DynamicCounterCodegenState.set_count(self.count - 1),
                ),
                rx.text(self.count, size="9"),
                rx.button(
                    "+",
                    on_click=DynamicCounterCodegenState.set_count(self.count + 1),
                ),
                spacing="5",
                justify="center",
            )

    state = DynamicCounterCodegenState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    code = serializers.serialize(state.counter_ui)

    assert isinstance(code, str)
    assert code.startswith("//__reflex_evaluate")
    assert "RadixThemesFlex" in code
    assert "RadixThemesButton" in code
    assert "RadixThemesText" in code
    assert 'justify:"center"' in code
    assert 'gap:"5"' in code
    assert "const {Fragment,useContext,useEffect}" in code
    assert "const {EventLoopContext} = window['__reflex'][\"$/utils/context\"]" in code
    assert (
        "const {ReflexEvent,applyEventActions} = window['__reflex'][\"$/utils/state\"]"
        in code
    )
    assert "const [addEvents, connectErrors] = useContext(EventLoopContext);" in code
    assert code.count("onClick:") == 2
    assert code.count("addEvents(") == 2
    assert code.count("ReflexEvent(") == 2
    assert code.count(".set_count") == 2
    assert '({ ["count"] : -1 }), ({  })' in code
    assert '({ ["count"] : 1 }), ({  })' in code
    assert 'jsx(RadixThemesText, ({as:"p",size:"9"}), 0)' in code
