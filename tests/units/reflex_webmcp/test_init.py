"""Unit tests for automatic Reflex event exposure through WebMCP."""

from typing import Literal

import pytest
import reflex_webmcp as webmcp
from reflex_base.components.component import Component
from reflex_base.event import EventChain, EventHandler, EventSpec
from reflex_base.plugins.compiler import CompileContext, CompilerHooks, PageContext
from reflex_base.utils.format import format_event_handler
from reflex_components_core.base.fragment import Fragment
from reflex_webmcp import WebMCPPlugin

import reflex as rx
from reflex.compiler import compiler
from reflex.compiler.plugins import default_page_plugins


class EventComponent(Component):
    """Test component with compiler-visible event triggers."""

    tag = "button"

    @classmethod
    def get_event_triggers(cls):
        """Declare event argument shapes used by these tests.

        Returns:
            Trigger name to argument-spec mapping.
        """
        return {
            "on_click": lambda: (),
            "on_search": lambda query: (query,),
        }


class EventState(rx.State):
    """Real Reflex state used by automatic event-discovery tests."""

    def clear_selection(self) -> None:
        """Reset the current selection."""

    def search(self, query: str) -> None:
        """Search the visible catalog."""

    def filter_items(
        self,
        categories: list[str],
        mode: Literal["all", "active"] = "all",
        limit: int | None = None,
    ) -> None:
        """Filter the visible items."""

    def select_item(self, item_id: int) -> None:
        """Select one visible item."""

    def variadic(self, *values: str) -> None:
        """Handle an unsupported variadic payload."""


CLEAR_HANDLER = EventState.event_handlers["clear_selection"]
SEARCH_HANDLER = EventState.event_handlers["search"]
FILTER_HANDLER = EventState.event_handlers["filter_items"]
SELECT_HANDLER = EventState.event_handlers["select_item"]
CLEAR_EVENT = format_event_handler(CLEAR_HANDLER)
SEARCH_EVENT = format_event_handler(SEARCH_HANDLER)
FILTER_EVENT = format_event_handler(FILTER_HANDLER)
SELECT_EVENT = format_event_handler(SELECT_HANDLER)


def tool_name(event_name: str) -> str:
    """Return the expected tool name for an EventState event.

    Args:
        event_name: Qualified Reflex event name.

    Returns:
        Expected generated WebMCP tool name.
    """
    return f"reflex_EventState_{event_name.rsplit('.', 1)[1]}"


def event_chain(*specs: EventSpec) -> EventChain:
    """Create an event chain without UI argument remapping.

    Args:
        specs: Event specifications to place in the chain.

    Returns:
        A compiler-visible event chain.
    """
    return EventChain(events=specs, args_spec=lambda: ())


def compile_component(
    component: Component, *, full_pipeline: bool = False
) -> PageContext:
    """Compile a component through the automatic WebMCP pass.

    Args:
        component: Component tree to compile.
        full_pipeline: Whether to include the default collector and memoization passes.

    Returns:
        The populated page context.
    """
    page_ctx = PageContext(
        name="page",
        route="index",
        root_component=Fragment.create(component),
    )
    hooks = CompilerHooks(
        plugins=(
            default_page_plugins(plugins=(WebMCPPlugin(),))
            if full_pipeline
            else (WebMCPPlugin(),)
        )
    )
    compile_ctx = CompileContext(pages=[], hooks=hooks)
    with compile_ctx, page_ctx:
        page_ctx.root_component = hooks.compile_component(
            page_ctx.root_component,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )
        hooks.compile_page(page_ctx, compile_context=compile_ctx)
    return page_ctx


def registrations(page_ctx: PageContext) -> list[str]:
    """Return generated WebMCP registration snippets.

    Args:
        page_ctx: Compiled page context.

    Returns:
        WebMCP registration snippets in compiler order.
    """
    return [code for code in page_ctx.module_code if "registerTool" in code]


def test_webmcp_module_exposes_plugin_alias() -> None:
    """The module follows the standard plugin loading convention."""
    assert webmcp.Plugin is WebMCPPlugin


def test_plugin_automatically_exposes_bound_reflex_events() -> None:
    """Bound backend events become tools without manual tool definitions."""
    component = EventComponent.create(
        on_click=CLEAR_HANDLER,
        on_search=SEARCH_HANDLER,
    )

    generated = registrations(compile_component(component))

    assert len(generated) == 2
    clear_tool, search_tool = generated
    assert f'name: "{tool_name(CLEAR_EVENT)}"' in clear_tool
    assert 'description: "Reset the current selection."' in clear_tool
    assert (
        'inputSchema: {"type":"object","properties":{},"additionalProperties":false}'
        in clear_tool
    )
    assert f'ReflexEvent("{CLEAR_EVENT}", payload, {{}})' in clear_tool
    assert f'name: "{tool_name(SEARCH_EVENT)}"' in search_tool
    assert 'description: "Search the visible catalog."' in search_tool
    assert '"query":{"type":"string"}' in search_tool
    assert '"required":["query"]' in search_tool
    assert f'ReflexEvent("{SEARCH_EVENT}", payload, {{}})' in search_tool


def test_plugin_discovers_event_built_by_real_reflex_component() -> None:
    """Normal State handlers and component factories need no special adapter."""
    component = rx.input(on_change=SEARCH_HANDLER)

    [generated] = registrations(compile_component(component))

    assert 'description: "Search the visible catalog."' in generated
    assert '"query":{"type":"string"}' in generated
    assert f'ReflexEvent("{SEARCH_EVENT}", payload, {{}})' in generated


def test_plugin_survives_default_memoization_and_renders_runtime_imports() -> None:
    """Discovery happens before trigger memoization in the real compiler chain."""
    page_ctx = compile_component(
        rx.input(on_change=SEARCH_HANDLER),
        full_pipeline=True,
    )

    _, output = compiler.compile_page_from_context(page_ctx)

    assert "registerTool" in output
    assert f'ReflexEvent("{SEARCH_EVENT}", payload, {{}})' in output
    assert "addEvents" in output
    assert 'from "$/utils/context"' in output
    assert 'from "$/utils/state"' in output


def test_plugin_generates_schema_from_handler_annotations_and_defaults() -> None:
    """Handler annotations and defaults become the tool input schema."""
    component = EventComponent.create(
        on_click=event_chain(EventSpec(handler=FILTER_HANDLER)),
    )

    [generated] = registrations(compile_component(component))

    assert '"categories":{"type":"array","items":{"type":"string"}}' in generated
    assert (
        '"mode":{"enum":["all","active"],"type":"string","default":"all"}' in generated
    )
    assert (
        '"limit":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":null}'
        in generated
    )
    assert '"required":["categories"]' in generated


def test_plugin_preserves_literal_arguments_already_bound_by_component() -> None:
    """A fixed UI event stays fixed instead of broadening handler access."""
    component = EventComponent.create(
        on_click=event_chain(SELECT_HANDLER(42)),
    )

    [generated] = registrations(compile_component(component))

    assert f'name: "{tool_name(SELECT_EVENT)}_' in generated
    assert 'Bound inputs: {\\"item_id\\":42}.' in generated
    assert (
        'inputSchema: {"type":"object","properties":{},"additionalProperties":false}'
        in generated
    )
    assert 'const payload = { ...input, ...{"item_id":42} };' in generated
    assert f'ReflexEvent("{SELECT_EVENT}", payload, {{}})' in generated


def test_plugin_preserves_existing_event_actions() -> None:
    """Debounce, throttle, and temporal semantics stay on the queued event."""
    component = EventComponent.create(
        on_click=event_chain(EventSpec(handler=CLEAR_HANDLER).debounce(250)),
    )

    [generated] = registrations(compile_component(component))

    assert f'name: "{tool_name(CLEAR_EVENT)}_' in generated
    assert f'ReflexEvent("{CLEAR_EVENT}", payload, {{"debounce":250}})' in generated


def test_plugin_deduplicates_handler_bound_to_multiple_components() -> None:
    """The same backend event is registered once per compiled page."""
    component = Fragment.create(
        EventComponent.create(on_click=CLEAR_HANDLER),
        EventComponent.create(on_click=CLEAR_HANDLER),
    )

    generated = registrations(compile_component(component))

    assert len(generated) == 1
    assert generated[0].count(f'name: "{tool_name(CLEAR_EVENT)}"') == 1


def test_plugin_exposes_every_backend_event_in_a_chain() -> None:
    """Backend EventSpecs in an existing Reflex chain become separate tools."""
    component = EventComponent.create(
        on_click=event_chain(
            EventSpec(handler=CLEAR_HANDLER),
            EventSpec(handler=FILTER_HANDLER),
        )
    )

    generated = registrations(compile_component(component))

    assert len(generated) == 2
    assert any(
        f'ReflexEvent("{CLEAR_EVENT}", payload, {{}})' in code for code in generated
    )
    assert any(
        f'ReflexEvent("{FILTER_EVENT}", payload, {{}})' in code for code in generated
    )


def test_plugin_ignores_frontend_only_events() -> None:
    """Only backend EventSpecs attached to a Reflex State are exposed."""
    frontend_handler = EventHandler(fn=lambda: None)
    component = EventComponent.create(
        on_click=event_chain(EventSpec(handler=frontend_handler)),
    )

    page_ctx = compile_component(component)

    assert registrations(page_ctx) == []
    assert page_ctx.imports == []


def test_plugin_skips_handlers_without_an_object_payload_shape(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Variadic handlers are skipped instead of producing a broken tool."""
    handler = EventState.event_handlers["variadic"]
    component = EventComponent.create(
        on_click=event_chain(EventSpec(handler=handler)),
    )

    page_ctx = compile_component(component)

    assert registrations(page_ctx) == []
    assert f"Cannot expose Reflex event {format_event_handler(handler)}" in caplog.text


def test_plugin_exposes_events_inside_memoized_foreach_bodies() -> None:
    """Row events sealed inside a Foreach snapshot are still discovered."""

    class RowState(rx.State):
        items: list[int] = []

        def toggle(self, item_id: int) -> None:
            """Toggle one row."""

    toggle = RowState.event_handlers["toggle"]
    page_ctx = compile_component(
        rx.foreach(RowState.items, lambda item: rx.checkbox(on_change=toggle(item))),
        full_pipeline=True,
    )
    generated = registrations(page_ctx)
    assert len(generated) == 1
    assert 'name: "reflex_RowState_toggle"' in generated[0]
    # The per-row Var argument is not fixed, so the agent supplies it.
    assert '"required":["item_id"]' in generated[0]


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (dict, {"type": "object"}),
        (list, {"type": "array"}),
        (tuple, {"type": "array"}),
    ],
)
def test_bare_container_annotations_have_typed_schemas(annotation, expected) -> None:
    """Un-parameterized containers still produce a typed schema."""
    assert webmcp._annotation_schema(annotation) == expected
