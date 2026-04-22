# ruff: noqa: D101

import dataclasses
from collections.abc import Callable
from typing import Any

from reflex_base.components.component import Component, field
from reflex_base.constants.compiler import MemoizationDisposition, MemoizationMode
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext
from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.base.bare import Bare
from reflex_components_core.base.fragment import Fragment

from reflex.compiler.plugins import DefaultCollectorPlugin, default_page_plugins
from reflex.compiler.plugins.memoize import MemoizeStatefulPlugin, _should_memoize
from reflex.experimental.memo import (
    ExperimentalMemoComponent,
    create_passthrough_component_memo,
)

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
    assert f'import {{{wrapper_tag}}} from "$/utils/components"' in output
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
        f'import {{{wrapper_tag}}} from "$/utils/components"'
    ) == 1


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
        assert f'import {{{tag}}} from "$/utils/components"' in output
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
    _output_path, memo_code, _memo_imports = compile_memo_components(
        components=(),
        experimental_memos=tuple(ctx.auto_memo_components.values()),
    )
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
