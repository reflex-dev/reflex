# ruff: noqa: D101

import dataclasses
import re
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from reflex_base.components.component import Component
from reflex_base.components.component import field as component_field
from reflex_base.components.memoize_helpers import (
    MemoizationStrategy,
    get_memoization_strategy,
)
from reflex_base.constants.compiler import MemoizationDisposition, MemoizationMode
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext
from reflex_base.vars import VarData
from reflex_base.vars.base import Field, LiteralVar, Var, field
from reflex_components_core.base.bare import Bare
from reflex_components_core.base.fragment import Fragment
from reflex_components_core.base.link import RawLink, ScriptTag
from reflex_components_core.core.foreach import Foreach
from reflex_components_core.el.elements.forms import BaseInput, Textarea
from reflex_components_core.el.elements.inline import Br, Wbr
from reflex_components_core.el.elements.media import (
    Area,
    Desc,
    Embed,
    Img,
    Source,
    SvgStyle,
    Track,
)
from reflex_components_core.el.elements.media import Script as SvgScript
from reflex_components_core.el.elements.media import Title as SvgTitle
from reflex_components_core.el.elements.metadata import Base, Link, Meta, StyleEl, Title
from reflex_components_core.el.elements.scripts import Noscript, Script
from reflex_components_core.el.elements.tables import Col
from reflex_components_core.el.elements.typography import Hr
from reflex_components_radix.themes.layout.box import Box

import reflex as rx
import reflex.compiler.plugins.memoize as memoize_plugin
from reflex.compiler.plugins import DefaultCollectorPlugin, default_page_plugins
from reflex.compiler.plugins.memoize import MemoizeStatefulPlugin, _should_memoize
from reflex.experimental.memo import (
    ExperimentalMemoComponent,
    ExperimentalMemoComponentDefinition,
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

    label: Var[str] = component_field(default=LiteralVar.create(""))


class LeafComponent(Component):
    tag = "LeafComponent"
    library = "leaf-lib"
    _memoization_mode = MemoizationMode(recursive=False)


class ChildrenViaProp(Component):
    """Stub mirroring ``CodeBlock`` — injects its content as ``children`` prop."""

    tag = "ChildrenViaProp"
    library = "children-via-prop-lib"

    code: Var[str] = component_field(default=LiteralVar.create(""))

    def _render(self):
        return super()._render().remove_props("code").add_props(children=self.code)


class SpecialFormMemoState(BaseState):
    items: Field[list[str]] = field(default_factory=lambda: ["a"])
    flag: Field[bool] = field(default=True)
    value: Field[str] = field(default="a")


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


def test_should_not_memoize_prop_var_with_imports_only_var_data() -> None:
    """Prop Vars carrying only imports (no state/hooks) must not trigger memoize.

    Regression: a ``class_name`` produced by the ``cn`` helper (clsx-for-tailwind)
    has VarData with non-empty ``imports`` but empty ``state`` and ``hooks``;
    snapshot-boundary elements like ``<textarea>`` were being wrapped in memo
    purely because of that helper import.
    """
    from reflex_base.utils.imports import ImportVar

    import_only_var = LiteralVar.create("static-class")._replace(
        merge_var_data=VarData(
            imports={"clsx-for-tailwind": [ImportVar(tag="cn")]},
        )
    )
    comp = WithProp.create(label=import_only_var)
    assert not _should_memoize(comp)
    # Snapshot-boundary form of the same: a Textarea whose only stateful-looking
    # signal is an import-bearing class_name should not be memoized either.
    boundary = Textarea.create(class_name=import_only_var, name="x")
    assert not _should_memoize(boundary)
    # And the Bare-contents short-circuit must use the same predicate: a Bare
    # wrapping a Var with import-only var_data must not be memoized.
    bare = Bare.create(import_only_var)
    assert not _should_memoize(bare)


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


def test_memoize_wrappers_distinct_for_different_on_mount() -> None:
    """Two components differing only in ``on_mount`` must NOT dedupe.

    ``on_mount`` is excluded from ``_render``'s props, so its handler does not
    appear in ``component.render()``. The memo wrapper body, however, includes
    a ``useEffect`` lifecycle hook whose body invokes the ``on_mount`` handler
    — two distinct handlers produce two distinct memo bodies and must compile
    to two distinct memo wrappers. Hashing only ``render()`` lets them collide
    on a single tag, silently dropping one handler's logic.
    """
    ctx, _page_ctx = _compile_single_page(
        lambda: Fragment.create(
            Plain.create(on_mount=rx.console_log("a")),
            Plain.create(on_mount=rx.console_log("b")),
        )
    )
    assert len(ctx.memoize_wrappers) == 2, (
        "Components with different on_mount handlers must produce distinct "
        f"memo wrappers, got: {list(ctx.memoize_wrappers)}"
    )


def test_memoize_wrappers_dedupe_passthrough_with_different_children() -> None:
    """Passthrough memos with identical props but different children must dedupe.

    Passthrough memo bodies render a ``{children}`` placeholder rather than
    the captured child JSX — the actual children flow through at the page-side
    call site. Two components with identical props but different children
    therefore generate identical memo body code and must share one wrapper
    tag. Hashing the rendered children into the tag splits them needlessly,
    bloating the generated component module with duplicate definitions.
    """
    ctx, _page_ctx = _compile_single_page(
        lambda: Fragment.create(
            WithProp.create("apple", label=STATE_VAR),
            WithProp.create("banana", label=STATE_VAR),
        )
    )
    assert len(ctx.memoize_wrappers) == 1, (
        "Passthrough memos differing only in children must collapse to one "
        f"wrapper, got: {list(ctx.memoize_wrappers)}"
    )


@pytest.mark.parametrize(
    ("special_form", "body_marker"),
    [
        ("foreach", "Array.prototype.map.call"),
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
    page_output = page_ctx.output_code
    assert page_output is not None
    assert state_wiring in memo_code
    assert state_wiring not in page_output
    assert body_marker in memo_code
    assert body_marker not in page_output


def test_foreach_parent_does_not_absorb_sibling_into_snapshot() -> None:
    """Foreach owns its own snapshot while the parent stays passthrough.

    Regression for the foreach-parent memoization fix: a parent component
    holding a Foreach used to be promoted to SNAPSHOT, absorbing any sibling
    reactive content into the same wide memo body. The parent should now render
    on the page side, with Foreach and any reactive sibling each getting their
    own independent wrapper.
    """
    ctx, _page_ctx = _compile_single_page(
        lambda: rx.box(
            Bare.create(SpecialFormMemoState.items.length()),
            rx.foreach(
                SpecialFormMemoState.items,
                lambda item: rx.text(item),
            ),
        )
    )

    wrapped_definitions = [
        definition
        for definition in ctx.auto_memo_components.values()
        if isinstance(definition, ExperimentalMemoComponentDefinition)
    ]
    wrapped_types = {type(definition.component) for definition in wrapped_definitions}

    assert len(wrapped_definitions) == 2
    assert Box not in wrapped_types

    foreach_definition = next(
        definition
        for definition in wrapped_definitions
        if isinstance(definition.component, Foreach)
    )
    assert (
        get_memoization_strategy(foreach_definition.component)
        is MemoizationStrategy.SNAPSHOT
    )

    bare_definition = next(
        definition
        for definition in wrapped_definitions
        if isinstance(definition.component, Bare)
    )
    assert (
        get_memoization_strategy(bare_definition.component)
        is MemoizationStrategy.PASSTHROUGH
    )
    assert bare_definition is not foreach_definition


def test_common_memoization_snapshot_helper_classifies_snapshot_cases() -> None:
    """The shared memoization strategy classifies structural render forms."""
    from reflex_components_core.core.cond import Cond
    from reflex_components_core.core.foreach import Foreach
    from reflex_components_core.core.match import Match
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

    # A parent with a structural-memoization child (Foreach) is itself
    # PASSTHROUGH — the snapshotting is owned by the structural child, which
    # captures its whole subtree.
    assert get_memoization_strategy(foreach_parent) is MemoizationStrategy.PASSTHROUGH
    foreach_child = foreach_parent.children[0]
    assert isinstance(foreach_child, Foreach)
    assert get_memoization_strategy(foreach_child) is MemoizationStrategy.SNAPSHOT
    assert get_memoization_strategy(cond_fragment) is MemoizationStrategy.PASSTHROUGH
    # Cond and Match now use passthrough so branch JSX renders on the page side
    # and the memo body just selects via children[i] indexing.
    assert isinstance(cond_fragment.children[0], Cond)
    assert (
        get_memoization_strategy(cond_fragment.children[0])
        is MemoizationStrategy.PASSTHROUGH
    )
    assert isinstance(match_fragment.children[0], Match)
    assert (
        get_memoization_strategy(match_fragment.children[0])
        is MemoizationStrategy.PASSTHROUGH
    )
    assert (
        get_memoization_strategy(LeafComponent.create(Plain.create()))
        is MemoizationStrategy.SNAPSHOT
    )

    form = Form.create(Input.create(name="username", id="username"))
    assert get_memoization_strategy(form) is MemoizationStrategy.PASSTHROUGH


def test_generated_memo_component_is_not_itself_memoized() -> None:
    """The generated memo component instance itself is skipped by the heuristic."""
    wrapper_factory, _definition = create_passthrough_component_memo(Fragment.create())
    wrapper = wrapper_factory(Plain.create())
    assert isinstance(wrapper, ExperimentalMemoComponent)
    assert not _should_memoize(wrapper)


def test_passthrough_memo_skips_hole_for_childless_component() -> None:
    """Childless components own their JSX output, so the wrapper must not
    inject a ``{children}`` hole.

    Regression: components like ``CodeBlock`` set ``children`` on their own
    rendered Tag via ``_render``. Substituting a ``Bare({children})`` hole
    would emit ``jsx(Inner, {children: "..."}, hole)``, and at call time the
    undefined hole arg overwrites ``props.children`` under Emotion's jsx
    semantics — causing every reactive ``rx.code_block`` to render an empty
    ``<code>`` element.
    """
    component = ChildrenViaProp.create(code=STATE_VAR)
    assert not component.children
    _wrapper_factory, definition = create_passthrough_component_memo(component)
    assert definition.passthrough_hole_child is None


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
    wrapper_factory, definition = create_passthrough_component_memo(Fragment.create())
    wrapper = wrapper_factory(Plain.create())
    assert isinstance(wrapper, ExperimentalMemoComponent)
    tag = definition.export_name
    assert tag.startswith("Fragment_"), (
        f"Expected the wrapped class qualname to be encoded in the tag prefix; "
        f"got {tag!r}"
    )
    assert wrapper.tag == tag
    assert wrapper.render()["name"] == tag


def test_passthrough_memo_definitions_are_not_shared_globally(monkeypatch) -> None:
    """Repeated tags across compiles rebuild their passthrough definitions.

    Regression: sharing auto-memo definitions globally by tag leaks the first
    app's captured component tree into later compiles, which can stale-bind
    state event names across AppHarness apps.
    """
    tag = "SharedMemoTag"
    first_component = Plain.create(STATE_VAR)
    second_component = Plain.create(STATE_VAR)

    monkeypatch.setattr(
        memoize_plugin,
        "fix_event_triggers_for_memo",
        lambda comp, page_context: comp,
    )

    def fake_create_passthrough_component_memo(component: Component):
        definition = SimpleNamespace(export_name=tag, component=component)
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


def test_match_non_stateful_cond_allows_stateful_children_to_memoize() -> None:
    """Match with a non-stateful condition must not suppress child memoization.

    Regression: Match was a MemoizationLeaf, causing it to push onto the
    suppressor stack when its condition had no VarData. That blocked
    independently-stateful children from being wrapped. After the fix Match
    is a plain Component and its stateful children are memoized normally.
    """

    def page() -> Component:
        comp = rx.match(
            "static",  # non-stateful condition
            ("a", WithProp.create(label=STATE_VAR)),
            WithProp.create(label=LiteralVar.create("default")),
        )
        assert isinstance(comp, Component)
        return comp

    ctx, _page_ctx = _compile_single_page(page)
    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected the stateful WithProp inside match cases to be memoized, "
        f"got wrappers: {list(ctx.memoize_wrappers)}"
    )


def test_cond_non_stateful_cond_allows_stateful_children_to_memoize() -> None:
    """Cond with a non-stateful condition must not suppress child memoization.

    When the condition carries no VarData, Cond should not be extracted to its
    own memo component. Its stateful children (comp1 / comp2) should still be
    independently memoized.
    """

    def page() -> Component:
        comp = rx.cond(
            True,  # non-stateful condition
            WithProp.create(label=STATE_VAR),
            WithProp.create(label=LiteralVar.create("false-branch")),
        )
        assert isinstance(comp, Component)
        return comp

    ctx, _page_ctx = _compile_single_page(page)
    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected the stateful WithProp inside cond branch to be memoized, "
        f"got wrappers: {list(ctx.memoize_wrappers)}"
    )


def test_cond_and_match_strategy_classification() -> None:
    """Cond and Match both use passthrough; branches render on the page side."""
    from reflex_components_core.core.cond import Cond
    from reflex_components_core.core.match import Match

    cond_non_stateful = rx.cond(
        True,
        rx.text("yes"),
        rx.text("no"),
    )
    cond_stateful = rx.cond(
        SpecialFormMemoState.flag,
        rx.text("yes"),
        rx.text("no"),
    )
    match_non_stateful = rx.match(
        "static",
        ("a", rx.text("A")),
        rx.text("default"),
    )
    match_stateful = rx.match(
        SpecialFormMemoState.value,
        ("a", rx.text("A")),
        rx.text("default"),
    )

    for comp in (cond_non_stateful, cond_stateful):
        assert isinstance(comp, Component)
        assert get_memoization_strategy(comp) is MemoizationStrategy.PASSTHROUGH
        assert isinstance(comp.children[0], Cond)
        assert (
            get_memoization_strategy(comp.children[0])
            is MemoizationStrategy.PASSTHROUGH
        )

    for comp in (match_non_stateful, match_stateful):
        assert isinstance(comp, Component)
        assert isinstance(comp.children[0], Match)
        assert (
            get_memoization_strategy(comp.children[0])
            is MemoizationStrategy.PASSTHROUGH
        )


def test_cond_stateful_var_branch_memoized_as_bare() -> None:
    """rx.cond(True, STATE_VAR, "false") embeds a stateful ternary Var in a Bare.

    The ternary Var produced by the Var-returning cond path carries STATE_VAR's
    VarData. When rendered inside rx.box it appears as a Bare child, which must
    be extracted into its own memoized component.
    """
    ctx, _page_ctx = _compile_single_page(
        lambda: rx.box(rx.cond(True, STATE_VAR, "false")),
    )
    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected stateful cond ternary var to produce one memoized Bare, "
        f"got wrappers: {list(ctx.memoize_wrappers)}"
    )


def test_cond_stateful_condition_memoizes_whole_cond_and_stateful_branch() -> None:
    """Stateful Cond condition memoizes both Cond and stateful branch.

    Cond should recurse into branches so stateful branch components are wrapped
    independently, while the Cond itself is also wrapped because its condition
    var reads state.
    """

    def page() -> Component:
        comp = rx.cond(
            SpecialFormMemoState.flag,
            WithProp.create(label=STATE_VAR),
            WithProp.create(label=LiteralVar.create("false-branch")),
        )
        assert isinstance(comp, Component)
        return comp

    ctx, _page_ctx = _compile_single_page(page)

    assert len(ctx.memoize_wrappers) == 2, (
        "Expected both Cond and its stateful branch component to be memoized, "
        f"got wrappers: {list(ctx.memoize_wrappers)}"
    )
    wrapper_tags = tuple(ctx.memoize_wrappers)
    assert any("cond" in tag.lower() for tag in wrapper_tags)
    assert any("withprop" in tag.lower() for tag in wrapper_tags)


def test_match_stateful_condition_memoizes_whole_match_and_stateful_branch() -> None:
    """Stateful Match condition memoizes both Match and stateful branch.

    Match should recurse into branches so stateful branch components are
    memoized independently, while Match itself is memoized when its condition
    var carries VarData.
    """

    def page() -> Component:
        comp = rx.match(
            SpecialFormMemoState.value,
            ("a", WithProp.create(label=STATE_VAR)),
            WithProp.create(label=LiteralVar.create("default")),
        )
        assert isinstance(comp, Component)
        return comp

    ctx, _page_ctx = _compile_single_page(page)
    assert len(ctx.memoize_wrappers) == 2, (
        "Expected both Match and its stateful branch component to be memoized, "
        f"got wrappers: {list(ctx.memoize_wrappers)}"
    )
    wrapper_tags = tuple(ctx.memoize_wrappers)
    assert any("match" in tag.lower() for tag in wrapper_tags)
    assert any("withprop" in tag.lower() for tag in wrapper_tags)


def test_cond_stateful_branch_component_renders_via_memoized_wrapper() -> None:
    """Components inside Cond branches must render via their memo wrappers.

    Regression shape matching the Match case: when the walker memoizes a
    branch component, Cond rendering must use the wrapped branch tag in page
    output rather than the original unwrapped component tag.
    """

    def page() -> Component:
        comp = rx.cond(
            True,
            WithProp.create(label=STATE_VAR),
            WithProp.create(label=LiteralVar.create("false-branch")),
        )
        assert isinstance(comp, Component)
        return comp

    ctx, page_ctx = _compile_single_page(page)
    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected stateful branch to produce one memo wrapper, got: {list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    output = page_ctx.output_code or ""
    assert f"jsx({wrapper_tag}," in output, (
        f"Memo wrapper {wrapper_tag!r} not found in page output.\n"
        f"Output snippet: {output[:2000]}"
    )


def test_cond_stateful_condition_renders_branch_logic_in_memo_body() -> None:
    """Stateful Cond memo body must select both branches via ``children`` indexing.

    Cond is now a passthrough wrapper: branch JSX is rendered on the page side
    and passed as the ``children`` array. The memo body's ternary must select
    ``children[0]`` for the true branch and ``children[1]`` for the false
    branch — neither branch should collapse to a generic ``? children`` hole
    nor inline the original branch text into the memo body.
    """
    from reflex.compiler.compiler import compile_memo_components

    def page() -> Component:
        comp = rx.cond(
            SpecialFormMemoState.flag,
            rx.text("yes"),
            rx.text("no"),
        )
        assert isinstance(comp, Component)
        return comp

    ctx, page_ctx = _compile_single_page(page)
    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected stateful Cond to produce one memo wrapper, got: {list(ctx.memoize_wrappers)}"
    )

    memo_files, _memo_imports = compile_memo_components(
        components=(),
        experimental_memos=tuple(ctx.auto_memo_components.values()),
    )
    memo_code = "\n".join(code for _, code in memo_files)

    assert "children?.at?.(0)" in memo_code, (
        "Cond memo body should select the true branch via children[0].\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    assert "children?.at?.(1)" in memo_code, (
        "Cond memo body should select the false branch via children[1].\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    assert '"yes"' not in memo_code, (
        "Cond memo body unexpectedly inlined the true branch.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    assert '"no"' not in memo_code, (
        "Cond memo body unexpectedly inlined the false branch.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )

    page_output = page_ctx.output_code or ""
    assert '"yes"' in page_output, (
        "Page output should render the true branch as a memo wrapper child.\n"
        f"Page output snippet: {page_output[:2000]}"
    )
    assert '"no"' in page_output, (
        "Page output should render the false branch as a memo wrapper child.\n"
        f"Page output snippet: {page_output[:2000]}"
    )


def test_match_stateful_branch_component_renders_via_memoized_wrapper() -> None:
    """Components inside Match branches must be rendered via their memo wrappers.

    Regression: Match._render() used self.match_cases / self.default directly
    instead of self.children. The walker updates children when it memoizes a
    branch component, but those updates were invisible to Match's render, so
    the generated page JSX still referenced the original unwrapped component
    tag rather than the memo wrapper.
    """

    def page() -> Component:
        comp = rx.match(
            "static",
            ("a", WithProp.create(label=STATE_VAR)),
            WithProp.create(label=LiteralVar.create("default")),
        )
        assert isinstance(comp, Component)
        return comp

    ctx, page_ctx = _compile_single_page(page)
    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected stateful branch to produce one memo wrapper, got: {list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    output = page_ctx.output_code or ""
    assert f"jsx({wrapper_tag}," in output, (
        f"Memo wrapper {wrapper_tag!r} not found in page output.\n"
        f"Output snippet: {output[:2000]}"
    )


def test_match_stateful_condition_uses_memoized_branch_wrapper_in_memo_body() -> None:
    """Stateful Match passes branch wrappers as page-side children.

    Match is now a passthrough wrapper: when both the match condition and a
    branch are stateful, the Match wrapper itself is memoized and the branch
    is memoized separately. The Match memo body selects via ``children[i]``
    indexing, and the page output renders the branch wrapper as a child of
    the Match wrapper (rather than inlining the unwrapped branch component).
    """
    from reflex.compiler.compiler import compile_memo_components

    def page() -> Component:
        comp = rx.match(
            SpecialFormMemoState.value,
            ("a", WithProp.create(label=STATE_VAR)),
            WithProp.create(label=LiteralVar.create("default")),
        )
        assert isinstance(comp, Component)
        return comp

    ctx, page_ctx = _compile_single_page(page)
    assert len(ctx.memoize_wrappers) == 2, (
        "Expected both Match and its stateful branch component to be memoized, "
        f"got wrappers: {list(ctx.memoize_wrappers)}"
    )

    match_wrapper_tag = next(
        tag for tag in ctx.memoize_wrappers if "match" in tag.lower()
    )
    branch_wrapper_tag = next(
        tag for tag in ctx.memoize_wrappers if "withprop" in tag.lower()
    )

    memo_files, _memo_imports = compile_memo_components(
        components=(),
        experimental_memos=tuple(ctx.auto_memo_components.values()),
    )
    match_memo_code = next(
        code
        for path, code in memo_files
        if Path(path).name == f"{match_wrapper_tag}.jsx"
    )

    assert "children?.at?.(0)" in match_memo_code, (
        "Match memo body should select case 0 via children indexing.\n"
        f"Memo code snippet: {match_memo_code[:2000]}"
    )
    assert "children?.at?.(1)" in match_memo_code, (
        "Match memo body should select the default via children indexing.\n"
        f"Memo code snippet: {match_memo_code[:2000]}"
    )
    assert f"jsx({branch_wrapper_tag}," not in match_memo_code, (
        "Match memo body should not inline the branch wrapper; the branch "
        "renders on the page side as a memo wrapper child.\n"
        f"Memo code snippet: {match_memo_code[:2000]}"
    )

    page_output = page_ctx.output_code or ""
    assert f"jsx({match_wrapper_tag}," in page_output, (
        f"Page output should render the Match memo wrapper {match_wrapper_tag!r}.\n"
        f"Output snippet: {page_output[:2000]}"
    )
    assert f"jsx({branch_wrapper_tag}," in page_output, (
        f"Page output should render the branch memo wrapper {branch_wrapper_tag!r} "
        "as a child of the Match wrapper.\n"
        f"Output snippet: {page_output[:2000]}"
    )


def test_memoized_match_wrapper_receives_case_children_in_page_output() -> None:
    """Passthrough Match wrapper receives all case children from the page output.

    With Match handled as a passthrough memo, the page renders each case's JSX
    as a child of the Match wrapper. The memo body selects which child to mount
    via ``children[i]`` indexing keyed on the (possibly stateful) condition.
    """

    def page() -> Component:
        comp = rx.match(
            SpecialFormMemoState.value,
            ("a", rx.text("A")),
            ("b", rx.text("B")),
            rx.text("default"),
        )
        assert isinstance(comp, Component)
        return comp

    ctx, page_ctx = _compile_single_page(page)
    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected stateful Match to produce one memo wrapper, got: {list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    output = page_ctx.output_code or ""

    assert f"jsx({wrapper_tag}," in output, (
        f"Memo wrapper {wrapper_tag!r} not found in page output.\n"
        f"Output snippet: {output[:2000]}"
    )
    # Each case-return JSX, plus the default, must reach the wrapper as a child.
    for case_text in ('"A"', '"B"', '"default"'):
        assert case_text in output, (
            f"Expected case JSX {case_text} in page output as a Match wrapper child.\n"
            f"Output snippet: {output[:2000]}"
        )
    # Match wrapper must be called with three positional children (the cases plus
    # default), not as an empty-children call.
    assert re.search(
        rf"jsx\({re.escape(wrapper_tag)},\s*\{{\}},\s*jsx\(",
        output,
    ), (
        "Match wrapper should receive case JSX as positional children in page output.\n"
        f"Output snippet: {output[:2000]}"
    )


def test_client_state_setter_in_call_function_event_imports_refs() -> None:
    """A button whose ``on_click`` calls a global ``ClientStateVar`` setter
    must memoize and the resulting memo body's imports must include ``refs``
    from ``$/utils/state``.

    Regression: ``ClientStateVar.set_value`` builds its setter as
    ``refs['_client_state_<setter>']`` but the returned setter ``Var`` does not
    carry the ``refs`` import. When the on_click event chain is compiled into
    the memo body, the body references ``refs['_client_state_<setter>'](42)``
    with no matching ``import { refs } from "$/utils/state"`` — producing a
    ``ReferenceError: refs is not defined`` at runtime.
    """
    from reflex.compiler.compiler import compile_memo_components
    from reflex.experimental.client_state import ClientStateVar

    counter = ClientStateVar.create("counter", default=0)

    def page() -> Component:
        return rx.el.button(
            "click",
            on_click=rx.call_function(counter.set_value(42)),
        )

    ctx, _page_ctx = _compile_single_page(page)

    assert len(ctx.memoize_wrappers) == 1, (
        "Expected the button with a stateful on_click to be auto-memoized, "
        f"got wrappers: {list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))

    memo_files, _memo_imports = compile_memo_components(
        components=(),
        experimental_memos=tuple(ctx.auto_memo_components.values()),
    )
    memo_code = next(
        code for path, code in memo_files if Path(path).name == f"{wrapper_tag}.jsx"
    )

    assert "refs['_client_state_setCounter'](42)" in memo_code, (
        "Expected the memo body to call the client-state setter via refs.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )

    state_import_match = re.search(
        r'^import\s*\{([^}]*)\}\s*from\s*"\$/utils/state"',
        memo_code,
        flags=re.MULTILINE,
    )
    assert state_import_match is not None, (
        "Memo body must import from $/utils/state since the on_click handler "
        "uses refs['_client_state_setCounter'].\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    imported_names = {name.strip() for name in state_import_match.group(1).split(",")}
    assert "refs" in imported_names, (
        f"Memo body imports {imported_names!r} from $/utils/state but is missing "
        "'refs' — the on_click handler references refs['_client_state_setCounter'].\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )


def test_debounce_input_memo_renders_react_debounce_wrapper() -> None:
    """``rx.input(value=..., on_change=..., debounce_timeout=N)`` memoizes via DebounceInput.

    When ``rx.input`` is given both ``value`` and ``on_change`` it is wrapped by
    ``DebounceInput`` so the underlying input is fully controlled without typing
    jank. The wrapper carries DebounceInput-known props (``debounce_timeout``,
    ``input_ref``, ``element``) and also forwards the inner TextField as the
    ``element`` prop. The memo body produced by the auto-memoize plugin must:

    - Import ``DebounceInput`` from ``react-debounce-input`` and render it via
      ``jsx(DebounceInput, ...)`` rather than rendering the inner TextField
      directly. The whole point of the wrapping is to give react-debounce-input
      ownership of the keystroke pipeline; if the memo emitted the inner
      ``TextField.Root`` instead, controlled-input updates would race the
      backend round-trip and drop characters.
    - Pass ``debounceTimeout`` as a real DebounceInput prop, not via ``css``.
      Reflex routes unknown TextFieldRoot kwargs (like ``debounce_timeout``)
      into ``style`` at component construction; ``DebounceInput.create`` then
      copies ``child.style`` into the wrapper, which can leak the timeout into
      the rendered ``css`` block. The timeout belongs on the wrapper as a real
      prop — leaking it to ``css`` makes it a no-op styling key while the real
      debounce behavior depends on the prop alone.
    - Wire ``element`` to ``RadixThemesTextField.Root`` so the underlying input
      is the radix text field and not a bare ``<input>``.
    """
    from reflex.compiler.compiler import compile_memo_components

    class DebounceState(BaseState):
        value: str = ""

        @rx.event
        def set_value(self, v: str) -> None:
            self.value = v

    def page() -> Component:
        return rx.input(
            id="my_input",
            value=DebounceState.value,
            on_change=DebounceState.set_value,
            debounce_timeout=250,
        )

    ctx, _page_ctx = _compile_single_page(page)

    assert len(ctx.memoize_wrappers) == 1, (
        "Expected the controlled rx.input to memoize as a single DebounceInput "
        f"wrapper, got: {list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    assert "debounceinput" in wrapper_tag.lower(), (
        f"Memo wrapper tag should be derived from DebounceInput, got: {wrapper_tag!r}"
    )

    memo_files, _memo_imports = compile_memo_components(
        components=(),
        experimental_memos=tuple(ctx.auto_memo_components.values()),
    )
    memo_code = next(
        code for path, code in memo_files if Path(path).name == f"{wrapper_tag}.jsx"
    )

    assert re.search(
        r'^import\s+DebounceInput\s+from\s+"react-debounce-input"',
        memo_code,
        flags=re.MULTILINE,
    ), (
        "Memo body must import DebounceInput from react-debounce-input.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    assert "jsx(DebounceInput," in memo_code, (
        "Memo body must render via DebounceInput, not inline the inner TextField.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    assert "debounceTimeout:250" in memo_code, (
        "Memo body must pass debounceTimeout as a DebounceInput prop.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    assert "element:RadixThemesTextField.Root" in memo_code, (
        "Memo body must pass the radix TextField as DebounceInput's element prop.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )

    css_block_match = re.search(
        r"css:\(\{([^}]*)\}\)",
        memo_code,
    )
    css_contents = css_block_match.group(1) if css_block_match else ""
    assert "debounceTimeout" not in css_contents, (
        "debounceTimeout leaked into the css block — it should only be a "
        "DebounceInput prop. Reflex routes unknown TextFieldRoot kwargs into "
        "style, and DebounceInput.create copies child.style verbatim, so the "
        "timeout ends up duplicated as a no-op CSS key.\n"
        f"css block: {css_contents!r}\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )


def test_should_memoize_snapshot_boundary_with_stateful_descendant() -> None:
    """A snapshot boundary memoizes when its subtree contains state-derived hooks.

    ``LeafComponent`` mirrors the Radix-primitive shape: ``recursive=False``
    set directly without inheriting from ``MemoizationLeaf``.
    """
    boundary = LeafComponent.create(Plain.create(STATE_VAR))
    assert _should_memoize(boundary)


def test_snapshot_boundary_wraps_subtree_once_when_descendant_is_stateful() -> None:
    """A snapshot boundary with a stateful descendant produces exactly one wrapper.

    The boundary owns its subtree; descendants must remain suppressed. End
    result: one snapshot wrapper covering the boundary, no independent wrapper
    for the stateful descendant.
    """
    ctx, page_ctx = _compile_single_page(
        lambda: LeafComponent.create(Plain.create(STATE_VAR))
    )
    assert len(ctx.memoize_wrappers) == 1, (
        "Expected exactly one snapshot wrapper covering the leaf and its "
        f"stateful descendant. Got: {list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    assert "leafcomponent" in wrapper_tag.lower(), (
        f"Wrapper should be derived from LeafComponent, got: {wrapper_tag!r}"
    )
    output = page_ctx.output_code or ""
    assert f"jsx({wrapper_tag}," in output


def test_snapshot_boundary_with_static_subtree_is_not_wrapped() -> None:
    """A snapshot boundary with no stateful descendant emits no wrapper.

    Sanity check: the new rule fires on subtree state, not on the boundary
    flag alone. Static leaves stay on the page as before.
    """
    ctx, _page_ctx = _compile_single_page(
        lambda: LeafComponent.create(Plain.create(LiteralVar.create("static")))
    )
    assert len(ctx.memoize_wrappers) == 0, (
        f"Expected no wrapper for a fully static boundary; got: {list(ctx.memoize_wrappers)}"
    )


def test_snapshot_boundary_with_event_trigger_descendant_is_wrapped() -> None:
    """A snapshot boundary with a stateful event-trigger descendant must wrap."""
    from reflex_base.event import EventChain

    event_var = Var(_js_expr="test_event")._replace(
        _var_type=EventChain,
        merge_var_data=VarData(state="TestState", hooks={"useTestState": None}),
    )
    inner = Plain.create(on_click=event_var)
    boundary = LeafComponent.create(inner)
    assert _should_memoize(boundary), (
        "Snapshot boundary with a stateful event-trigger descendant must memoize."
    )


def test_snapshot_boundary_with_no_arg_event_handler_descendant_is_wrapped() -> None:
    """A boundary whose descendant has on_click without arg vars still wraps.

    No-arg handlers (``on_click=State.ping``) contribute to the page only
    via the descendant's ``event_triggers`` and ``_get_events_hooks`` — the
    per-Var subtree scan misses them. The reactive-data check must also
    inspect ``event_triggers`` directly so the boundary wraps and the
    callback's ``useCallback`` lands inside the snapshot body.
    """
    inner = Plain.create()
    inner.event_triggers["on_click"] = Var(_js_expr="evt")
    boundary = LeafComponent.create(inner)
    assert _should_memoize(boundary)


def test_title_with_stateful_var_child_does_not_wrap_bare_independently() -> None:
    """``rx.el.title(state_var)`` must not produce a Bare component child.

    ``<title>`` is RCDATA — text content only. Wrapping the inner Bare as an
    independent memo wrapper renders ``jsx("title", {}, jsx(Bare_xxx, {}))``
    which React refuses to interpolate as text. Marking ``Title`` as a
    snapshot boundary keeps the Bare inside the title's snapshot, where it
    renders as a text interpolation.
    """
    title = Title.create(STATE_VAR)
    ctx, page_ctx = _compile_single_page(lambda: title)

    assert len(ctx.memoize_wrappers) == 1, (
        "Expected exactly one snapshot wrapper for the title; got: "
        f"{list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    assert wrapper_tag.lower().startswith("title_"), (
        f"Wrapper should be derived from Title, got: {wrapper_tag!r}"
    )
    output = page_ctx.output_code
    assert output is not None
    assert f"jsx({wrapper_tag}," in output, (
        "The page output must call the snapshot wrapper.\n"
        f"Page output snippet: {output[:2000]}"
    )
    assert "useTestState" not in output, (
        "The state-bearing hook should live inside the memo body, not the page.\n"
        f"Page output snippet: {output[:2000]}"
    )
    assert "TestState" not in output, (
        "The state-context wiring should live inside the memo body, not the page.\n"
        f"Page output snippet: {output[:2000]}"
    )


def test_meta_with_stateful_var_child_does_not_wrap_bare_independently() -> None:
    """``rx.el.meta(state_var)`` must not produce a Bare component child.

    ``<meta>`` is a void element — it forbids any children at all. Memoizing
    the Bare independently produces ``jsx("meta", {}, jsx(Bare_xxx, {}))``
    which is invalid HTML.
    """
    meta = Meta.create(STATE_VAR)
    ctx, page_ctx = _compile_single_page(lambda: meta)

    assert len(ctx.memoize_wrappers) == 1, (
        "Expected exactly one snapshot wrapper for the meta; got: "
        f"{list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    output = page_ctx.output_code
    assert output is not None
    assert f"jsx({wrapper_tag}," in output, (
        "The page output must call the meta's snapshot wrapper.\n"
        f"Page output snippet: {output[:2000]}"
    )
    assert "useTestState" not in output, (
        "The state-bearing hook should live inside the memo body, not the page.\n"
        f"Page output snippet: {output[:2000]}"
    )
    assert "TestState" not in output, (
        "The state-context wiring should live inside the memo body, not the page.\n"
        f"Page output snippet: {output[:2000]}"
    )


@pytest.mark.parametrize(
    "cls",
    [
        pytest.param(StyleEl, id="style"),
        pytest.param(Textarea, id="textarea"),
        pytest.param(Script, id="script"),
    ],
)
def test_text_only_element_with_stateful_var_child_does_not_wrap_bare(
    cls: type[Component],
) -> None:
    """Text-only HTML elements must not wrap stateful Bare children as components.

    ``<style>``/``<textarea>``/``<script>`` all have raw-text content models.
    A JSX component child renders as a stringified ``[object Object]`` — the
    text interpolation needs to land inside the element's snapshot body.
    """
    component = cls.create(STATE_VAR)
    ctx, page_ctx = _compile_single_page(lambda: component)

    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected exactly one snapshot wrapper; got: {list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    output = page_ctx.output_code
    assert output is not None
    assert f"jsx({wrapper_tag}," in output, (
        "The page output must call the raw-text element's snapshot wrapper.\n"
        f"Page output snippet: {output[:2000]}"
    )
    assert "useTestState" not in output, (
        "The state-bearing hook must live inside the memo body, not the page.\n"
        f"Page output snippet: {output[:2000]}"
    )
    assert "TestState" not in output, (
        "The state-context wiring must live inside the memo body, not the page.\n"
        f"Page output snippet: {output[:2000]}"
    )


def test_accordion_trigger_with_stateful_cond_is_memoized() -> None:
    """AccordionTrigger holding a stateful cond wraps as a single snapshot.

    AccordionTrigger sets ``recursive=False`` without inheriting from
    ``MemoizationLeaf``; the boundary itself must memoize so the cond's
    state read lands inside the snapshot rather than the page module.
    """
    from reflex_components_radix.primitives.accordion import AccordionTrigger

    trigger = AccordionTrigger.create(
        rx.cond(
            SpecialFormMemoState.flag,
            rx.text("Hide"),
            rx.text("Show"),
        )
    )
    ctx, page_ctx = _compile_single_page(lambda: trigger)

    wrapper_tags = list(ctx.memoize_wrappers)
    trigger_wrappers = [t for t in wrapper_tags if "trigger" in t.lower()]
    assert trigger_wrappers, (
        "AccordionTrigger with a stateful cond must produce its own snapshot "
        f"wrapper. Got wrappers: {wrapper_tags}"
    )

    output = page_ctx.output_code
    assert output is not None
    assert "useContext(StateContexts" not in output, (
        "State read leaked into the page module — the trigger's stateful cond "
        "should be captured inside the snapshot wrapper instead.\n"
        f"Page output snippet: {output[:2000]}"
    )


@pytest.mark.parametrize(
    "component_cls",
    [
        # text-only (RCDATA / raw text)
        pytest.param(Title, id="title"),
        pytest.param(StyleEl, id="style"),
        pytest.param(Textarea, id="textarea"),
        pytest.param(Script, id="script"),
        pytest.param(Noscript, id="noscript"),
        pytest.param(ScriptTag, id="script_tag"),
        # void HTML elements
        pytest.param(Meta, id="meta"),
        pytest.param(Base, id="base"),
        pytest.param(Link, id="link"),
        pytest.param(RawLink, id="raw_link"),
        pytest.param(BaseInput, id="input"),
        pytest.param(Br, id="br"),
        pytest.param(Wbr, id="wbr"),
        pytest.param(Col, id="col"),
        pytest.param(Hr, id="hr"),
        pytest.param(Area, id="area"),
        pytest.param(Img, id="img"),
        pytest.param(Track, id="track"),
        pytest.param(Embed, id="embed"),
        pytest.param(Source, id="source"),
        # SVG raw-text equivalents
        pytest.param(Desc, id="svg_desc"),
        pytest.param(SvgTitle, id="svg_title"),
        pytest.param(SvgScript, id="svg_script"),
        pytest.param(SvgStyle, id="svg_style"),
    ],
)
def test_restricted_content_element_isolates_stateful_bare_via_snapshot(
    component_cls: type[Component],
) -> None:
    """Restricted-content elements snapshot-wrap and never expose a Bare child.

    Asserts both the classification (the element opts into SNAPSHOT) and the
    invariant (a stateful Bare child stays inside the snapshot rather than
    being independently wrapped as a JSX component child of an element whose
    content model rejects components).
    """
    from reflex_base.components.memoize_helpers import is_snapshot_boundary

    instance = component_cls.create()
    assert is_snapshot_boundary(instance), (
        f"{component_cls.__qualname__} should be classified as a snapshot boundary."
    )
    assert get_memoization_strategy(instance) is MemoizationStrategy.SNAPSHOT, (
        f"{component_cls.__qualname__} should use SNAPSHOT strategy"
    )

    ctx, page_ctx = _compile_single_page(lambda: component_cls.create(STATE_VAR))
    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected exactly one snapshot wrapper for {component_cls.__qualname__}, "
        f"got: {list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    output = page_ctx.output_code
    assert output is not None
    assert f"jsx({wrapper_tag}," in output, (
        f"Page output for {component_cls.__qualname__} must call the snapshot "
        f"wrapper.\nPage output snippet: {output[:2000]}"
    )
    assert "useTestState" not in output, (
        f"Stateful Bare child of <{getattr(component_cls, 'tag', '?')}> "
        f"({component_cls.__qualname__}) leaked the state hook into the page; "
        "the element's snapshot must capture it.\n"
        f"Page output snippet: {output[:2000]}"
    )
    assert "TestState" not in output, (
        f"State-context wiring for <{getattr(component_cls, 'tag', '?')}> "
        f"({component_cls.__qualname__}) leaked into the page module.\n"
        f"Page output snippet: {output[:2000]}"
    )


def _compile_memo_module_text(ctx: CompileContext) -> str:
    """Compile the auto-memo definitions and return the concatenated JSX text.

    Args:
        ctx: The compile context produced by ``_compile_single_page``.

    Returns:
        The full memo module source code joined by newlines.
    """
    from reflex.compiler.compiler import compile_memo_components

    memo_files, _imports = compile_memo_components(
        components=(),
        experimental_memos=tuple(ctx.auto_memo_components.values()),
    )
    return "\n".join(code for _, code in memo_files)


def test_title_memo_body_renders_text_interpolation_not_bare_component() -> None:
    """The title's memo body must interpolate the state Var as text.

    The body must contain a literal ``jsx("title", …)`` call carrying the
    state-context wiring, and the page module must subscribe via the wrapper
    rather than directly. The state hook/context lives in the memo body only.
    """
    ctx, page_ctx = _compile_single_page(lambda: Title.create(STATE_VAR))
    memo_code = _compile_memo_module_text(ctx)

    assert 'jsx("title"' in memo_code, (
        f'Title snapshot body should contain a literal ``jsx("title", …)`` '
        f"call. Memo code:\n{memo_code[:2000]}"
    )
    assert "useTestState" in memo_code, (
        "Title memo body should carry the stateful hook so the Bare child is "
        f"interpolated inline, not lifted out.\nMemo code:\n{memo_code[:2000]}"
    )

    page_output = page_ctx.output_code
    assert page_output is not None
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    assert f"jsx({wrapper_tag}," in page_output
    assert "useTestState" not in page_output


def test_meta_memo_body_renders_void_element_inline() -> None:
    """Meta's snapshot body should call ``jsx("meta", …)`` and own the state."""
    ctx, _page_ctx = _compile_single_page(lambda: Meta.create(STATE_VAR))
    memo_code = _compile_memo_module_text(ctx)

    assert 'jsx("meta"' in memo_code
    assert "useTestState" in memo_code, (
        "Meta memo body should carry the stateful hook so the Bare child is "
        f"interpolated inline, not lifted out.\nMemo code:\n{memo_code[:2000]}"
    )


def test_snapshot_boundary_memo_body_subscribes_state_in_body_not_page() -> None:
    """State subscription wiring lives in the memo body, not in the page module.

    The whole point of memoization is to isolate state reads from the page.
    This asserts that ``useContext(StateContexts…)`` (state subscription)
    appears in the memo module and NOT in the page output, confirming the
    state read landed inside the snapshot wrapper.
    """
    from reflex_components_radix.primitives.accordion import AccordionTrigger

    trigger = AccordionTrigger.create(
        rx.cond(
            SpecialFormMemoState.flag,
            rx.text("Hide"),
            rx.text("Show"),
        )
    )
    ctx, page_ctx = _compile_single_page(lambda: trigger)
    memo_code = _compile_memo_module_text(ctx)

    assert "useContext(StateContexts" in memo_code, (
        "Snapshot wrapper should subscribe to state inside the memo body."
    )
    page_output = page_ctx.output_code
    assert page_output is not None
    assert "useContext(StateContexts" not in page_output, (
        "State subscription should NOT appear in the page module — it must be "
        "isolated inside the snapshot wrapper.\n"
        f"Page output:\n{page_output[:2000]}"
    )


def test_nested_snapshot_boundaries_produce_one_outer_wrapper() -> None:
    """A snapshot boundary inside another snapshot boundary produces ONE wrapper.

    The outer boundary's suppressor stack must absorb the inner boundary into
    its own snapshot. Two nested wrappers would both duplicate the inner
    component AND defeat the boundary's "I own my subtree" contract.
    """
    inner = LeafComponent.create(Plain.create(STATE_VAR))
    outer = LeafComponent.create(inner)
    ctx, _page_ctx = _compile_single_page(lambda: outer)

    assert len(ctx.memoize_wrappers) == 1, (
        f"Nested snapshot boundaries must collapse to one outer wrapper; got "
        f"{list(ctx.memoize_wrappers)}"
    )

    memo_code = _compile_memo_module_text(ctx)
    assert "jsx(LeafComponent" in memo_code, (
        "The outer wrapper's body must render the inner LeafComponent so the "
        "suppressed inner boundary still appears under the outer snapshot.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    assert "jsx(Plain" in memo_code, (
        "The outer wrapper's body must render the innermost Plain component "
        "and its Bare child so the stateful subtree lands inside the snapshot.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )


def test_memoization_leaf_subclass_and_raw_recursive_false_behave_identically() -> None:
    """Both ways to opt into recursive=False produce one snapshot wrapper.

    ``MemoizationLeaf`` subclasses and components that simply set
    ``_memoization_mode = MemoizationMode(recursive=False)`` are handled
    equivalently by the compiler.
    """
    from reflex_base.components.component import MemoizationLeaf

    class LeafSubclass(MemoizationLeaf):
        tag = "LeafSubclass"
        library = "leaf-subclass-lib"

    leaf_subclass = LeafSubclass.create(Plain.create(STATE_VAR))
    raw_leaf = LeafComponent.create(Plain.create(STATE_VAR))

    ctx_a, _ = _compile_single_page(lambda: leaf_subclass)
    ctx_b, _ = _compile_single_page(lambda: raw_leaf)

    assert len(ctx_a.memoize_wrappers) == 1
    assert len(ctx_b.memoize_wrappers) == 1


def test_snapshot_boundary_with_multiple_stateful_descendants_emits_one_wrapper() -> (
    None
):
    """One boundary + many stateful descendants = one wrapper (not one per descendant).

    Without this invariant, a Radix primitive wrapping several stateful
    children would balloon the page with one wrapper per child even though
    the boundary already owns the subtree.
    """
    boundary = LeafComponent.create(
        Plain.create(STATE_VAR),
        Plain.create(STATE_VAR),
        WithProp.create(label=STATE_VAR),
    )
    ctx, _page_ctx = _compile_single_page(lambda: boundary)
    assert len(ctx.memoize_wrappers) == 1, (
        f"Multiple stateful descendants must share the boundary's wrapper; got "
        f"{list(ctx.memoize_wrappers)}"
    )

    memo_code = _compile_memo_module_text(ctx)
    assert memo_code.count("jsx(Plain") == 2, (
        "The boundary's snapshot body must render both Plain children inline.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    assert "jsx(WithProp" in memo_code, (
        "The boundary's snapshot body must render the WithProp child inline.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )


def test_repeated_snapshot_boundary_subtrees_dedupe_to_one_definition() -> None:
    """Two identical boundary subtrees collapse to one memo definition.

    Memo definitions are keyed on the rendered subtree shape, so two
    identical boundaries should share a wrapper tag (even though they appear
    twice on the page).
    """
    ctx, page_ctx = _compile_single_page(
        lambda: Fragment.create(
            LeafComponent.create(Plain.create(STATE_VAR)),
            LeafComponent.create(Plain.create(STATE_VAR)),
        )
    )
    assert len(ctx.memoize_wrappers) == 1, (
        f"Identical boundary subtrees should share one wrapper; got "
        f"{list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    assert (page_ctx.output_code or "").count(f"jsx({wrapper_tag},") == 2


def test_snapshot_boundary_with_stateful_prop_and_descendant_emits_one_wrapper() -> (
    None
):
    """A boundary with both stateful props and stateful descendants memoizes once."""
    from reflex_components_core.el.elements.metadata import Title

    title = Title.create(
        STATE_VAR,  # stateful child Bare
        class_name=STATE_VAR.to(str),  # stateful prop
    )
    ctx, _page_ctx = _compile_single_page(lambda: title)
    assert len(ctx.memoize_wrappers) == 1


def test_disposition_never_overrides_snapshot_boundary_subtree_check() -> None:
    """``MemoizationDisposition.NEVER`` wins even with a stateful subtree.

    Snapshot boundaries that explicitly opt out via NEVER must stay
    unwrapped — useful for components that do their own memoization
    elsewhere or shouldn't be memoized for correctness reasons.
    """
    boundary = LeafComponent.create(Plain.create(STATE_VAR))
    object.__setattr__(
        boundary,
        "_memoization_mode",
        dataclasses.replace(
            boundary._memoization_mode,
            disposition=MemoizationDisposition.NEVER,
        ),
    )
    assert not _should_memoize(boundary)


def test_static_subtree_inside_passthrough_no_memo_at_all() -> None:
    """Sanity: a fully static page produces no memo wrappers.

    Guards against a regression where the new branch incorrectly fires for
    components without state hooks.
    """
    ctx, _page_ctx = _compile_single_page(
        lambda: rx.box(rx.text("static"), rx.text("also static"))
    )
    assert len(ctx.memoize_wrappers) == 0, (
        f"No state, no wrappers expected. Got: {list(ctx.memoize_wrappers)}"
    )


def test_void_element_with_only_stateful_prop_memoizes_via_snapshot() -> None:
    """A void element with only a stateful prop still snapshot-wraps cleanly.

    Verifies that even without children, stateful props on void elements go
    through the boundary's snapshot wrapper rather than degrading to a
    passthrough that re-reads state on the page.
    """
    from reflex_components_core.el.elements.media import Img

    img = Img.create(src=STATE_VAR.to(str))
    ctx, page_ctx = _compile_single_page(lambda: img)
    assert len(ctx.memoize_wrappers) == 1
    output = page_ctx.output_code
    assert output is not None
    assert "useContext(StateContexts" not in output


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(lambda: Title.create("hello", id="t"), id="title_with_id"),
        pytest.param(lambda: Img.create(src="/x.png", id="logo"), id="img_with_id"),
        pytest.param(lambda: Br.create(id="br"), id="br_with_id"),
        pytest.param(lambda: BaseInput.create(id="i"), id="input_with_id"),
        pytest.param(
            lambda: Meta.create(name="description", id="m"), id="meta_with_id"
        ),
    ],
)
def test_static_restricted_element_with_id_only_does_not_memoize(
    factory: Callable[[], Component],
) -> None:
    """Restricted-content elements with only an ``id`` ref stay unwrapped.

    The subtree scan subtracts the static-id ``useRef`` line from the
    component's internal hooks so id-only elements do not flag as reactive.
    Both ``MemoizationLeaf``-based elements and components that explicitly
    set ``_memoization_mode = recursive=False`` go through this same path.
    """
    component = factory()
    ctx, _page_ctx = _compile_single_page(lambda: component)
    assert len(ctx.memoize_wrappers) == 0, (
        f"Static restricted element with only an id ref should not memoize. "
        f"Got wrappers: {list(ctx.memoize_wrappers)}"
    )


def test_static_restricted_element_no_id_no_children_does_not_memoize() -> None:
    """Sanity: a fully static restricted element with no props/children stays unwrapped."""
    from reflex_components_core.el.elements.metadata import Title

    ctx, _page_ctx = _compile_single_page(lambda: Title.create("static-string"))
    assert len(ctx.memoize_wrappers) == 0, (
        f"Static title should not memoize. Got: {list(ctx.memoize_wrappers)}"
    )


@pytest.mark.parametrize("global_ref", [True, False])
def test_client_state_value_inside_snapshot_boundary_is_memoized(
    global_ref: bool,
) -> None:
    """Client-state Vars are reactive and must trigger boundary memoization.

    A ``client_state`` Var contributes its ``useState``/``useId`` hooks via
    ``var_data.hooks`` without setting ``var_data.state``. The reactive-Var
    walk must catch the hooks-only case so client-state-driven content
    inside a snapshot boundary lands in the memo body. Both global and
    page-local ``ClientStateVar`` Vars must drive the same wrapping.
    """
    from reflex.experimental.client_state import ClientStateVar

    cs_var = ClientStateVar.create("titletest", default="hi", global_ref=global_ref)
    title = Title.create(cs_var.value)
    ctx, page_ctx = _compile_single_page(lambda: title)
    assert len(ctx.memoize_wrappers) == 1, (
        "Client-state-driven title content must memoize. Got: "
        f"{list(ctx.memoize_wrappers)}"
    )
    page_output = page_ctx.output_code
    assert page_output is not None
    assert "useState" not in page_output, (
        "Client-state hooks should be inside the memo body, not the page.\n"
        f"Page output snippet: {page_output[:2000]}"
    )


def test_hooks_only_var_data_descendant_inside_snapshot_boundary_is_memoized() -> None:
    """Hook-bearing VarData without ``state`` still triggers snapshot memoization.

    Some frontend-only Vars contribute React hooks but do not carry a backend
    state name. The snapshot-boundary subtree scan must catch those hooks-only
    Vars so their hook lines land in the memo body instead of being suppressed
    with the descendant.
    """
    hook_var = Var(_js_expr="hookOnlyProbe")._replace(
        merge_var_data=VarData(hooks={"const hookOnlyProbe = useHookOnly();": None})
    )
    child = Plain.create()
    child.special_props = [hook_var]
    boundary = LeafComponent.create(child)

    ctx, page_ctx = _compile_single_page(lambda: boundary)
    memo_code = _compile_memo_module_text(ctx)

    assert len(ctx.memoize_wrappers) == 1, (
        f"Hooks-only descendant should produce one boundary wrapper, got: "
        f"{list(ctx.memoize_wrappers)}"
    )
    assert "useHookOnly" in memo_code, (
        "Hooks-only VarData should be emitted in the memo body.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    page_output = page_ctx.output_code
    assert page_output is not None
    assert "useHookOnly" not in page_output, (
        "Hooks-only VarData leaked into the page module.\n"
        f"Page output snippet: {page_output[:2000]}"
    )


def test_added_hook_descendant_inside_snapshot_boundary_is_memoized() -> None:
    """Hooks from ``add_hooks`` descendants trigger snapshot memoization.

    ``add_hooks`` output does not necessarily appear in any Var or event
    trigger. Snapshot boundaries must still wrap so the walker skips the
    descendant and the hook lands in the memo body, matching the signal used
    by ``MemoizationLeaf.create``.
    """

    class HookOnlyChild(Component):
        tag = "HookOnlyChild"
        library = "hook-only-child-lib"

        def add_hooks(self) -> list[str]:
            """Add a hook line for the regression test.

            Returns:
                The hook lines this component contributes.
            """
            return ["const hookOnlyChild = useHookOnlyChild();"]

    boundary = LeafComponent.create(HookOnlyChild.create())
    assert _should_memoize(boundary)

    ctx, page_ctx = _compile_single_page(lambda: boundary)
    memo_code = _compile_memo_module_text(ctx)

    assert len(ctx.memoize_wrappers) == 1, (
        f"Added-hook descendant should produce one boundary wrapper, got: "
        f"{list(ctx.memoize_wrappers)}"
    )
    assert "useHookOnlyChild" in memo_code, (
        "add_hooks output should be emitted in the memo body.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )
    page_output = page_ctx.output_code
    assert page_output is not None
    assert "useHookOnlyChild" not in page_output, (
        "add_hooks output leaked into the page module.\n"
        f"Page output snippet: {page_output[:2000]}"
    )


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(lambda: Meta.create(content=STATE_VAR), id="meta_content"),
        pytest.param(lambda: Base.create(href=STATE_VAR), id="base_href"),
        pytest.param(lambda: Link.create(href=STATE_VAR), id="link_href"),
        pytest.param(lambda: Script.create(src=STATE_VAR), id="script_src"),
        pytest.param(lambda: BaseInput.create(value=STATE_VAR), id="input_value"),
        pytest.param(lambda: Textarea.create(value=STATE_VAR), id="textarea_value"),
        pytest.param(lambda: SvgStyle.create(media=STATE_VAR), id="svg_style_media"),
    ],
)
def test_restricted_content_element_with_stateful_attribute_uses_snapshot(
    factory: Callable[[], Component],
) -> None:
    """Stateful attrs on restricted-content elements are isolated in snapshots."""
    ctx, page_ctx = _compile_single_page(factory)
    memo_code = _compile_memo_module_text(ctx)

    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected one snapshot wrapper for a stateful restricted attr, got: "
        f"{list(ctx.memoize_wrappers)}"
    )
    page_output = page_ctx.output_code
    assert page_output is not None
    assert "useTestState" not in page_output, (
        "Reactive hook marker for restricted attr should not leak to page output.\n"
        f"Page output snippet: {page_output[:2000]}"
    )
    assert "useTestState" in memo_code, (
        "Reactive hook marker for restricted attr should live in the memo body.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )


def _real_recursive_false_factories() -> list:
    from reflex_components_radix.primitives.dialog import DialogTrigger
    from reflex_components_radix.primitives.drawer import DrawerTrigger
    from reflex_components_radix.themes.components.popover import PopoverTrigger
    from reflex_components_radix.themes.components.tabs import TabsTrigger
    from reflex_components_radix.themes.components.tooltip import Tooltip

    return [
        pytest.param(
            lambda: DialogTrigger.create(rx.text(STATE_VAR)),
            id="primitive_dialog_trigger",
        ),
        pytest.param(
            lambda: DrawerTrigger.create(rx.text(STATE_VAR)),
            id="primitive_drawer_trigger",
        ),
        pytest.param(
            lambda: PopoverTrigger.create(rx.text(STATE_VAR)),
            id="themes_popover_trigger",
        ),
        pytest.param(
            lambda: TabsTrigger.create(rx.text(STATE_VAR), value="tab-1"),
            id="themes_tabs_trigger",
        ),
        pytest.param(
            lambda: Tooltip.create(rx.text(STATE_VAR), content="tip"),
            id="themes_tooltip",
        ),
    ]


@pytest.mark.parametrize("factory", _real_recursive_false_factories())
def test_real_recursive_false_components_with_stateful_descendants_snapshot_wrap(
    factory: Callable[[], Component],
) -> None:
    """Several real ``recursive=False`` components share the boundary behavior."""
    component = factory()
    ctx, page_ctx = _compile_single_page(lambda: component)

    assert len(ctx.memoize_wrappers) == 1, (
        f"Expected one wrapper for {type(component).__qualname__}, got: "
        f"{list(ctx.memoize_wrappers)}"
    )
    wrapper_tag = next(iter(ctx.memoize_wrappers))
    assert type(component).__name__.lower() in wrapper_tag.lower(), (
        f"Wrapper {wrapper_tag!r} should be derived from {type(component).__name__}."
    )
    page_output = page_ctx.output_code
    assert page_output is not None
    assert "useContext(StateContexts" not in page_output, (
        "Stateful descendant under a real snapshot boundary leaked to page output.\n"
        f"Page output snippet: {page_output[:2000]}"
    )


def test_restricted_content_element_with_id_and_stateful_child_still_memoizes() -> None:
    """Static ref filtering must not suppress real stateful content."""
    from reflex_components_core.el.elements.metadata import Title

    title = Title.create(STATE_VAR, id="stateful-title")
    ctx, page_ctx = _compile_single_page(lambda: title)
    memo_code = _compile_memo_module_text(ctx)

    assert len(ctx.memoize_wrappers) == 1, (
        f"Stateful title with id should still memoize, got: {list(ctx.memoize_wrappers)}"
    )
    page_output = page_ctx.output_code
    assert page_output is not None
    assert "ref_stateful_title" not in page_output, (
        "The title ref should move with the snapshot body, not stay on the page.\n"
        f"Page output snippet: {page_output[:2000]}"
    )
    assert "ref_stateful_title" in memo_code, (
        "The title ref should be emitted inside the snapshot memo body.\n"
        f"Memo code snippet: {memo_code[:2000]}"
    )


def test_each_memo_wrapper_emits_one_component_module_file() -> None:
    """Every wrapper tag corresponds to exactly one ``components/{tag}.jsx`` file.

    Locks the per-wrapper file invariant: ``compile_memo_components`` must
    emit one module per wrapper (plus the shared index), so that React can
    code-split per wrapper. A wrapper without a file (or a file without a
    wrapper) would mean broken imports at runtime.
    """
    from reflex.compiler.compiler import compile_memo_components

    ctx, _page_ctx = _compile_single_page(
        lambda: Fragment.create(
            Plain.create(STATE_VAR),
            WithProp.create(label=STATE_VAR),
            LeafComponent.create(Plain.create(STATE_VAR)),
        )
    )
    memo_files, _imports = compile_memo_components(
        components=(),
        experimental_memos=tuple(ctx.auto_memo_components.values()),
    )
    component_module_names = {
        Path(path).name
        for path, _ in memo_files
        if Path(path).parent.name == "components"
    }
    expected = {f"{tag}.jsx" for tag in ctx.memoize_wrappers}
    assert component_module_names == expected, (
        f"Per-wrapper file invariant broken. wrappers={sorted(ctx.memoize_wrappers)} "
        f"files={sorted(component_module_names)}"
    )
    assert len(ctx.memoize_wrappers) == 3, (
        "Test should exercise the multi-wrapper case: one passthrough wrapper "
        "for Plain, one for WithProp, and one snapshot wrapper for the "
        f"LeafComponent boundary. Got: {sorted(ctx.memoize_wrappers)}"
    )
