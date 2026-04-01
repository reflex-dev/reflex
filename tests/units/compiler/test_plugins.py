# ruff: noqa: D101, D102

import asyncio
import dataclasses
from collections.abc import AsyncGenerator, Callable
from typing import Any, cast

import pytest
from reflex_components_core.base.fragment import Fragment
from reflex_core.components.component import (
    BaseComponent,
    Component,
    ComponentStyle,
    field,
)
from reflex_core.utils import format as format_utils
from reflex_core.utils.imports import ImportVar, collapse_imports, merge_imports

from reflex.compiler.plugins import (
    ApplyStylePlugin,
    BaseContext,
    CompileContext,
    CompilerHooks,
    CompilerPlugin,
    ComponentAndChildren,
    ConsolidateAppWrapPlugin,
    ConsolidateCustomCodePlugin,
    ConsolidateDynamicImportsPlugin,
    ConsolidateHooksPlugin,
    ConsolidateImportsPlugin,
    ConsolidateRefsPlugin,
    DefaultPagePlugin,
    PageContext,
    default_page_plugins,
)


@dataclasses.dataclass(slots=True)
class FakePage:
    route: str
    component: Callable[[], Component]
    title: str | None = None
    description: str | None = None
    image: str = ""
    meta: tuple[dict[str, Any], ...] = ()


class StubCompilerPlugin(CompilerPlugin):
    pass


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


async def collect_page_context(
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

    async with page_ctx:
        page_ctx.root_component = await hooks.compile_component(page_ctx.root_component)
        await hooks.compile_page(page_ctx)

    return page_ctx


def create_component_tree() -> RootComponent:
    return RootComponent.create(
        ChildComponent.create(id="child-id", style={"color": "red"}),
        slot=PropComponent.create(id="prop-id", style={"opacity": "0.5"}),
        style={"margin": "0"},
    )


def page_style() -> ComponentStyle:
    return {
        RootComponent: {"padding": "1rem"},
        ChildComponent: {"font_size": "12px"},
        PropComponent: {"border": "1px solid green"},
    }


class EvalPagePlugin(StubCompilerPlugin):
    async def eval_page(
        self,
        page_fn: Any,
        /,
        *,
        page: FakePage,
        **kwargs: Any,
    ) -> PageContext:
        component = page_fn() if callable(page_fn) else page_fn
        if not isinstance(component, BaseComponent):
            msg = f"Expected a BaseComponent, got {type(component).__name__}."
            raise TypeError(msg)
        name = getattr(page_fn, "__name__", page.route)
        return PageContext(
            name=name,
            route=page.route,
            root_component=component,
        )


class CollectPageDataPlugin(StubCompilerPlugin):
    async def compile_component(
        self,
        comp: BaseComponent,
        /,
        **kwargs: Any,
    ) -> AsyncGenerator[None, ComponentAndChildren]:
        compiled_component, _children = yield
        if isinstance(compiled_component, Component):
            page_ctx = PageContext.get()
            imports = compiled_component._get_imports()
            if imports:
                page_ctx.imports.append(imports)
            page_ctx.hooks.update(compiled_component._get_hooks_internal())
            if hooks := compiled_component._get_hooks():
                page_ctx.hooks[hooks] = None
            page_ctx.hooks.update(compiled_component._get_added_hooks())
            if module_code := compiled_component._get_custom_code():
                page_ctx.module_code[module_code] = None
            if dynamic_import := compiled_component._get_dynamic_imports():
                page_ctx.dynamic_imports.add(dynamic_import)
            if ref := compiled_component.get_ref():
                page_ctx.refs[ref] = None
            page_ctx.app_wrap_components.update(
                compiled_component._get_app_wrap_components()
            )

    async def compile_page(
        self,
        page_ctx: PageContext,
        /,
        **kwargs: Any,
    ) -> None:
        page_ctx.imports = (
            [collapse_imports(merge_imports(*page_ctx.imports))]
            if page_ctx.imports
            else []
        )


@pytest.mark.asyncio
async def test_eval_page_uses_first_non_none_result() -> None:
    calls: list[str] = []
    page = FakePage(route="/demo", component=lambda: Fragment.create())

    class NoMatchPlugin(StubCompilerPlugin):
        async def eval_page(
            self,
            page_fn: Any,
            /,
            *,
            page: FakePage,
            **kwargs: Any,
        ) -> None:
            del page_fn, page, kwargs
            calls.append("no-match")
            return

    class MatchPlugin(StubCompilerPlugin):
        async def eval_page(
            self,
            page_fn: Any,
            /,
            *,
            page: FakePage,
            **kwargs: Any,
        ) -> PageContext:
            calls.append("match")
            return PageContext(
                name="page",
                route=page.route,
                root_component=page_fn(),
            )

    class UnreachablePlugin(StubCompilerPlugin):
        async def eval_page(
            self,
            page_fn: Any,
            /,
            *,
            page: FakePage,
            **kwargs: Any,
        ) -> PageContext:
            del page_fn, page, kwargs
            calls.append("unreachable")
            msg = "eval_page should stop at the first page context"
            raise AssertionError(msg)

    hooks = CompilerHooks(plugins=(NoMatchPlugin(), MatchPlugin(), UnreachablePlugin()))

    page_ctx = await hooks.eval_page(page.component, page=page, compile_context=None)

    assert page_ctx is not None
    assert page_ctx.route == "/demo"
    assert calls == ["no-match", "match"]


@pytest.mark.asyncio
async def test_compile_page_runs_plugins_in_registration_order() -> None:
    calls: list[str] = []
    page_ctx = PageContext(
        name="page",
        route="/ordered",
        root_component=Fragment.create(),
    )

    class FirstPlugin(StubCompilerPlugin):
        async def compile_page(
            self,
            page_ctx: PageContext,
            /,
            **kwargs: Any,
        ) -> None:
            calls.append("first")

    class SecondPlugin(StubCompilerPlugin):
        async def compile_page(
            self,
            page_ctx: PageContext,
            /,
            **kwargs: Any,
        ) -> None:
            calls.append("second")

    hooks = CompilerHooks(plugins=(FirstPlugin(), SecondPlugin()))

    await hooks.compile_page(page_ctx, compile_context=None)

    assert calls == ["first", "second"]


@pytest.mark.asyncio
async def test_compile_page_skips_inherited_protocol_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page_ctx = PageContext(
        name="page",
        route="/ordered",
        root_component=Fragment.create(),
    )
    calls: list[str] = []

    async def fail_compile_page(
        self,
        page_ctx: PageContext,
        /,
        **kwargs: Any,
    ) -> None:
        del self, page_ctx, kwargs
        await asyncio.sleep(0)
        msg = "Inherited protocol compile_page hook should be skipped."
        raise AssertionError(msg)

    monkeypatch.setattr(CompilerPlugin, "compile_page", fail_compile_page)

    class ProtocolOnlyPlugin(CompilerPlugin):
        pass

    class RealPlugin(StubCompilerPlugin):
        async def compile_page(
            self,
            page_ctx: PageContext,
            /,
            **kwargs: Any,
        ) -> None:
            calls.append("real")

    hooks = CompilerHooks(plugins=(ProtocolOnlyPlugin(), RealPlugin()))

    await hooks.compile_page(page_ctx, compile_context=None)

    assert calls == ["real"]


@pytest.mark.asyncio
async def test_compile_component_orders_pre_and_post_by_plugin() -> None:
    events: list[str] = []
    root = RootComponent.create()

    class FirstPlugin(StubCompilerPlugin):
        async def compile_component(
            self,
            comp: BaseComponent,
            /,
            **kwargs: Any,
        ) -> AsyncGenerator[None, ComponentAndChildren]:
            events.append("first:pre")
            yield
            events.append("first:post")

    class SecondPlugin(StubCompilerPlugin):
        async def compile_component(
            self,
            comp: BaseComponent,
            /,
            **kwargs: Any,
        ) -> AsyncGenerator[None, ComponentAndChildren]:
            events.append("second:pre")
            yield
            events.append("second:post")

    hooks = CompilerHooks(plugins=(FirstPlugin(), SecondPlugin()))

    compiled_root = await hooks.compile_component(root)

    assert compiled_root is root
    assert events == ["first:pre", "second:pre", "second:post", "first:post"]


@pytest.mark.asyncio
async def test_compile_component_skips_inherited_protocol_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    root = RootComponent.create()

    async def fail_compile_component(
        self,
        comp: BaseComponent,
        /,
        **kwargs: Any,
    ) -> AsyncGenerator[None, ComponentAndChildren]:
        del self, comp, kwargs
        await asyncio.sleep(0)
        msg = "Inherited protocol compile_component hook should be skipped."
        raise AssertionError(msg)
        if False:  # pragma: no cover
            yield None

    monkeypatch.setattr(
        CompilerPlugin,
        "compile_component",
        fail_compile_component,
    )

    class ProtocolOnlyPlugin(CompilerPlugin):
        pass

    class RealPlugin(StubCompilerPlugin):
        async def compile_component(
            self,
            comp: BaseComponent,
            /,
            **kwargs: Any,
        ) -> AsyncGenerator[None, ComponentAndChildren]:
            events.append("real:pre")
            yield
            events.append("real:post")

    hooks = CompilerHooks(plugins=(ProtocolOnlyPlugin(), RealPlugin()))

    compiled_root = await hooks.compile_component(root)

    assert compiled_root is root
    assert events == ["real:pre", "real:post"]


@pytest.mark.asyncio
async def test_compile_component_traverses_children_before_prop_components() -> None:
    visited: list[str] = []
    root = RootComponent.create(
        ChildComponent.create(),
        slot=PropComponent.create(),
    )

    class VisitPlugin(StubCompilerPlugin):
        async def compile_component(
            self,
            comp: BaseComponent,
            /,
            **kwargs: Any,
        ) -> AsyncGenerator[None, ComponentAndChildren]:
            if isinstance(comp, Component):
                visited.append(comp.tag or type(comp).__name__)
            yield

    hooks = CompilerHooks(plugins=(VisitPlugin(),))
    await hooks.compile_component(root)

    assert visited == ["RootComponent", "ChildComponent", "PropComponent"]


@pytest.mark.asyncio
async def test_context_lifecycle_and_cleanup() -> None:
    compile_ctx = CompileContext(pages=[], hooks=CompilerHooks())
    page_ctx = PageContext(
        name="page",
        route="/ctx",
        root_component=Fragment.create(),
    )

    with pytest.raises(RuntimeError, match="No active CompileContext"):
        CompileContext.get()
    with pytest.raises(RuntimeError, match="must be entered with 'async with'"):
        compile_ctx.ensure_context_attached()

    async with compile_ctx:
        assert CompileContext.get() is compile_ctx
        with pytest.raises(RuntimeError, match="No active PageContext"):
            PageContext.get()
        async with page_ctx:
            assert CompileContext.get() is compile_ctx
            assert PageContext.get() is page_ctx
            page_ctx.ensure_context_attached()
        with pytest.raises(RuntimeError, match="No active PageContext"):
            PageContext.get()
        assert CompileContext.get() is compile_ctx

    with pytest.raises(RuntimeError, match="No active CompileContext"):
        CompileContext.get()

    with pytest.raises(ValueError, match="boom"):
        async with compile_ctx:
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


@pytest.mark.asyncio
async def test_apply_style_plugin_matches_legacy_recursive_behavior() -> None:
    legacy_component = create_component_tree()
    plugin_component = create_component_tree()
    style = page_style()

    legacy_component._add_style_recursive(style)
    page_ctx = await collect_page_context(
        plugin_component,
        plugins=(ApplyStylePlugin(style=style),),
    )
    compiled_root = cast(RootComponent, page_ctx.root_component)
    assert compiled_root.slot is not None
    assert legacy_component.slot is not None

    assert compiled_root.render() == legacy_component.render()
    assert compiled_root.slot.render() == legacy_component.slot.render()


@pytest.mark.asyncio
async def test_consolidate_imports_plugin_matches_legacy_recursive_collector() -> None:
    root = create_component_tree()

    page_ctx = await collect_page_context(
        root,
        plugins=(ConsolidateImportsPlugin(),),
    )

    assert page_ctx.merged_imports(collapse=True) == root._get_all_imports(
        collapse=True
    )


@pytest.mark.asyncio
async def test_consolidate_hooks_plugin_matches_legacy_recursive_collector() -> None:
    root = create_component_tree()

    page_ctx = await collect_page_context(
        root,
        plugins=(ConsolidateHooksPlugin(),),
    )

    assert page_ctx.hooks == root._get_all_hooks()
    assert "const propHook = usePropHook();" not in page_ctx.hooks


@pytest.mark.asyncio
async def test_consolidate_custom_code_plugin_matches_legacy_recursive_collector() -> (
    None
):
    root = create_component_tree()

    page_ctx = await collect_page_context(
        root,
        plugins=(ConsolidateCustomCodePlugin(),),
    )

    assert page_ctx.custom_code_dict() == root._get_all_custom_code()
    assert list(page_ctx.custom_code_dict()) == list(root._get_all_custom_code())


@pytest.mark.asyncio
async def test_consolidate_dynamic_imports_plugin_matches_legacy_recursive_collector() -> (
    None
):
    root = create_component_tree()

    page_ctx = await collect_page_context(
        root,
        plugins=(ConsolidateDynamicImportsPlugin(),),
    )

    assert page_ctx.dynamic_imports == root._get_all_dynamic_imports()


@pytest.mark.asyncio
async def test_consolidate_refs_plugin_matches_legacy_recursive_collector() -> None:
    root = create_component_tree()

    page_ctx = await collect_page_context(
        root,
        plugins=(ConsolidateRefsPlugin(),),
    )

    assert page_ctx.refs == root._get_all_refs()


@pytest.mark.asyncio
async def test_consolidate_app_wrap_plugin_matches_legacy_recursive_collector() -> None:
    root = create_component_tree()

    page_ctx = await collect_page_context(
        root,
        plugins=(ConsolidateAppWrapPlugin(),),
    )

    assert (
        page_ctx.app_wrap_components.keys()
        == root._get_all_app_wrap_components().keys()
    )
    assert (15, "PropWrap") not in page_ctx.app_wrap_components
    assert (20, "NestedWrap") in page_ctx.app_wrap_components


@pytest.mark.asyncio
async def test_default_page_plugin_evaluates_page_like_legacy_compile_path() -> None:
    page = FakePage(
        route="/demo",
        component=create_component_tree,
        title="Demo",
        description="Demo page",
        image="demo.png",
        meta=({"name": "robots", "content": "index,follow"},),
    )
    hooks = CompilerHooks(plugins=(DefaultPagePlugin(),))

    page_ctx = await hooks.eval_page(page.component, page=page)

    assert page_ctx is not None
    assert page_ctx.route == "/demo"
    assert page_ctx.name == "create_component_tree"
    assert any(child.tag == "title" for child in page_ctx.root_component.children)
    assert any(child.tag == "meta" for child in page_ctx.root_component.children)


@pytest.mark.asyncio
async def test_default_plugin_pipeline_matches_legacy_page_context_data() -> None:
    root = create_component_tree()

    page_ctx = await collect_page_context(
        root,
        plugins=default_page_plugins(),
    )

    assert page_ctx.merged_imports(collapse=True) == root._get_all_imports(
        collapse=True
    )
    assert page_ctx.hooks == root._get_all_hooks()
    assert page_ctx.custom_code_dict() == root._get_all_custom_code()
    assert page_ctx.dynamic_imports == root._get_all_dynamic_imports()
    assert page_ctx.refs == root._get_all_refs()
    assert (
        page_ctx.app_wrap_components.keys()
        == root._get_all_app_wrap_components().keys()
    )


@pytest.mark.asyncio
async def test_compile_context_compiles_pages_and_accumulates_page_data() -> None:
    page = FakePage(
        route="/demo",
        component=lambda: RootComponent.create(
            ChildComponent.create(id="child-id"),
            slot=PropComponent.create(),
        ),
    )
    compile_ctx = CompileContext(
        pages=[page],
        hooks=CompilerHooks(
            plugins=(EvalPagePlugin(), CollectPageDataPlugin()),
        ),
    )

    async with compile_ctx:
        compiled_pages = await compile_ctx.compile()

    assert compiled_pages is compile_ctx.compiled_pages
    assert list(compiled_pages) == ["/demo"]

    page_ctx = compiled_pages["/demo"]
    assert page_ctx.name == "<lambda>"
    assert page_ctx.route == "/demo"
    assert page_ctx.imports
    assert set(page_ctx.frontend_imports) >= {
        "root-lib",
        "child-lib",
        "prop-lib",
        "react",
    }
    assert page_ctx.output_path is not None
    assert page_ctx.output_code is not None
    assert "RootComponent" in page_ctx.output_code
    assert page_ctx.module_code == {
        "const propCustomCode = 1;": None,
        "const propAddedCode = 1;": None,
        "const rootAddedCode = 1;": None,
        "const childCustomCode = 1;": None,
        "const childAddedCode = 1;": None,
    }
    assert page_ctx.dynamic_imports == {"dynamic(() => import('prop-lib'))"}
    assert any("useChildHook" in hook for hook in page_ctx.hooks)
    assert any("useRef" in hook for hook in page_ctx.hooks)
    assert page_ctx.refs == {format_utils.format_ref("child-id"): None}
    assert (10, "Wrap") in page_ctx.app_wrap_components
    assert (15, "PropWrap") in page_ctx.app_wrap_components


@pytest.mark.asyncio
async def test_compile_context_rejects_duplicate_routes() -> None:
    pages = [
        FakePage(route="/duplicate", component=lambda: Fragment.create()),
        FakePage(route="/duplicate", component=lambda: Fragment.create()),
    ]
    compile_ctx = CompileContext(
        pages=pages,
        hooks=CompilerHooks(plugins=(EvalPagePlugin(),)),
    )

    async with compile_ctx:
        with pytest.raises(RuntimeError, match="Duplicate compiled page route"):
            await compile_ctx.compile()


@pytest.mark.asyncio
async def test_compile_context_requires_attached_context() -> None:
    compile_ctx = CompileContext(
        pages=[],
        hooks=CompilerHooks(),
    )

    with pytest.raises(RuntimeError, match="must be entered with 'async with'"):
        await compile_ctx.compile()
