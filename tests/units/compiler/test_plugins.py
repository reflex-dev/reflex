# ruff: noqa: D101, D102

import dataclasses
from collections.abc import Callable
from typing import Any

import pytest
from reflex_base import constants
from reflex_base.components.component import (
    BaseComponent,
    Component,
    ComponentStyle,
    StatefulComponent,
    field,
)
from reflex_base.environment import environment
from reflex_base.plugins import (
    BaseContext,
    CompileContext,
    CompilerHooks,
    CompilerPlugin,
    ComponentAndChildren,
    PageContext,
    PageDefinition,
    Plugin,
)
from reflex_base.utils import format as format_utils
from reflex_base.utils.imports import ImportVar, collapse_imports, merge_imports
from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.base.fragment import Fragment

from reflex.app import UnevaluatedPage
from reflex.compiler import compiler
from reflex.compiler.plugins import (
    ApplyStylePlugin,
    DefaultCollectorPlugin,
    DefaultPagePlugin,
    default_page_plugins,
)


@dataclasses.dataclass(slots=True)
class FakePage:
    route: str
    component: Callable[[], Component]
    title: Var | str | None = None
    description: Var | str | None = None
    image: str = ""
    meta: tuple[dict[str, Any], ...] = ()


class WrapperComponent(Component):
    tag = "WrapperComponent"
    library = "wrapper-lib"

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        return {(20, "NestedWrap"): Fragment.create()}


class RootComponent(Component):
    tag = "RootComponent"
    library = "root-lib"

    slot: Component | None = field(default=None)

    def add_style(self) -> dict[str, Any] | None:
        return {"display": "flex"}

    def add_custom_code(self) -> list[str]:
        return ["const rootAddedCode = 1;"]

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        return {(10, "Wrap"): WrapperComponent.create()}


class ChildComponent(Component):
    tag = "ChildComponent"
    library = "child-lib"

    def add_style(self) -> dict[str, Any] | None:
        return {"align_items": "center"}

    def add_custom_code(self) -> list[str]:
        return ["const childAddedCode = 1;"]

    def _get_custom_code(self) -> str | None:
        return "const childCustomCode = 1;"

    def _get_hooks(self) -> str | None:
        return "const childHook = useChildHook();"


class PropComponent(Component):
    tag = "PropComponent"
    library = "prop-lib"

    def add_custom_code(self) -> list[str]:
        return ["const propAddedCode = 1;"]

    def _get_custom_code(self) -> str | None:
        return "const propCustomCode = 1;"

    def _get_dynamic_imports(self) -> str | None:
        return "dynamic(() => import('prop-lib'))"

    def _get_hooks(self) -> str | None:
        return "const propHook = usePropHook();"

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        return {(15, "PropWrap"): Fragment.create()}


class NoRecursiveImportsComponent(Component):
    tag = "NoRecursiveImportsComponent"
    library = "no-recursive-imports-lib"


class SharedLibraryComponent(Component):
    tag = "SharedLibraryComponent"
    library = "react-moment"

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        return {(25, "SharedLibraryWrap"): Fragment.create()}


class StubCompilerPlugin(Plugin):
    pass


SHARED_STATEFUL_VAR = LiteralVar.create("shared")._replace(
    merge_var_data=VarData(
        hooks={"useSharedStatefulValue": None},
        state="SharedState",
    )
)


def create_component_tree() -> RootComponent:
    return RootComponent.create(
        ChildComponent.create(id="child-id", style={"color": "red"}),
        slot=PropComponent.create(id="prop-id", style={"opacity": "0.5"}),
        style={"margin": "0"},
    )


def create_shared_stateful_component() -> SharedLibraryComponent:
    return SharedLibraryComponent.create(SHARED_STATEFUL_VAR)


def create_no_recursive_imports_component() -> NoRecursiveImportsComponent:
    return NoRecursiveImportsComponent.create()


def page_style() -> ComponentStyle:
    return {
        RootComponent: {"padding": "1rem"},
        ChildComponent: {"font_size": "12px"},
        PropComponent: {"border": "1px solid green"},
    }


def normalize_style(component: BaseComponent) -> dict[str, str]:
    assert isinstance(component, Component)
    return {key: str(value) for key, value in component.style.items()}


def create_compile_context(hooks: CompilerHooks | None = None) -> CompileContext:
    return CompileContext(pages=[], hooks=hooks or CompilerHooks())


def collect_page_context(
    component: BaseComponent,
    *,
    plugins: tuple[Any, ...],
) -> PageContext:
    page_ctx = PageContext(
        name="page",
        route="/page",
        root_component=component,
    )
    hooks = CompilerHooks(plugins=plugins)
    compile_ctx = create_compile_context(hooks)

    with compile_ctx, page_ctx:
        page_ctx.root_component = hooks.compile_component(
            page_ctx.root_component,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )
        hooks.compile_page(page_ctx, compile_context=compile_ctx)

    return page_ctx


def test_eval_page_uses_first_non_none_result() -> None:
    calls: list[str] = []
    page = FakePage(route="/demo", component=lambda: Fragment.create())

    class NoMatchPlugin(StubCompilerPlugin):
        def eval_page(
            self,
            page_fn: Any,
            /,
            *,
            page: PageDefinition,
            **kwargs: Any,
        ) -> None:
            del page_fn, page, kwargs
            calls.append("no-match")

    class MatchPlugin(StubCompilerPlugin):
        def eval_page(
            self,
            page_fn: Any,
            /,
            *,
            page: PageDefinition,
            **kwargs: Any,
        ) -> PageContext:
            del kwargs
            calls.append("match")
            return PageContext(
                name="page",
                route=page.route,
                root_component=page_fn(),
            )

    class UnreachablePlugin(StubCompilerPlugin):
        def eval_page(
            self,
            page_fn: Any,
            /,
            *,
            page: PageDefinition,
            **kwargs: Any,
        ) -> PageContext:
            del page_fn, page, kwargs
            calls.append("unreachable")
            msg = "eval_page should stop at the first page context"
            raise AssertionError(msg)

    hooks = CompilerHooks(plugins=(NoMatchPlugin(), MatchPlugin(), UnreachablePlugin()))

    page_ctx = hooks.eval_page(page.component, page=page, compile_context=None)

    assert page_ctx is not None
    assert page_ctx.route == "/demo"
    assert calls == ["no-match", "match"]


def test_compile_page_runs_plugins_in_registration_order() -> None:
    calls: list[str] = []
    page_ctx = PageContext(
        name="page",
        route="/ordered",
        root_component=Fragment.create(),
    )

    class FirstPlugin(StubCompilerPlugin):
        def compile_page(
            self,
            page_ctx: PageContext,
            /,
            **kwargs: Any,
        ) -> None:
            del page_ctx, kwargs
            calls.append("first")

    class SecondPlugin(StubCompilerPlugin):
        def compile_page(
            self,
            page_ctx: PageContext,
            /,
            **kwargs: Any,
        ) -> None:
            del page_ctx, kwargs
            calls.append("second")

    hooks = CompilerHooks(plugins=(FirstPlugin(), SecondPlugin()))
    hooks.compile_page(page_ctx, compile_context=None)

    assert calls == ["first", "second"]


def test_component_hook_resolution_caches_only_real_overrides() -> None:
    class EnterPlugin(StubCompilerPlugin):
        def enter_component(
            self,
            comp: BaseComponent,
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> None:
            del comp, page_context, compile_context, in_prop_tree, stateful_component

    class LeavePlugin(StubCompilerPlugin):
        def leave_component(
            self,
            comp: BaseComponent,
            children: tuple[BaseComponent, ...],
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> None:
            del (
                comp,
                children,
                page_context,
                compile_context,
                in_prop_tree,
                stateful_component,
            )

    hooks = CompilerHooks(plugins=(Plugin(), EnterPlugin(), LeavePlugin()))

    assert len(hooks._enter_component_hook_binders) == 1
    assert len(hooks._leave_component_hook_binders) == 1


def test_enter_component_skips_inherited_base_plugin_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[str] = []
    root = RootComponent.create()

    def fail_enter_component(
        self,
        comp: BaseComponent,
        /,
        *,
        page_context: PageContext,
        compile_context: CompileContext,
        in_prop_tree: bool = False,
        stateful_component: StatefulComponent | None = None,
    ) -> None:
        del self, comp, page_context, compile_context, in_prop_tree, stateful_component
        msg = "Inherited Plugin.enter_component hook should be skipped."
        raise AssertionError(msg)

    monkeypatch.setattr(Plugin, "enter_component", fail_enter_component)

    class RealPlugin(StubCompilerPlugin):
        def enter_component(
            self,
            comp: BaseComponent,
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> None:
            del page_context, compile_context, in_prop_tree, stateful_component
            visited.append(type(comp).__name__)

    hooks = CompilerHooks(plugins=(Plugin(), RealPlugin()))
    page_ctx = PageContext(name="page", route="/page", root_component=root)
    compile_ctx = create_compile_context(hooks)

    with compile_ctx, page_ctx:
        hooks.compile_component(
            root,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )

    assert visited == ["RootComponent"]


def test_enter_component_skips_inherited_protocol_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[str] = []
    root = RootComponent.create()

    def fail_enter_component(
        self,
        comp: BaseComponent,
        /,
        *,
        page_context: PageContext,
        compile_context: CompileContext,
        in_prop_tree: bool = False,
        stateful_component: StatefulComponent | None = None,
    ) -> None:
        del self, comp, page_context, compile_context, in_prop_tree, stateful_component
        msg = "Inherited CompilerPlugin.enter_component hook should be skipped."
        raise AssertionError(msg)

    monkeypatch.setattr(CompilerPlugin, "enter_component", fail_enter_component)

    class ProtocolOnlyPlugin(CompilerPlugin):
        pass

    class RealPlugin(StubCompilerPlugin):
        def enter_component(
            self,
            comp: BaseComponent,
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> None:
            del page_context, compile_context, in_prop_tree, stateful_component
            visited.append(type(comp).__name__)

    hooks = CompilerHooks(plugins=(ProtocolOnlyPlugin(), RealPlugin()))
    page_ctx = PageContext(name="page", route="/page", root_component=root)
    compile_ctx = create_compile_context(hooks)

    with compile_ctx, page_ctx:
        hooks.compile_component(
            root,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )

    assert visited == ["RootComponent"]


def test_compile_component_orders_enter_and_leave_by_plugin() -> None:
    events: list[str] = []
    root = RootComponent.create()

    class FirstPlugin(StubCompilerPlugin):
        def enter_component(
            self,
            comp: BaseComponent,
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> None:
            del comp, page_context, compile_context, in_prop_tree, stateful_component
            events.append("first:enter")

        def leave_component(
            self,
            comp: BaseComponent,
            children: tuple[BaseComponent, ...],
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> None:
            del (
                comp,
                children,
                page_context,
                compile_context,
                in_prop_tree,
                stateful_component,
            )
            events.append("first:leave")

    class SecondPlugin(StubCompilerPlugin):
        def enter_component(
            self,
            comp: BaseComponent,
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> None:
            del comp, page_context, compile_context, in_prop_tree, stateful_component
            events.append("second:enter")

        def leave_component(
            self,
            comp: BaseComponent,
            children: tuple[BaseComponent, ...],
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> None:
            del (
                comp,
                children,
                page_context,
                compile_context,
                in_prop_tree,
                stateful_component,
            )
            events.append("second:leave")

    hooks = CompilerHooks(plugins=(FirstPlugin(), SecondPlugin()))
    page_ctx = PageContext(name="page", route="/page", root_component=root)
    compile_ctx = create_compile_context(hooks)

    with compile_ctx, page_ctx:
        compiled_root = hooks.compile_component(
            root,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )

    assert compiled_root is root
    assert events == [
        "first:enter",
        "second:enter",
        "second:leave",
        "first:leave",
    ]


def test_compile_component_traverses_children_before_prop_components() -> None:
    visited: list[str] = []
    root = RootComponent.create(
        ChildComponent.create(),
        slot=PropComponent.create(),
    )

    class VisitPlugin(StubCompilerPlugin):
        def enter_component(
            self,
            comp: BaseComponent,
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> None:
            del page_context, compile_context, in_prop_tree, stateful_component
            if isinstance(comp, Component):
                visited.append(comp.tag or type(comp).__name__)

    hooks = CompilerHooks(plugins=(VisitPlugin(),))
    page_ctx = PageContext(name="page", route="/page", root_component=root)
    compile_ctx = create_compile_context(hooks)

    with compile_ctx, page_ctx:
        hooks.compile_component(
            root,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )

    assert visited == ["RootComponent", "ChildComponent", "PropComponent"]


def test_enter_and_leave_replacements_match_generator_style_behavior() -> None:
    child = ChildComponent.create(id="original")
    root = RootComponent.create(child)

    class ReplacePlugin(StubCompilerPlugin):
        def enter_component(
            self,
            comp: BaseComponent,
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> BaseComponent | ComponentAndChildren | None:
            del page_context, compile_context, stateful_component
            if isinstance(comp, RootComponent) and not in_prop_tree:
                replacement_child = ChildComponent.create(id="replacement")
                return comp, (replacement_child,)
            return None

        def leave_component(
            self,
            comp: BaseComponent,
            children: tuple[BaseComponent, ...],
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
            stateful_component: StatefulComponent | None = None,
        ) -> BaseComponent | ComponentAndChildren | None:
            del page_context, compile_context, in_prop_tree, stateful_component
            if isinstance(comp, RootComponent):
                return Fragment.create(comp), children
            return None

    hooks = CompilerHooks(plugins=(ReplacePlugin(),))
    page_ctx = PageContext(name="page", route="/page", root_component=root)
    compile_ctx = create_compile_context(hooks)

    with compile_ctx, page_ctx:
        compiled_root = hooks.compile_component(
            root,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )

    assert isinstance(compiled_root, Fragment)
    assert len(compiled_root.children) == 1
    replacement_child = compiled_root.children[0]
    assert isinstance(replacement_child, ChildComponent)
    assert str(replacement_child.id) == "replacement"


def test_context_lifecycle_and_cleanup() -> None:
    compile_ctx = CompileContext(pages=[], hooks=CompilerHooks())
    page_ctx = PageContext(
        name="page",
        route="/ctx",
        root_component=Fragment.create(),
    )

    with pytest.raises(RuntimeError, match="No active CompileContext"):
        CompileContext.get()
    with pytest.raises(
        RuntimeError, match="must be entered with 'with' or 'async with'"
    ):
        compile_ctx.ensure_context_attached()

    with compile_ctx:
        assert CompileContext.get() is compile_ctx
        with pytest.raises(RuntimeError, match="No active PageContext"):
            PageContext.get()
        with page_ctx:
            assert CompileContext.get() is compile_ctx
            assert PageContext.get() is page_ctx
            page_ctx.ensure_context_attached()
        with pytest.raises(RuntimeError, match="No active PageContext"):
            PageContext.get()
        assert CompileContext.get() is compile_ctx

    with pytest.raises(RuntimeError, match="No active CompileContext"):
        CompileContext.get()

    with pytest.raises(ValueError, match="boom"), compile_ctx:
        msg = "boom"
        raise ValueError(msg)

    with pytest.raises(RuntimeError, match="No active CompileContext"):
        CompileContext.get()


def test_page_context_default_factories_are_isolated() -> None:
    page_ctx_a = PageContext(
        name="a",
        route="/a",
        root_component=Fragment.create(),
    )
    page_ctx_b = PageContext(
        name="b",
        route="/b",
        root_component=Fragment.create(),
    )

    page_ctx_a.imports.append({"lib-a": [ImportVar(tag="ThingA")]})
    page_ctx_a.module_code["const a = 1;"] = None
    page_ctx_a.hooks["hookA"] = None
    page_ctx_a.dynamic_imports.add("dynamic-a")
    page_ctx_a.refs["refA"] = None
    page_ctx_a.app_wrap_components[1, "WrapA"] = Fragment.create()

    assert page_ctx_b.imports == []
    assert page_ctx_b.module_code == {}
    assert page_ctx_b.hooks == {}
    assert page_ctx_b.dynamic_imports == set()
    assert page_ctx_b.refs == {}
    assert page_ctx_b.app_wrap_components == {}


def test_page_context_helpers_preserve_accumulated_values() -> None:
    page_ctx = PageContext(
        name="page",
        route="/page",
        root_component=Fragment.create(),
    )
    page_ctx.imports.extend([
        {"lib-a": [ImportVar(tag="ThingA")]},
        {"lib-a": [ImportVar(tag="ThingB")], "lib-b": [ImportVar(tag="ThingC")]},
    ])
    page_ctx.module_code["const first = 1;"] = None
    page_ctx.module_code["const second = 2;"] = None

    assert page_ctx.merged_imports() == merge_imports(*page_ctx.imports)
    assert page_ctx.merged_imports(collapse=True) == collapse_imports(
        merge_imports(*page_ctx.imports)
    )
    assert list(page_ctx.custom_code_dict()) == [
        "const first = 1;",
        "const second = 2;",
    ]


def test_base_context_subclasses_initialize_distinct_context_vars() -> None:
    class DynamicContext(BaseContext):
        pass

    class AnotherDynamicContext(BaseContext):
        pass

    assert DynamicContext.__context_var__ is not AnotherDynamicContext.__context_var__


def test_apply_style_plugin_matches_legacy_style_behavior() -> None:
    component = create_component_tree()
    legacy_component = create_component_tree()

    legacy_component._add_style_recursive(page_style())

    hooks = CompilerHooks(plugins=(ApplyStylePlugin(style=page_style()),))
    page_ctx = PageContext(name="page", route="/page", root_component=component)
    compile_ctx = create_compile_context(hooks)

    with compile_ctx, page_ctx:
        hooks.compile_component(
            component,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )

    assert normalize_style(component) == normalize_style(legacy_component)
    assert normalize_style(component.children[0]) == normalize_style(
        legacy_component.children[0]
    )
    assert component.slot is not None
    assert legacy_component.slot is not None
    assert normalize_style(component.slot) == normalize_style(legacy_component.slot)


def test_default_collector_matches_legacy_collectors() -> None:
    component = create_component_tree()
    page_ctx = collect_page_context(
        component,
        plugins=(DefaultCollectorPlugin(),),
    )

    assert page_ctx.imports == [component._get_all_imports(collapse=True)]
    assert page_ctx.hooks == component._get_all_hooks()
    assert "usePropHook" not in "".join(page_ctx.hooks)
    assert page_ctx.module_code == component._get_all_custom_code()
    assert page_ctx.dynamic_imports == component._get_all_dynamic_imports()
    assert page_ctx.refs == component._get_all_refs()
    assert page_ctx.refs == {
        format_utils.format_ref("child-id"): None,
        format_utils.format_ref("prop-id"): None,
    }
    assert (
        page_ctx.app_wrap_components.keys()
        == component._get_all_app_wrap_components().keys()
    )


def test_default_page_plugins_are_minimal_and_ordered() -> None:
    plugins = default_page_plugins(style=page_style())

    assert len(plugins) == 3
    assert isinstance(plugins[0], DefaultPagePlugin)
    assert isinstance(plugins[1], ApplyStylePlugin)
    assert isinstance(plugins[2], DefaultCollectorPlugin)


def test_compile_context_compiles_pages_and_matches_legacy_output() -> None:
    page = FakePage(route="/demo", component=create_component_tree)
    compile_ctx = CompileContext(
        pages=[page],
        hooks=CompilerHooks(plugins=default_page_plugins(style=page_style())),
    )

    with compile_ctx:
        compiled_pages = compile_ctx.compile()

    assert compiled_pages is compile_ctx.compiled_pages
    assert list(compiled_pages) == ["/demo"]

    page_ctx = compiled_pages["/demo"]
    assert isinstance(page_ctx.root_component, Component)
    assert page_ctx.name == "create_component_tree"
    assert page_ctx.route == "/demo"
    assert page_ctx.frontend_imports == page_ctx.merged_imports(collapse=True)
    compile_ctx_imports = collapse_imports(compile_ctx.all_imports)
    for lib, fields in page_ctx.frontend_imports.items():
        assert lib in compile_ctx_imports
        assert set(compile_ctx_imports[lib]) >= set(fields)
    assert page_ctx.output_path is not None
    assert page_ctx.output_code is not None
    assert page_ctx.imports == [page_ctx.root_component._get_all_imports(collapse=True)]
    assert page_ctx.hooks == page_ctx.root_component._get_all_hooks()
    assert page_ctx.module_code == page_ctx.root_component._get_all_custom_code()
    assert (
        page_ctx.dynamic_imports == page_ctx.root_component._get_all_dynamic_imports()
    )
    assert page_ctx.refs == page_ctx.root_component._get_all_refs()
    assert (
        page_ctx.app_wrap_components.keys()
        == page_ctx.root_component._get_all_app_wrap_components().keys()
    )

    legacy_component = compiler.compile_unevaluated_page(
        page.route,
        UnevaluatedPage(
            component=page.component,
            route=page.route,
            title=page.title,
            description=page.description,
            image=page.image,
            on_load=None,
            meta=page.meta,
            context={},
        ),
        page_style(),
        None,
    )
    expected_output = compiler.compile_page(page.route, legacy_component)[1]
    assert page_ctx.output_code == expected_output


def test_compile_context_does_not_recurse_root_imports() -> None:
    page = FakePage(
        route="/no-recursive-imports",
        component=create_no_recursive_imports_component,
    )
    compile_ctx = CompileContext(
        pages=[page],
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )

    with compile_ctx:
        compiled_pages = compile_ctx.compile()

    page_ctx = compiled_pages["/no-recursive-imports"]
    assert "no-recursive-imports-lib" in page_ctx.frontend_imports
    assert "no-recursive-imports-lib" in compile_ctx.all_imports
    assert page_ctx.output_code is not None


def test_default_page_plugin_handles_var_backed_title_like_legacy_compiler() -> None:
    page = UnevaluatedPage(
        component=lambda: Fragment.create(),
        route="/var-title",
        title=Var(_js_expr="pageTitle", _var_type=str),
        description=None,
        image="",
        on_load=None,
        meta=(),
        context={},
    )
    hooks = CompilerHooks(plugins=(DefaultPagePlugin(),))
    compile_ctx = create_compile_context(hooks)

    with compile_ctx:
        page_ctx = hooks.eval_page(
            page.component,
            page=page,
            compile_context=compile_ctx,
        )

    assert page_ctx is not None

    legacy_component = compiler.compile_unevaluated_page(
        page.route,
        page,
        None,
        None,
    )
    assert page_ctx.root_component.render() == legacy_component.render()


def test_compile_context_rejects_duplicate_routes() -> None:
    pages = [
        FakePage(route="/duplicate", component=lambda: Fragment.create()),
        FakePage(route="/duplicate", component=lambda: Fragment.create()),
    ]
    compile_ctx = CompileContext(
        pages=pages,
        hooks=CompilerHooks(plugins=(DefaultPagePlugin(),)),
    )

    with (
        compile_ctx,
        pytest.raises(
            RuntimeError,
            match="Duplicate compiled page route",
        ),
    ):
        compile_ctx.compile()


def test_compile_context_requires_attached_context() -> None:
    compile_ctx = CompileContext(
        pages=[],
        hooks=CompilerHooks(),
    )

    with pytest.raises(
        RuntimeError, match="must be entered with 'with' or 'async with'"
    ):
        compile_ctx.compile()


def test_compile_context_preserves_shared_stateful_component_imports_and_wraps() -> (
    None
):
    previous_mode = environment.REFLEX_ENV_MODE.get()
    environment.REFLEX_ENV_MODE.set(constants.Env.PROD)
    try:
        pages = [
            FakePage(route="/a", component=create_shared_stateful_component),
            FakePage(route="/b", component=create_shared_stateful_component),
        ]
        compile_ctx = CompileContext(
            pages=pages,
            hooks=CompilerHooks(plugins=default_page_plugins()),
        )

        with compile_ctx:
            compile_ctx.compile()

        assert "react-moment" in compile_ctx.all_imports
        assert (25, "SharedLibraryWrap") in compile_ctx.app_wrap_components
        assert "react-moment" in compile_ctx.stateful_components_code
        assert "$/utils/stateful_components" in (
            compile_ctx.compiled_pages["/a"].output_code or ""
        )
    finally:
        environment.REFLEX_ENV_MODE.set(previous_mode)


def test_compile_context_resets_stateful_component_cache_between_runs() -> None:
    previous_mode = environment.REFLEX_ENV_MODE.get()
    try:
        environment.REFLEX_ENV_MODE.set(constants.Env.PROD)
        prod_ctx = CompileContext(
            pages=[
                FakePage(route="/a", component=create_shared_stateful_component),
                FakePage(route="/b", component=create_shared_stateful_component),
            ],
            hooks=CompilerHooks(plugins=default_page_plugins()),
        )
        with prod_ctx:
            prod_ctx.compile()

        environment.REFLEX_ENV_MODE.set(constants.Env.DEV)
        dev_ctx = CompileContext(
            pages=[FakePage(route="/c", component=create_shared_stateful_component)],
            hooks=CompilerHooks(plugins=default_page_plugins()),
        )
        with dev_ctx:
            dev_ctx.compile()

        page_ctx = dev_ctx.compiled_pages["/c"]
        assert "react-moment" in page_ctx.frontend_imports
        assert "$/utils/stateful_components" not in (page_ctx.output_code or "")
    finally:
        environment.REFLEX_ENV_MODE.set(previous_mode)
