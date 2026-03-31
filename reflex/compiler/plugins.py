"""Compiler plugin foundations for single-pass page compilation."""

from __future__ import annotations

import dataclasses
from collections.abc import AsyncGenerator, Sequence
from contextvars import ContextVar, Token
from types import TracebackType
from typing import Any, ClassVar, Literal, Protocol, TypeAlias, cast, overload

from reflex_core.components.component import BaseComponent, Component, StatefulComponent
from reflex_core.utils.imports import ParsedImportDict, collapse_imports, merge_imports
from reflex_core.vars import VarData
from typing_extensions import Self


class PageDefinition(Protocol):
    """Protocol for page-like objects compiled by :class:`CompileContext`."""

    route: str
    component: Any


ComponentAndChildren: TypeAlias = tuple[BaseComponent, tuple[BaseComponent, ...]]
CompileComponentYield: TypeAlias = BaseComponent | ComponentAndChildren | None


class CompilerPlugin(Protocol):
    """Protocol for compiler plugins that participate in page compilation."""

    async def eval_page(
        self,
        page_fn: Any,
        /,
        **kwargs: Any,
    ) -> PageContext | None:
        """Evaluate a page-like object into a page context."""
        ...

    async def compile_page(
        self,
        page_ctx: PageContext,
        /,
        **kwargs: Any,
    ) -> None:
        """Finalize a page context after its component tree has been traversed."""
        ...

    def compile_component(
        self,
        comp: BaseComponent,
        /,
        **kwargs: Any,
    ) -> AsyncGenerator[CompileComponentYield, ComponentAndChildren]:
        """Inspect or transform a component during recursive compilation."""
        ...


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class CompilerHooks:
    """Dispatch compiler hooks across an ordered plugin chain."""

    plugins: tuple[CompilerPlugin, ...] = ()

    @overload
    async def _dispatch(
        self,
        hook_name: str,
        *args: Any,
        stop_on_result: Literal[False] = False,
        **kwargs: Any,
    ) -> list[Any]: ...

    @overload
    async def _dispatch(
        self,
        hook_name: str,
        *args: Any,
        stop_on_result: Literal[True],
        **kwargs: Any,
    ) -> Any | None: ...

    async def _dispatch(
        self,
        hook_name: str,
        *args: Any,
        stop_on_result: bool = False,
        **kwargs: Any,
    ) -> list[Any] | Any | None:
        """Dispatch a coroutine hook across all plugins in registration order.

        Args:
            hook_name: The plugin hook attribute to invoke.
            *args: Positional arguments forwarded to the hook.
            stop_on_result: Whether to return immediately on the first non-None
                result instead of collecting all results.
            **kwargs: Keyword arguments forwarded to the hook.

        Returns:
            When ``stop_on_result`` is false, a list of hook return values in
            registration order. Otherwise, the first non-None result, or
            ``None`` if every plugin returned ``None``.
        """
        results: list[Any] = []
        for plugin in self.plugins:
            result = await getattr(plugin, hook_name)(*args, **kwargs)
            if stop_on_result and result is not None:
                return result
            results.append(result)
        return None if stop_on_result else results

    async def eval_page(
        self,
        page_fn: Any,
        /,
        **kwargs: Any,
    ) -> PageContext | None:
        """Return the first page context produced by the plugin chain."""
        result = await self._dispatch(
            "eval_page",
            page_fn,
            stop_on_result=True,
            **kwargs,
        )
        return cast(PageContext | None, result)

    async def compile_page(
        self,
        page_ctx: PageContext,
        /,
        **kwargs: Any,
    ) -> None:
        """Run all ``compile_page`` hooks in plugin order."""
        await self._dispatch("compile_page", page_ctx, **kwargs)

    async def compile_component(
        self,
        comp: BaseComponent,
        /,
        **kwargs: Any,
    ) -> BaseComponent:
        """Walk a component tree once while dispatching component hooks.

        Plugins are entered in registration order before children are visited and
        unwound in reverse order after the structural children have been
        compiled. Component-valued props are traversed after structural children
        for collection and side effects, but their transformed values are not
        written back to the parent in this foundational slice.

        Args:
            comp: The component to compile.
            **kwargs: Additional context shared with plugins.

        Returns:
            The compiled component.
        """
        active_generators: list[
            AsyncGenerator[CompileComponentYield, ComponentAndChildren]
        ] = []
        compiled_component = comp
        structural_children: tuple[BaseComponent, ...] | None = None

        try:
            for plugin in self.plugins:
                generator = plugin.compile_component(compiled_component, **kwargs)
                active_generators.append(generator)
                try:
                    replacement = await anext(generator)
                except StopAsyncIteration:
                    replacement = None
                compiled_component, structural_children = self._apply_replacement(
                    compiled_component,
                    structural_children,
                    replacement,
                )

            structural_children = (
                structural_children
                if structural_children is not None
                else tuple(compiled_component.children)
            )
            compiled_children = await self._compile_children(
                structural_children,
                **kwargs,
            )

            if isinstance(compiled_component, Component):
                for prop_component in compiled_component._get_components_in_props():
                    await self.compile_component(prop_component, **kwargs)

            for generator in reversed(active_generators):
                try:
                    replacement = await generator.asend((
                        compiled_component,
                        compiled_children,
                    ))
                except StopAsyncIteration:
                    replacement = None
                compiled_component, replacement_children = self._apply_replacement(
                    compiled_component,
                    compiled_children,
                    replacement,
                )
                if replacement_children is not compiled_children:
                    compiled_children = await self._compile_children(
                        replacement_children,
                        **kwargs,
                    )

            compiled_component.children = list(compiled_children)
            return compiled_component
        finally:
            for generator in reversed(active_generators):
                await generator.aclose()

    async def _compile_children(
        self,
        children: Sequence[BaseComponent],
        **kwargs: Any,
    ) -> tuple[BaseComponent, ...]:
        """Compile a sequence of structural children in order.

        Args:
            children: The structural children to compile.
            **kwargs: Additional keyword arguments forwarded to the walker.

        Returns:
            The compiled children in their original order.
        """
        compiled_children = [
            await self.compile_component(child, **kwargs) for child in children
        ]
        return tuple(compiled_children)

    @staticmethod
    def _apply_replacement(
        comp: BaseComponent,
        children: tuple[BaseComponent, ...] | None,
        replacement: CompileComponentYield,
    ) -> tuple[BaseComponent, tuple[BaseComponent, ...] | None]:
        """Apply a plugin replacement to the current component state.

        Args:
            comp: The current component.
            children: The current structural children.
            replacement: The replacement returned by a plugin hook.

        Returns:
            The updated component and structural children tuple.
        """
        if replacement is None:
            return comp, children
        if isinstance(replacement, tuple):
            return replacement
        return replacement, children


@dataclasses.dataclass(kw_only=True)
class BaseContext:
    """Async context manager that exposes itself through a class-local context var."""

    __context_var__: ClassVar[ContextVar[Self | None]]

    _attached_context_token: Token[Self | None] | None = dataclasses.field(
        default=None,
        init=False,
        repr=False,
    )

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Initialize a dedicated context variable for each subclass."""
        super().__init_subclass__(**kwargs)
        cls.__context_var__ = ContextVar(cls.__name__, default=None)

    @classmethod
    def get(cls) -> Self:
        """Return the active context instance for the current task."""
        context = cls.__context_var__.get()
        if context is None:
            msg = f"No active {cls.__name__} is attached to the current context."
            raise RuntimeError(msg)
        return context

    async def __aenter__(self) -> Self:
        """Attach this context to the current task.

        Returns:
            The attached context instance.
        """
        if self._attached_context_token is not None:
            msg = "Context is already attached and cannot be entered twice."
            raise RuntimeError(msg)
        self._attached_context_token = type(self).__context_var__.set(self)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Detach this context from the current task."""
        if self._attached_context_token is None:
            return
        try:
            type(self).__context_var__.reset(self._attached_context_token)
        finally:
            self._attached_context_token = None

    def ensure_context_attached(self) -> None:
        """Ensure this instance is the active context for the current task."""
        try:
            current = type(self).get()
        except RuntimeError as err:
            msg = (
                f"{type(self).__name__} must be entered with 'async with' before "
                "calling this method."
            )
            raise RuntimeError(msg) from err
        if current is not self:
            msg = f"{type(self).__name__} is not attached to the current task context."
            raise RuntimeError(msg)


@dataclasses.dataclass(slots=True, kw_only=True)
class PageContext(BaseContext):
    """Mutable compilation state for a single page."""

    name: str
    route: str
    root_component: BaseComponent
    imports: list[ParsedImportDict] = dataclasses.field(default_factory=list)
    module_code: dict[str, None] = dataclasses.field(default_factory=dict)
    hooks: dict[str, VarData | None] = dataclasses.field(default_factory=dict)
    dynamic_imports: set[str] = dataclasses.field(default_factory=set)
    refs: dict[str, None] = dataclasses.field(default_factory=dict)
    app_wrap_components: dict[tuple[int, str], Component] = dataclasses.field(
        default_factory=dict
    )

    def merged_imports(self, *, collapse: bool = False) -> ParsedImportDict:
        """Return the imports accumulated for this page.

        Args:
            collapse: Whether to deduplicate import vars before returning.

        Returns:
            The merged import dictionary.
        """
        imports = merge_imports(*self.imports) if self.imports else {}
        return collapse_imports(imports) if collapse else imports

    def custom_code_dict(self) -> dict[str, None]:
        """Return custom-code snippets keyed like legacy collectors."""
        return dict(self.module_code)


@dataclasses.dataclass(slots=True, kw_only=True)
class CompileContext(BaseContext):
    """Mutable compilation state for an entire compile run."""

    pages: Sequence[PageDefinition]
    hooks: CompilerHooks = dataclasses.field(default_factory=CompilerHooks)
    compiled_pages: dict[str, PageContext] = dataclasses.field(default_factory=dict)

    async def compile(self, **kwargs: Any) -> dict[str, PageContext]:
        """Compile all configured pages through the plugin pipeline.

        Args:
            **kwargs: Additional keyword arguments forwarded to plugin hooks.

        Returns:
            The compiled pages keyed by route.

        Raises:
            RuntimeError: If no plugin can evaluate a page, or if two compiled
                pages resolve to the same route.
        """
        self.ensure_context_attached()
        self.compiled_pages.clear()

        for page in self.pages:
            page_fn = page.component
            page_ctx = await self.hooks.eval_page(
                page_fn,
                page=page,
                compile_context=self,
                **kwargs,
            )
            if page_ctx is None:
                page_name = getattr(page_fn, "__name__", repr(page_fn))
                msg = (
                    f"No compiler plugin was able to evaluate page {page.route!r} "
                    f"({page_name})."
                )
                raise RuntimeError(msg)
            if page_ctx.route in self.compiled_pages:
                msg = f"Duplicate compiled page route {page_ctx.route!r}."
                raise RuntimeError(msg)

            async with page_ctx:
                page_ctx.root_component = await self.hooks.compile_component(
                    page_ctx.root_component,
                    page=page,
                    page_context=page_ctx,
                    compile_context=self,
                    **kwargs,
                )
                await self.hooks.compile_page(
                    page_ctx,
                    page=page,
                    compile_context=self,
                    **kwargs,
                )

            self.compiled_pages[page_ctx.route] = page_ctx

        return self.compiled_pages


def collect_component_tree_context(
    component: BaseComponent,
    *,
    name: str = "",
    route: str = "",
    collect_imports: bool = True,
    collect_hooks: bool = True,
    collect_custom_code: bool = True,
    collect_dynamic_imports: bool = True,
    collect_refs: bool = True,
    collect_app_wrap_components: bool = True,
    stateful_custom_code_export: bool = False,
) -> PageContext:
    """Collect compilation artifacts from a component tree in a single walk.

    This is a synchronous bridge for the existing compiler pipeline. It mirrors
    the semantics of the legacy recursive ``_get_all_*`` methods while avoiding
    multiple full-tree walks over the same component hierarchy.

    Args:
        component: The component tree root.
        name: Optional logical page name for the returned context.
        route: Optional logical page route for the returned context.
        collect_imports: Whether to gather imports.
        collect_hooks: Whether to gather hooks.
        collect_custom_code: Whether to gather custom module code.
        collect_dynamic_imports: Whether to gather dynamic imports.
        collect_refs: Whether to gather refs.
        collect_app_wrap_components: Whether to gather app-wrap components.
        stateful_custom_code_export: Whether generated StatefulComponent code
            should use export statements.

    Returns:
        The populated page context.
    """
    page_ctx = PageContext(
        name=name or getattr(component, "tag", type(component).__name__),
        route=route,
        root_component=component,
    )
    _collect_component_subtree(
        component,
        page_ctx,
        collect_imports=collect_imports,
        collect_hooks=collect_hooks,
        collect_custom_code=collect_custom_code,
        collect_dynamic_imports=collect_dynamic_imports,
        collect_refs=collect_refs,
        collect_app_wrap_components=collect_app_wrap_components,
        stateful_custom_code_export=stateful_custom_code_export,
        app_wrap_ignore_ids=set(),
    )
    return page_ctx


def collect_component_tree_artifacts(
    component: BaseComponent,
    *,
    name: str = "",
    route: str = "",
    collect_imports: bool = True,
    collect_hooks: bool = True,
    collect_custom_code: bool = True,
    collect_dynamic_imports: bool = True,
    collect_refs: bool = True,
    collect_app_wrap_components: bool = True,
    stateful_custom_code_export: bool = False,
) -> dict[str, Any]:
    """Collect legacy compiler artifacts from a component tree in one pass.

    Args:
        component: The component tree root.
        name: Optional logical page name for the collection context.
        route: Optional logical page route for the collection context.
        collect_imports: Whether to gather imports.
        collect_hooks: Whether to gather hooks.
        collect_custom_code: Whether to gather custom module code.
        collect_dynamic_imports: Whether to gather dynamic imports.
        collect_refs: Whether to gather refs.
        collect_app_wrap_components: Whether to gather app-wrap components.
        stateful_custom_code_export: Whether generated StatefulComponent code
            should use export statements.

    Returns:
        A dict matching the legacy compiler collector outputs.
    """
    page_ctx = collect_component_tree_context(
        component,
        name=name,
        route=route,
        collect_imports=collect_imports,
        collect_hooks=collect_hooks,
        collect_custom_code=collect_custom_code,
        collect_dynamic_imports=collect_dynamic_imports,
        collect_refs=collect_refs,
        collect_app_wrap_components=collect_app_wrap_components,
        stateful_custom_code_export=stateful_custom_code_export,
    )
    return {
        "imports": page_ctx.merged_imports(),
        "hooks": dict(page_ctx.hooks),
        "custom_code": page_ctx.custom_code_dict(),
        "dynamic_imports": set(page_ctx.dynamic_imports),
        "refs": dict(page_ctx.refs),
        "app_wrap_components": dict(page_ctx.app_wrap_components),
    }


def _collect_component_subtree(
    component: BaseComponent,
    page_ctx: PageContext,
    *,
    collect_imports: bool,
    collect_hooks: bool,
    collect_custom_code: bool,
    collect_dynamic_imports: bool,
    collect_refs: bool,
    collect_app_wrap_components: bool,
    stateful_custom_code_export: bool,
    app_wrap_ignore_ids: set[int],
) -> None:
    """Recursively collect component data with legacy traversal semantics."""
    if isinstance(component, StatefulComponent):
        _collect_stateful_component_subtree(
            component,
            page_ctx,
            collect_imports=collect_imports,
            collect_hooks=collect_hooks,
            collect_custom_code=collect_custom_code,
            collect_dynamic_imports=collect_dynamic_imports,
            collect_refs=collect_refs,
            collect_app_wrap_components=collect_app_wrap_components,
            stateful_custom_code_export=stateful_custom_code_export,
            app_wrap_ignore_ids=app_wrap_ignore_ids,
        )
        return

    if not isinstance(component, Component):
        _collect_non_component_subtree(
            component,
            page_ctx,
            collect_imports=collect_imports,
            collect_hooks=collect_hooks,
            collect_custom_code=collect_custom_code,
            collect_dynamic_imports=collect_dynamic_imports,
            collect_refs=collect_refs,
            collect_app_wrap_components=collect_app_wrap_components,
        )
        return

    if collect_imports:
        imports = component._get_imports()
        if imports:
            page_ctx.imports.append(imports)

    if collect_hooks:
        page_ctx.hooks.update(component._get_hooks_internal())
        if hooks := component._get_hooks():
            page_ctx.hooks[hooks] = None
        page_ctx.hooks.update(component._get_added_hooks())

    if collect_custom_code:
        if custom_code := component._get_custom_code():
            page_ctx.module_code[custom_code] = None

        for prop_component in component._get_components_in_props():
            _collect_component_subtree(
                prop_component,
                page_ctx,
                collect_imports=False,
                collect_hooks=False,
                collect_custom_code=True,
                collect_dynamic_imports=False,
                collect_refs=False,
                collect_app_wrap_components=False,
                stateful_custom_code_export=stateful_custom_code_export,
                app_wrap_ignore_ids=app_wrap_ignore_ids,
            )

        for clz in component._iter_parent_classes_with_method("add_custom_code"):
            for item in clz.add_custom_code(component):
                page_ctx.module_code[item] = None

    if collect_dynamic_imports and (dynamic_import := component._get_dynamic_imports()):
        page_ctx.dynamic_imports.add(dynamic_import)

    if collect_refs and (ref := component.get_ref()) is not None:
        page_ctx.refs[ref] = None

    if collect_app_wrap_components:
        direct_wrappers = component._get_app_wrap_components()
        if direct_wrappers:
            page_ctx.app_wrap_components.update(direct_wrappers)
            for wrapper in direct_wrappers.values():
                wrapper_id = id(wrapper)
                if wrapper_id in app_wrap_ignore_ids:
                    continue
                app_wrap_ignore_ids.add(wrapper_id)
                _collect_component_subtree(
                    wrapper,
                    page_ctx,
                    collect_imports=False,
                    collect_hooks=False,
                    collect_custom_code=False,
                    collect_dynamic_imports=False,
                    collect_refs=False,
                    collect_app_wrap_components=True,
                    stateful_custom_code_export=stateful_custom_code_export,
                    app_wrap_ignore_ids=app_wrap_ignore_ids,
                )

    for child in component.children:
        _collect_component_subtree(
            child,
            page_ctx,
            collect_imports=collect_imports,
            collect_hooks=collect_hooks,
            collect_custom_code=collect_custom_code,
            collect_dynamic_imports=collect_dynamic_imports,
            collect_refs=collect_refs,
            collect_app_wrap_components=collect_app_wrap_components,
            stateful_custom_code_export=stateful_custom_code_export,
            app_wrap_ignore_ids=app_wrap_ignore_ids,
        )

    if collect_dynamic_imports or collect_refs:
        for prop_component in component._get_components_in_props():
            _collect_component_subtree(
                prop_component,
                page_ctx,
                collect_imports=False,
                collect_hooks=False,
                collect_custom_code=False,
                collect_dynamic_imports=collect_dynamic_imports,
                collect_refs=collect_refs,
                collect_app_wrap_components=False,
                stateful_custom_code_export=stateful_custom_code_export,
                app_wrap_ignore_ids=app_wrap_ignore_ids,
            )


def _collect_stateful_component_subtree(
    component: StatefulComponent,
    page_ctx: PageContext,
    *,
    collect_imports: bool,
    collect_hooks: bool,
    collect_custom_code: bool,
    collect_dynamic_imports: bool,
    collect_refs: bool,
    collect_app_wrap_components: bool,
    stateful_custom_code_export: bool,
    app_wrap_ignore_ids: set[int],
) -> None:
    """Collect from a StatefulComponent while preserving legacy semantics."""
    del collect_hooks, collect_app_wrap_components
    if component.rendered_as_shared:
        if collect_imports:
            imports = component._get_all_imports()
            if imports:
                page_ctx.imports.append(imports)
        return

    _collect_component_subtree(
        component.component,
        page_ctx,
        collect_imports=collect_imports,
        collect_hooks=False,
        collect_custom_code=collect_custom_code,
        collect_dynamic_imports=collect_dynamic_imports,
        collect_refs=collect_refs,
        collect_app_wrap_components=False,
        stateful_custom_code_export=stateful_custom_code_export,
        app_wrap_ignore_ids=app_wrap_ignore_ids,
    )
    if collect_custom_code:
        rendered_stateful_code = component._render_stateful_code(
            export=stateful_custom_code_export
        )
        page_ctx.module_code[rendered_stateful_code] = None


def _collect_non_component_subtree(
    component: BaseComponent,
    page_ctx: PageContext,
    *,
    collect_imports: bool,
    collect_hooks: bool,
    collect_custom_code: bool,
    collect_dynamic_imports: bool,
    collect_refs: bool,
    collect_app_wrap_components: bool,
) -> None:
    """Fallback collector for BaseComponent types without local per-node hooks."""
    if collect_imports:
        imports = component._get_all_imports()
        if imports:
            page_ctx.imports.append(imports)
    if collect_hooks:
        page_ctx.hooks.update(component._get_all_hooks())
    if collect_custom_code:
        page_ctx.module_code.update(component._get_all_custom_code())
    if collect_dynamic_imports:
        page_ctx.dynamic_imports.update(component._get_all_dynamic_imports())
    if collect_refs:
        page_ctx.refs.update(component._get_all_refs())


__all__ = [
    "BaseContext",
    "CompileComponentYield",
    "CompileContext",
    "CompilerHooks",
    "CompilerPlugin",
    "ComponentAndChildren",
    "PageContext",
    "PageDefinition",
    "collect_component_tree_artifacts",
    "collect_component_tree_context",
]
