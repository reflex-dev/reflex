# ruff: noqa: D101, D102

import dataclasses
from collections.abc import AsyncGenerator, Callable
from typing import Any

import pytest
from reflex_components_core.base.fragment import Fragment
from reflex_core.components.component import BaseComponent, Component, field
from reflex_core.utils import format as format_utils
from reflex_core.utils.imports import ImportVar, collapse_imports, merge_imports

from reflex.compiler.plugins import (
    BaseContext,
    CompileComponentYield,
    CompileContext,
    CompilerHooks,
    ComponentAndChildren,
    PageContext,
    collect_component_tree_artifacts,
)


@dataclasses.dataclass(slots=True)
class FakePage:
    route: str
    component: Callable[[], Component]


class TestCompilerPlugin:
    async def eval_page(self, page_fn: Any, /, **kwargs: Any) -> PageContext | None:
        return None

    async def compile_page(
        self,
        page_ctx: PageContext,
        /,
        **kwargs: Any,
    ) -> None:
        return

    async def compile_component(
        self,
        comp: BaseComponent,
        /,
        **kwargs: Any,
    ) -> AsyncGenerator[CompileComponentYield, ComponentAndChildren]:
        if False:  # pragma: no cover
            yield None
        return


class RootComponent(Component):
    tag = "RootComponent"
    library = "root-lib"

    slot: Component | None = field(default=None)

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        return {(10, "Wrap"): Fragment.create()}


class ChildComponent(Component):
    tag = "ChildComponent"
    library = "child-lib"

    def _get_custom_code(self) -> str | None:
        return "const childCustomCode = 1;"

    def _get_hooks(self) -> str | None:
        return "const childHook = useChildHook();"


class PropComponent(Component):
    tag = "PropComponent"
    library = "prop-lib"

    def _get_dynamic_imports(self) -> str | None:
        return "dynamic(() => import('prop-lib'))"


class OrderedRootComponent(Component):
    tag = "OrderedRootComponent"
    library = "ordered-root-lib"

    slot: Component | None = field(default=None)

    def _get_custom_code(self) -> str | None:
        return "const rootCustomCode = 1;"

    def add_custom_code(self) -> list[str]:
        return ["const rootAddedCustomCode = 2;"]


class OrderedPropComponent(Component):
    tag = "OrderedPropComponent"
    library = "ordered-prop-lib"

    def _get_custom_code(self) -> str | None:
        return "const propCustomCode = 3;"

    def add_custom_code(self) -> list[str]:
        return ["const propAddedCustomCode = 4;"]


class OrderedChildComponent(Component):
    tag = "OrderedChildComponent"
    library = "ordered-child-lib"

    def _get_custom_code(self) -> str | None:
        return "const childCustomCode = 5;"

    def add_custom_code(self) -> list[str]:
        return ["const childAddedCustomCode = 6;"]


class EvalPagePlugin(TestCompilerPlugin):
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


class CollectPageDataPlugin(TestCompilerPlugin):
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

    class NoMatchPlugin(TestCompilerPlugin):
        async def eval_page(self, page_fn: Any, /, **kwargs: Any) -> None:
            calls.append("no-match")
            return

    class MatchPlugin(TestCompilerPlugin):
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

    class UnreachablePlugin(TestCompilerPlugin):
        async def eval_page(self, page_fn: Any, /, **kwargs: Any) -> PageContext:
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

    class FirstPlugin(TestCompilerPlugin):
        async def compile_page(
            self,
            page_ctx: PageContext,
            /,
            **kwargs: Any,
        ) -> None:
            calls.append("first")

    class SecondPlugin(TestCompilerPlugin):
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
async def test_compile_component_orders_pre_and_post_by_plugin() -> None:
    events: list[str] = []
    root = RootComponent.create()

    class FirstPlugin(TestCompilerPlugin):
        async def compile_component(
            self,
            comp: BaseComponent,
            /,
            **kwargs: Any,
        ) -> AsyncGenerator[None, ComponentAndChildren]:
            events.append("first:pre")
            yield
            events.append("first:post")

    class SecondPlugin(TestCompilerPlugin):
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
async def test_compile_component_traverses_children_before_prop_components() -> None:
    visited: list[str] = []
    root = RootComponent.create(
        ChildComponent.create(),
        slot=PropComponent.create(),
    )

    class VisitPlugin(TestCompilerPlugin):
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


def test_base_context_subclasses_initialize_distinct_context_vars() -> None:
    class DynamicContext(BaseContext):
        pass

    class AnotherDynamicContext(BaseContext):
        pass

    assert DynamicContext.__context_var__ is not AnotherDynamicContext.__context_var__


def test_single_pass_collector_matches_legacy_recursive_collectors() -> None:
    root = RootComponent.create(
        ChildComponent.create(id="child-id"),
        slot=PropComponent.create(),
    )

    collected = collect_component_tree_artifacts(root)

    assert collapse_imports(collected["imports"]) == collapse_imports(
        root._get_all_imports()
    )
    assert collected["hooks"] == root._get_all_hooks()
    assert collected["custom_code"] == root._get_all_custom_code()
    assert collected["dynamic_imports"] == root._get_all_dynamic_imports()
    assert collected["refs"] == root._get_all_refs()
    assert (
        collected["app_wrap_components"].keys()
        == root._get_all_app_wrap_components().keys()
    )


def test_single_pass_collector_preserves_legacy_custom_code_order() -> None:
    root = OrderedRootComponent.create(
        OrderedChildComponent.create(),
        slot=OrderedPropComponent.create(),
    )

    collected = collect_component_tree_artifacts(root)
    legacy_custom_code = root._get_all_custom_code()

    assert list(collected["custom_code"]) == list(legacy_custom_code)
    assert list(collected["custom_code"]) == [
        "const rootCustomCode = 1;",
        "const propCustomCode = 3;",
        "const propAddedCustomCode = 4;",
        "const rootAddedCustomCode = 2;",
        "const childCustomCode = 5;",
        "const childAddedCustomCode = 6;",
    ]


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
    assert set(page_ctx.imports[0]) >= {"root-lib", "child-lib", "prop-lib", "react"}
    assert page_ctx.module_code == {"const childCustomCode = 1;": None}
    assert page_ctx.dynamic_imports == {"dynamic(() => import('prop-lib'))"}
    assert any("useChildHook" in hook for hook in page_ctx.hooks)
    assert any("useRef" in hook for hook in page_ctx.hooks)
    assert page_ctx.refs == {format_utils.format_ref("child-id"): None}
    assert (10, "Wrap") in page_ctx.app_wrap_components


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
