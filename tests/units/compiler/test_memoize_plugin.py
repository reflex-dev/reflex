# ruff: noqa: D101

import dataclasses
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pytest
from reflex_base.components.component import Component, field
from reflex_base.components.memoize_helpers import (
    MemoizationStrategy,
    get_memoization_strategy,
)
from reflex_base.constants.compiler import MemoizationDisposition, MemoizationMode
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext
from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.base.bare import Bare
from reflex_components_core.base.fragment import Fragment

import reflex as rx
import reflex.compiler.plugins.memoize as memoize_plugin
from reflex.compiler.plugins import DefaultCollectorPlugin, default_page_plugins
from reflex.compiler.plugins.memoize import MemoizeStatefulPlugin, _should_memoize
from reflex.experimental.memo import (
    ExperimentalMemoComponent,
    create_passthrough_component_memo,
)
from reflex.state import BaseState

STATE_VAR = LiteralVar.create("value")._replace(
    merge_var_data=VarData(hooks={"useTestState": None}, state="TestState")
)


class Plain(Component):
    tag = "Plain"
    library = "plain-lib"


class WithProp(Component):
    tag = "WithProp"
    library = "with-prop-lib"

    label: Var[str] = field(default=LiteralVar.create(""))


class LeafComponent(Component):
    tag = "LeafComponent"
    library = "leaf-lib"
    _memoization_mode = MemoizationMode(recursive=False)


class SpecialFormMemoState(BaseState):
    items: list[str] = ["a"]
    flag: bool = True
    value: str = "a"


@dataclasses.dataclass(slots=True)
class FakePage:
    route: str
    component: Callable[[], Component]
    title: Any = None
    description: Any = None
    image: str = ""
    meta: tuple[dict[str, Any], ...] = ()


def _compile_single_page(
    component_factory: Callable[[], Component],
) -> tuple[CompileContext, PageContext]:
    ctx = CompileContext(
        pages=[FakePage(route="/p", component=component_factory)],
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )
    with ctx:
        ctx.compile()
    return ctx, ctx.compiled_pages["/p"]


def test_should_memoize_catches_direct_state_var_in_prop() -> None:
    """A component whose own prop carries state VarData should memoize."""
    comp = WithProp.create(label=STATE_VAR)
    assert _should_memoize(comp)


def test_should_not_memoize_state_var_in_child_bare() -> None:
    """A component whose Bare child contains state VarData should memoize."""
    comp = Plain.create(STATE_VAR)
    assert not _should_memoize(comp)


def test_should_not_memoize_plain_component() -> None:
    """A component with no state vars and no event triggers is not memoized."""
    comp = Plain.create(LiteralVar.create("static-content"))
    assert not _should_memoize(comp)


def test_should_memoize_state_var_in_child_cond() -> None:
    """A Bare containing state VarData should memoize."""
    comp = Bare.create(STATE_VAR)
    assert _should_memoize(comp)


def test_should_not_memoize_when_disposition_never() -> None:
    """``MemoizationDisposition.NEVER`` overrides heuristic eligibility."""
    comp = Plain.create(STATE_VAR)
    object.__setattr__(
        comp,
        "_memoization_mode",
        dataclasses.replace(
            comp._memoization_mode, disposition=MemoizationDisposition.NEVER
        ),
    )
    assert not _should_memoize(comp)


def test_memoize_wrapper_uses_experimental_memo_component_and_call_site() -> None:
    """Memoizable component imports a generated ``rx._x.memo`` wrapper."""
    ctx, page_ctx = _compile_single_page(lambda: Plain.create(STATE_VAR))

    assert len(ctx.memoize_wrappers) == 1
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    assert wrapper_tag in ctx.auto_memo_components
    output = page_ctx.output_code or ""
    assert f'import {{{wrapper_tag}}} from "$/utils/components/{wrapper_tag}"' in output
    assert f"jsx({wrapper_tag}," in (page_ctx.output_code or "")
    assert f"const {wrapper_tag} = memo" not in output


def test_memoize_wrapper_deduped_across_repeated_subtrees() -> None:
    """Two identical memoizable call-sites collapse to one memo definition."""
    ctx, page_ctx = _compile_single_page(
        lambda: Fragment.create(
            Plain.create(STATE_VAR),
            Plain.create(STATE_VAR),
        )
    )
    assert len(ctx.memoize_wrappers) == 1
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    assert list(ctx.auto_memo_components) == [wrapper_tag]
    assert (page_ctx.output_code or "").count(
        f'import {{{wrapper_tag}}} from "$/utils/components/{wrapper_tag}"'
    ) == 1


@pytest.mark.parametrize(
    ("special_form", "body_marker"),
    [
        ("foreach", "Array.prototype.map.call"),
        ("cond", "flag_rx_state_?"),
        ("match", "switch (JSON.stringify"),
    ],
)
def test_special_form_memo_wrappers_render_structural_body(
    special_form: str,
    body_marker: str,
) -> None:
    """Generated memo wrappers for special forms render the structural body.

    The memo body must subscribe to the state the special form references
    (via ``useContext(StateContexts...)``), and the page must not — otherwise
    the state-dependent render has leaked into page scope.
    """
    from reflex.compiler.compiler import compile_memo_components

    def special_child() -> Component:
        if special_form == "foreach":
            return rx.foreach(
                SpecialFormMemoState.items,
                lambda item: rx.text(item),
            )
        if special_form == "cond":
            return cast(
                Component,
                rx.cond(
                    SpecialFormMemoState.flag,
                    rx.text("yes"),
                    rx.text("no"),
                ),
            )
        return cast(
            Component,
            rx.match(
                SpecialFormMemoState.value,
                ("a", rx.text("A")),
                rx.text("default"),
            ),
        )

    ctx, page_ctx = _compile_single_page(lambda: rx.box(special_child()))

    memo_files, _memo_imports = compile_memo_components(
        components=(),
        experimental_memos=tuple(ctx.auto_memo_components.values()),
    )
    memo_code = "\n".join(code for _, code in memo_files)

    state_wiring = "useContext(StateContexts"
    assert state_wiring in memo_code
    assert state_wiring not in (page_ctx.output_code or "")
    assert body_marker in memo_code
    assert body_marker not in (page_ctx.output_code or "")


def test_common_memoization_snapshot_helper_classifies_snapshot_cases() -> None:
    """The shared memoization strategy covers leaves and structural forms."""
    from reflex_components_core.el.elements.forms import Form, Input

    foreach_parent = rx.box(
        rx.foreach(
            SpecialFormMemoState.items,
            lambda item: rx.text(item),
        )
    )
    cond_fragment = cast(
        Component,
        rx.cond(
            SpecialFormMemoState.flag,
            rx.text("yes"),
            rx.text("no"),
        ),
    )
    match_fragment = cast(
        Component,
        rx.match(
            SpecialFormMemoState.value,
            ("a", rx.text("A")),
            rx.text("default"),
        ),
    )

    assert get_memoization_strategy(foreach_parent) is MemoizationStrategy.SNAPSHOT
    assert get_memoization_strategy(cond_fragment) is MemoizationStrategy.SNAPSHOT
    assert get_memoization_strategy(match_fragment) is MemoizationStrategy.SNAPSHOT
    assert (
        get_memoization_strategy(LeafComponent.create(Plain.create()))
        is MemoizationStrategy.SNAPSHOT
    )

    form = Form.create(Input.create(name="username", id="username"))
    assert get_memoization_strategy(form) is MemoizationStrategy.PASSTHROUGH


def test_memoization_leaf_suppresses_descendant_wrapping() -> None:
    """A MemoizationLeaf suppresses independent wrappers for its descendants.

    Even when a descendant (``Plain(STATE_VAR)``) would otherwise be wrapped,
    being inside a leaf's subtree suppresses that wrapping. Whether or not the
    leaf itself gets wrapped, descendants do not produce their own wrappers.
    """
    ctx, _page_ctx = _compile_single_page(
        lambda: LeafComponent.create(
            Plain.create(STATE_VAR),  # would otherwise be independently memoized
        )
    )
    # The inner Plain(STATE_VAR) is suppressed because it's inside the leaf's
    # subtree. The leaf itself has no direct state dependency so no wrapper
    # is emitted for it either.
    assert len(ctx.memoize_wrappers) == 0


def test_generated_memo_component_is_not_itself_memoized() -> None:
    """The generated memo component instance itself is skipped by the heuristic."""
    wrapper_factory, _definition = create_passthrough_component_memo(
        "MyTag", Fragment.create()
    )
    wrapper = wrapper_factory(Plain.create())
    assert isinstance(wrapper, ExperimentalMemoComponent)
    assert not _should_memoize(wrapper)


def test_event_trigger_memoization_not_emit_usecallback_in_page_hooks() -> None:
    """Components with event triggers do not get useCallback wrappers at the page level."""
    from reflex_base.event import EventChain

    # Construct an event chain referencing state so _get_memoized_event_triggers
    # emits a useCallback.
    event_var = Var(_js_expr="test_event")._replace(
        _var_type=EventChain,
        merge_var_data=VarData(state="TestState"),
    )
    comp = Plain.create()
    comp.event_triggers["on_click"] = event_var

    _ctx, page_ctx = _compile_single_page(lambda: comp)

    # Check that a useCallback hook line was added to the page hooks dict.
    hook_lines = list(page_ctx.hooks.keys())
    assert not any(
        "useCallback" in hook_line and "on_click_" in hook_line
        for hook_line in hook_lines
    ), f"Expected no on_click useCallback hook in {hook_lines!r}"


def test_generated_memo_component_renders_as_its_exported_tag() -> None:
    """The generated experimental memo component renders as its exported tag."""
    wrapper_factory, definition = create_passthrough_component_memo(
        "MyWrapper_abc", Fragment.create()
    )
    wrapper = wrapper_factory(Plain.create())
    assert isinstance(wrapper, ExperimentalMemoComponent)
    assert wrapper.tag == "MyWrapper_abc"
    assert definition.export_name == "MyWrapper_abc"
    assert wrapper.render()["name"] == "MyWrapper_abc"


def test_passthrough_memo_definitions_are_not_shared_globally(monkeypatch) -> None:
    """Repeated tags across compiles rebuild their passthrough definitions.

    Regression: sharing auto-memo definitions globally by tag leaks the first
    app's captured component tree into later compiles, which can stale-bind
    state event names across AppHarness apps.
    """
    tag = "SharedMemoTag"
    first_component = Plain.create(STATE_VAR)
    second_component = Plain.create(STATE_VAR)

    monkeypatch.setattr(memoize_plugin, "_compute_memo_tag", lambda comp: tag)
    monkeypatch.setattr(
        memoize_plugin,
        "fix_event_triggers_for_memo",
        lambda comp, page_context: comp,
    )

    def fake_create_passthrough_component_memo(
        export_name: str,
        component: Component,
    ):
        definition = SimpleNamespace(export_name=export_name, component=component)
        return (lambda definition=definition: definition), definition

    monkeypatch.setattr(
        memoize_plugin,
        "create_passthrough_component_memo",
        fake_create_passthrough_component_memo,
    )

    first_compile = SimpleNamespace(memoize_wrappers={}, auto_memo_components={})
    second_compile = SimpleNamespace(memoize_wrappers={}, auto_memo_components={})
    page_context = cast(PageContext, SimpleNamespace())

    MemoizeStatefulPlugin._build_wrapper(
        first_component,
        page_context=page_context,
        compile_context=first_compile,
    )
    MemoizeStatefulPlugin._build_wrapper(
        second_component,
        page_context=page_context,
        compile_context=second_compile,
    )

    first_definition = first_compile.auto_memo_components[tag]
    second_definition = second_compile.auto_memo_components[tag]
    assert first_definition.component is first_component
    assert second_definition.component is second_component
    assert second_definition is not first_definition


def test_shared_subtree_across_pages_uses_same_tag() -> None:
    """The same memoizable subtree on multiple pages gets one shared tag."""
    ctx = CompileContext(
        pages=[
            FakePage(route="/a", component=lambda: Plain.create(STATE_VAR)),
            FakePage(route="/b", component=lambda: Plain.create(STATE_VAR)),
        ],
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )
    with ctx:
        ctx.compile()

    assert len(ctx.memoize_wrappers) == 1
    tag = next(iter(ctx.memoize_wrappers))
    assert list(ctx.auto_memo_components) == [tag]
    for route in ("/a", "/b"):
        output = ctx.compiled_pages[route].output_code or ""
        assert f'import {{{tag}}} from "$/utils/components/{tag}"' in output
        assert f"jsx({tag}," in output


def test_shared_parent_instance_across_pages_preserves_original() -> None:
    """A parent instance reused across pages must not have its children rebound.

    Regression: the compile walker replaces memoizable descendants with memo
    wrappers and writes the new children list onto their parent. If the parent
    is the same Python object on two pages (e.g. a module-scope layout), page
    A's compile would mutate page B's starting tree, producing a ``ReferenceError``
    for the memo tag on the second page.
    """
    shared_parent = Fragment.create(WithProp.create(label=STATE_VAR))
    original_children = list(shared_parent.children)
    original_child = shared_parent.children[0]

    ctx = CompileContext(
        pages=[
            FakePage(route="/a", component=lambda: shared_parent),
            FakePage(route="/b", component=lambda: shared_parent),
        ],
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )
    with ctx:
        ctx.compile()

    assert shared_parent.children == original_children, (
        f"shared parent's children mutated: {shared_parent.children!r}"
    )
    assert shared_parent.children[0] is original_child, (
        "shared parent's child reference replaced by a memo wrapper"
    )

    assert len(ctx.memoize_wrappers) == 1
    tag = next(iter(ctx.memoize_wrappers))
    for route in ("/a", "/b"):
        output = ctx.compiled_pages[route].output_code or ""
        assert f'import {{{tag}}} from "$/utils/components/{tag}"' in output, (
            f"route {route} missing memo tag import"
        )
        assert f"jsx({tag}," in output, f"route {route} does not render the memo tag"


def test_shared_nested_parent_mirroring_common_elements_preserves_original() -> None:
    """Deeper nested shape — mirrors ``common_elements`` in test_event_chain.

    ``common_elements`` is an outer ``rx.vstack`` that contains an inner
    ``rx.vstack(rx.foreach(...))`` memoizable subtree. The walker must clone
    the entire spine from the memoized descendant up to the shared root, not
    just the immediate parent.
    """
    inner_parent = Fragment.create(WithProp.create(label=STATE_VAR))
    shared_outer = Fragment.create(
        WithProp.create(label=LiteralVar.create("static")),
        inner_parent,
        WithProp.create(label=LiteralVar.create("trailing")),
    )
    original_outer_children = list(shared_outer.children)
    original_inner = shared_outer.children[1]
    original_inner_children = list(inner_parent.children)
    original_innermost = inner_parent.children[0]

    ctx = CompileContext(
        pages=[
            FakePage(route="/a", component=lambda: shared_outer),
            FakePage(route="/b", component=lambda: shared_outer),
            FakePage(route="/c", component=lambda: shared_outer),
        ],
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )
    with ctx:
        ctx.compile()

    assert shared_outer.children == original_outer_children
    assert shared_outer.children[1] is original_inner
    assert inner_parent.children == original_inner_children
    assert inner_parent.children[0] is original_innermost

    assert len(ctx.memoize_wrappers) == 1
    tag = next(iter(ctx.memoize_wrappers))
    for route in ("/a", "/b", "/c"):
        output = ctx.compiled_pages[route].output_code or ""
        assert f'import {{{tag}}} from "$/utils/components/{tag}"' in output
        assert f"jsx({tag}," in output


def test_memoization_leaf_internal_hooks_do_not_leak_into_page() -> None:
    """Hooks from a ``MemoizationLeaf``'s internal children stay in its memo body.

    ``MemoizationLeaf``-derived components (e.g. ``rx.upload.root``) build
    internal machinery as their own structural children, attaching stateful
    hooks via ``special_props``/``VarData``. Those hooks belong to the memo
    component's function body — not to the page — because the whole point of
    the leaf is to isolate its subtree from page-level re-renders.

    The test asserts both directions: the hook lines do not appear in the
    page's collected hooks, *and* they do appear in the compiled memo module
    (otherwise a regression that drops them entirely would pass the negative
    check).
    """
    from reflex_base.components.component import MemoizationLeaf
    from reflex_base.event import EventChain
    from reflex_base.vars.base import Var

    from reflex.compiler.compiler import compile_memo_components

    class StatefulLeaf(MemoizationLeaf):
        tag = "StatefulLeaf"
        library = "stateful-leaf-lib"

        @classmethod
        def create(cls, *children, **props):
            # Simulate what rx.upload.root does: build an internal child whose
            # special_props carry stateful hook lines via VarData.
            internal_hook_var = Var(
                _js_expr="__internal_leaf_probe()",
                _var_type=None,
                _var_data=VarData(
                    hooks={
                        "const __internal_leaf_probe = useLeafProbe();": None,
                        "const on_drop_xyz = useCallback(() => {}, []);": None,
                    },
                    state="LeafState",
                ),
            )
            internal_child = Plain.create(*children)
            internal_child.special_props = [internal_hook_var]
            return super().create(internal_child, **props)

    stateful_event = Var(_js_expr="evt")._replace(
        _var_type=EventChain,
        merge_var_data=VarData(state="LeafState"),
    )
    leaf = StatefulLeaf.create()
    leaf.event_triggers["on_something"] = stateful_event

    ctx, page_ctx = _compile_single_page(lambda: leaf)

    page_hook_lines = list(page_ctx.hooks)
    leaking_hooks = [
        hook
        for hook in page_hook_lines
        if "useLeafProbe" in hook or "on_drop_xyz" in hook
    ]
    assert not leaking_hooks, (
        f"MemoizationLeaf internal hooks leaked into page: {leaking_hooks!r}"
    )

    # The hooks must survive somewhere — in the compiled memo module for the
    # generated leaf wrapper. Compile the auto-memo definitions collected
    # during the page compile and check that the hook lines are present.
    assert ctx.auto_memo_components, (
        "expected an auto-memo wrapper to be generated for the leaf"
    )
    memo_files, _memo_imports = compile_memo_components(
        components=(),
        experimental_memos=tuple(ctx.auto_memo_components.values()),
    )
    memo_code = "\n".join(code for _, code in memo_files)
    assert "useLeafProbe" in memo_code, (
        "leaf's internal probe hook was dropped from the memo module"
    )
    assert "on_drop_xyz" in memo_code, (
        "leaf's internal useCallback hook was dropped from the memo module"
    )


def test_plugin_only_registered_once_in_default_page_plugins() -> None:
    """MemoizeStatefulPlugin appears exactly once in the default plugin pipeline."""
    plugins = default_page_plugins()
    memoize_plugins = [p for p in plugins if isinstance(p, MemoizeStatefulPlugin)]
    assert len(memoize_plugins) == 1
    # And it is registered after the DefaultCollectorPlugin.
    collector_index = next(
        i for i, p in enumerate(plugins) if isinstance(p, DefaultCollectorPlugin)
    )
    memoize_index = plugins.index(memoize_plugins[0])
    assert memoize_index > collector_index
