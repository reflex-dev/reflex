"""Compiler plugin infrastructure: protocols, contexts, and dispatch."""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable, Sequence
from contextvars import ContextVar, Token
from types import TracebackType
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeAlias, cast

from typing_extensions import Self

from reflex_base.components.component import BaseComponent, Component
from reflex_base.utils.imports import ParsedImportDict, collapse_imports, merge_imports
from reflex_base.vars import VarData

from .base import Plugin

if TYPE_CHECKING:
    from reflex.app import App, ComponentCallable

    PageComponent: TypeAlias = Component | ComponentCallable
else:
    PageComponent: TypeAlias = (
        Component
        | Callable[
            [],
            Component | tuple[Component, ...] | str,
        ]
    )


class PageDefinition(Protocol):
    """Protocol for page-like objects compiled by :class:`CompileContext`."""

    @property
    def route(self) -> str:
        """Return the route for this page definition."""
        ...

    @property
    def component(self) -> PageComponent:
        """Return the component or callable for this page definition."""
        ...


ComponentAndChildren: TypeAlias = tuple[BaseComponent, tuple[BaseComponent, ...]]
ComponentReplacement: TypeAlias = BaseComponent | ComponentAndChildren | None
CompiledEnterHook: TypeAlias = Callable[
    [BaseComponent, bool],
    ComponentReplacement,
]
CompiledLeaveHook: TypeAlias = Callable[
    [BaseComponent, tuple[BaseComponent, ...], bool],
    ComponentReplacement,
]
EnterHookBinder: TypeAlias = Callable[
    ["PageContext", "CompileContext"],
    CompiledEnterHook,
]
LeaveHookBinder: TypeAlias = Callable[
    ["PageContext", "CompileContext"],
    CompiledLeaveHook,
]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class CompilerHooks:
    """Dispatch compiler hooks across an ordered plugin chain."""

    plugins: tuple[Plugin, ...] = ()
    _eval_page_hooks: tuple[Callable[..., Any], ...] = dataclasses.field(
        init=False,
        repr=False,
    )
    _compile_page_hooks: tuple[Callable[..., Any], ...] = dataclasses.field(
        init=False,
        repr=False,
    )
    _enter_component_hook_binders: tuple[EnterHookBinder, ...] = dataclasses.field(
        init=False,
        repr=False,
    )
    _leave_component_hook_binders: tuple[LeaveHookBinder, ...] = dataclasses.field(
        init=False,
        repr=False,
    )
    _component_hooks_can_replace: bool = dataclasses.field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Resolve the active compiler hook callables once."""
        object.__setattr__(self, "_eval_page_hooks", self._resolve_hooks("eval_page"))
        object.__setattr__(
            self,
            "_compile_page_hooks",
            self._resolve_hooks("compile_page"),
        )
        enter_hook_binders: list[EnterHookBinder] = []
        leave_hook_binders: list[LeaveHookBinder] = []
        component_hooks_can_replace = False

        for plugin in self.plugins:
            if (
                hook_impl := self._get_hook_impl(plugin, "enter_component")
            ) is not None:
                enter_hook_binders.append(
                    self._get_enter_hook_binder(plugin, hook_impl)
                )
                component_hooks_can_replace = component_hooks_can_replace or bool(
                    getattr(
                        type(plugin),
                        "_compiler_can_replace_enter_component",
                        True,
                    )
                )

            if (
                hook_impl := self._get_hook_impl(plugin, "leave_component")
            ) is not None:
                leave_hook_binders.append(
                    self._get_leave_hook_binder(plugin, hook_impl)
                )
                component_hooks_can_replace = component_hooks_can_replace or bool(
                    getattr(
                        type(plugin),
                        "_compiler_can_replace_leave_component",
                        True,
                    )
                )

        object.__setattr__(
            self,
            "_enter_component_hook_binders",
            tuple(enter_hook_binders),
        )
        object.__setattr__(
            self,
            "_leave_component_hook_binders",
            tuple(reversed(tuple(leave_hook_binders))),
        )
        object.__setattr__(
            self,
            "_component_hooks_can_replace",
            component_hooks_can_replace,
        )

    @staticmethod
    def _get_hook_impl(
        plugin: Plugin,
        hook_name: str,
    ) -> Callable[..., Any] | None:
        """Return the concrete hook implementation for a plugin, if any.

        Args:
            plugin: The plugin to inspect.
            hook_name: The hook attribute name.

        Returns:
            The bound hook implementation, or ``None`` when the hook is inherited
            unchanged from the default base implementation.
        """
        plugin_impl = inspect.getattr_static(type(plugin), hook_name, None)
        if plugin_impl is None:
            return None

        if plugin_impl is inspect.getattr_static(Plugin, hook_name, None):
            return None

        return cast(Callable[..., Any], getattr(plugin, hook_name, None))

    def _resolve_hooks(self, hook_name: str) -> tuple[Callable[..., Any], ...]:
        """Resolve concrete hook implementations for the plugin chain.

        Args:
            hook_name: The hook attribute name.

        Returns:
            The ordered concrete hook implementations for the hook.
        """
        return tuple(
            hook_impl
            for plugin in self.plugins
            if (hook_impl := self._get_hook_impl(plugin, hook_name)) is not None
        )

    @staticmethod
    def _get_enter_hook_binder(
        plugin: Plugin,
        hook_impl: Callable[..., Any],
    ) -> EnterHookBinder:
        """Return a binder that produces a compiled enter-component hook."""
        if (
            binder := getattr(plugin, "_compiler_bind_enter_component", None)
        ) is not None:
            return cast(EnterHookBinder, binder)

        def bind(
            page_context: PageContext, compile_context: CompileContext
        ) -> CompiledEnterHook:
            def enter_component(
                comp: BaseComponent,
                in_prop_tree: bool,
            ) -> ComponentReplacement:
                return cast(
                    ComponentReplacement,
                    hook_impl(
                        comp,
                        page_context=page_context,
                        compile_context=compile_context,
                        in_prop_tree=in_prop_tree,
                    ),
                )

            return enter_component

        return bind

    @staticmethod
    def _get_leave_hook_binder(
        plugin: Plugin,
        hook_impl: Callable[..., Any],
    ) -> LeaveHookBinder:
        """Return a binder that produces a compiled leave-component hook."""
        if (
            binder := getattr(plugin, "_compiler_bind_leave_component", None)
        ) is not None:
            return cast(LeaveHookBinder, binder)

        def bind(
            page_context: PageContext, compile_context: CompileContext
        ) -> CompiledLeaveHook:
            def leave_component(
                comp: BaseComponent,
                children: tuple[BaseComponent, ...],
                in_prop_tree: bool,
            ) -> ComponentReplacement:
                return cast(
                    ComponentReplacement,
                    hook_impl(
                        comp,
                        children,
                        page_context=page_context,
                        compile_context=compile_context,
                        in_prop_tree=in_prop_tree,
                    ),
                )

            return leave_component

        return bind

    def eval_page(
        self,
        page_fn: PageComponent,
        /,
        *,
        page: PageDefinition,
        **kwargs: Any,
    ) -> PageContext | None:
        """Return the first page context produced by the plugin chain."""
        for hook_impl in self._eval_page_hooks:
            result = hook_impl(page_fn, page=page, **kwargs)
            if result is not None:
                return cast(PageContext, result)
        return None

    def compile_page(
        self,
        page_ctx: PageContext,
        /,
        **kwargs: Any,
    ) -> None:
        """Run all ``compile_page`` hooks in plugin order."""
        for hook_impl in self._compile_page_hooks:
            hook_impl(page_ctx, **kwargs)

    def compile_component(
        self,
        comp: BaseComponent,
        /,
        *,
        page_context: PageContext,
        compile_context: CompileContext,
        in_prop_tree: bool = False,
    ) -> BaseComponent:
        """Walk a component tree once while dispatching cached enter/leave hooks.

        Returns:
            The compiled component root for this subtree.
        """
        enter_hooks = tuple(
            hook_binder(page_context, compile_context)
            for hook_binder in self._enter_component_hook_binders
        )

        if not self._component_hooks_can_replace:
            leave_hooks = tuple(
                hook_binder(page_context, compile_context)
                for hook_binder in self._leave_component_hook_binders
            )

            if len(enter_hooks) == 1 and not leave_hooks:
                return self._compile_component_single_enter_fast_path(
                    comp,
                    enter_hook=enter_hooks[0],
                    in_prop_tree=in_prop_tree,
                )

            return self._compile_component_without_replacements(
                comp,
                enter_hooks=enter_hooks,
                leave_hooks=leave_hooks,
                in_prop_tree=in_prop_tree,
            )

        return self._compile_component_with_replacements(
            comp,
            enter_hooks=enter_hooks,
            leave_hooks=tuple(
                hook_binder(page_context, compile_context)
                for hook_binder in self._leave_component_hook_binders
            ),
            in_prop_tree=in_prop_tree,
        )

    def _compile_component_without_replacements(
        self,
        comp: BaseComponent,
        /,
        *,
        enter_hooks: tuple[CompiledEnterHook, ...],
        leave_hooks: tuple[CompiledLeaveHook, ...],
        in_prop_tree: bool = False,
    ) -> BaseComponent:
        """Walk a component tree when hook plans only observe state.

        Returns:
            The compiled component root for this subtree.
        """

        def visit(
            current_comp: BaseComponent,
            current_in_prop_tree: bool,
        ) -> BaseComponent:
            for hook_impl in enter_hooks:
                hook_impl(
                    current_comp,
                    current_in_prop_tree,
                )

            updated_children: list[BaseComponent] | None = None
            children = current_comp.children
            for index, child in enumerate(children):
                compiled_child = visit(
                    child,
                    current_in_prop_tree,
                )
                if updated_children is None:
                    if compiled_child is child:
                        continue
                    updated_children = list(children[:index])
                updated_children.append(compiled_child)
            if updated_children is not None:
                current_comp.children = updated_children

            if isinstance(current_comp, Component):
                for prop_component in current_comp._get_components_in_props():
                    visit(
                        prop_component,
                        True,
                    )

            if leave_hooks:
                compiled_children = tuple(current_comp.children)
                for hook_impl in leave_hooks:
                    hook_impl(
                        current_comp,
                        compiled_children,
                        current_in_prop_tree,
                    )

            return current_comp

        return visit(
            comp,
            in_prop_tree,
        )

    def _compile_component_single_enter_fast_path(
        self,
        comp: BaseComponent,
        /,
        *,
        enter_hook: CompiledEnterHook,
        in_prop_tree: bool = False,
    ) -> BaseComponent:
        """Walk a component tree for the common one-enter-hook fast path.

        Returns:
            The compiled component root for this subtree.
        """

        def visit(
            current_comp: BaseComponent,
            current_in_prop_tree: bool,
        ) -> BaseComponent:
            enter_hook(
                current_comp,
                current_in_prop_tree,
            )

            updated_children: list[BaseComponent] | None = None
            children = current_comp.children
            for index, child in enumerate(children):
                compiled_child = visit(
                    child,
                    current_in_prop_tree,
                )
                if updated_children is None:
                    if compiled_child is child:
                        continue
                    updated_children = list(children[:index])
                updated_children.append(compiled_child)
            if updated_children is not None:
                current_comp.children = updated_children

            if isinstance(current_comp, Component):
                for prop_component in current_comp._get_components_in_props():
                    visit(
                        prop_component,
                        True,
                    )

            return current_comp

        return visit(
            comp,
            in_prop_tree,
        )

    def _compile_component_with_replacements(
        self,
        comp: BaseComponent,
        /,
        *,
        enter_hooks: tuple[CompiledEnterHook, ...],
        leave_hooks: tuple[CompiledLeaveHook, ...],
        in_prop_tree: bool = False,
    ) -> BaseComponent:
        """Walk a component tree while honoring hook replacements.

        Returns:
            The compiled component root for this subtree.
        """
        apply_replacement = self._apply_replacement

        def visit_children(
            children: Sequence[BaseComponent],
            current_in_prop_tree: bool,
        ) -> tuple[BaseComponent, ...]:
            if not children:
                return ()

            updated_children: list[BaseComponent] | None = None
            for index, child in enumerate(children):
                compiled_child = visit(
                    child,
                    current_in_prop_tree,
                )
                if updated_children is None:
                    if compiled_child is child:
                        continue
                    updated_children = list(children[:index])
                updated_children.append(compiled_child)
            if updated_children is None:
                return children if isinstance(children, tuple) else tuple(children)
            return tuple(updated_children)

        def visit(
            current_comp: BaseComponent,
            current_in_prop_tree: bool,
        ) -> BaseComponent:
            compiled_component = current_comp
            structural_children: tuple[BaseComponent, ...] | None = None

            for hook_impl in enter_hooks:
                compiled_component, structural_children = apply_replacement(
                    compiled_component,
                    structural_children,
                    hook_impl(
                        compiled_component,
                        current_in_prop_tree,
                    ),
                )

            if structural_children is None:
                structural_children = tuple(compiled_component.children)
            compiled_children = visit_children(
                structural_children,
                current_in_prop_tree,
            )
            if isinstance(compiled_component, Component):
                for prop_component in compiled_component._get_components_in_props():
                    visit(
                        prop_component,
                        True,
                    )

            for hook_impl in leave_hooks:
                compiled_component, replacement_children = apply_replacement(
                    compiled_component,
                    compiled_children,
                    hook_impl(
                        compiled_component,
                        compiled_children,
                        current_in_prop_tree,
                    ),
                )
                if replacement_children is not compiled_children:
                    assert replacement_children is not None
                    compiled_children = visit_children(
                        replacement_children,
                        current_in_prop_tree,
                    )

            compiled_component.children = list(compiled_children)
            return compiled_component

        return visit(
            comp,
            in_prop_tree,
        )

    @staticmethod
    def _apply_replacement(
        comp: BaseComponent,
        children: tuple[BaseComponent, ...] | None,
        replacement: ComponentReplacement,
    ) -> tuple[BaseComponent, tuple[BaseComponent, ...] | None]:
        """Apply a plugin replacement to the current component state.

        Args:
            comp: The current component.
            children: The current structural children.
            replacement: The plugin-supplied replacement.

        Returns:
            The updated component and structural children pair.
        """
        if replacement is None:
            return comp, children
        if isinstance(replacement, tuple):
            return replacement
        return replacement, children


@dataclasses.dataclass(kw_only=True)
class BaseContext:
    """Context manager that exposes itself through a class-local context var."""

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
        """Return the active context instance for the current task.

        Returns:
            The active context instance for the current task.
        """
        context = cls.__context_var__.get()
        if context is None:
            msg = f"No active {cls.__name__} is attached to the current context."
            raise RuntimeError(msg)
        return context

    def __enter__(self) -> Self:
        """Attach this context to the current task.

        Returns:
            The attached context instance.
        """
        if self._attached_context_token is not None:
            msg = "Context is already attached and cannot be entered twice."
            raise RuntimeError(msg)
        self._attached_context_token = type(self).__context_var__.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Detach this context from the current task."""
        del exc_type, exc_val, exc_tb
        if self._attached_context_token is None:
            return
        try:
            type(self).__context_var__.reset(self._attached_context_token)
        finally:
            self._attached_context_token = None

    async def __aenter__(self) -> Self:
        """Attach this context to the current task asynchronously.

        Returns:
            The attached context instance.
        """
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Detach this context from the current task asynchronously."""
        self.__exit__(exc_type, exc_val, exc_tb)

    def ensure_context_attached(self) -> None:
        """Ensure this instance is the active context for the current task."""
        try:
            current = type(self).get()
        except RuntimeError as err:
            msg = (
                f"{type(self).__name__} must be entered with 'with' or 'async with' "
                "before calling this method."
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
    frontend_imports: ParsedImportDict = dataclasses.field(default_factory=dict)
    output_path: str | None = None
    output_code: str | None = None
    # Stack of ``id(component)`` for components whose subtree is
    # memoize-suppressed. Populated by ``MemoizeStatefulPlugin`` when it
    # encounters a ``MemoizationLeaf``-style snapshot boundary and popped on
    # the matching ``leave_component``. Non-empty iff we are inside such a
    # subtree.
    memoize_suppressor_stack: list[int] = dataclasses.field(default_factory=list)

    def merged_imports(self, *, collapse: bool = False) -> ParsedImportDict:
        """Return the imports accumulated for this page.

        Args:
            collapse: Whether to collapse duplicate imports.

        Returns:
            The merged page imports.
        """
        imports = merge_imports(*self.imports) if self.imports else {}
        return collapse_imports(imports) if collapse else imports

    def custom_code_dict(self) -> dict[str, None]:
        """Return custom-code snippets keyed like legacy collectors.

        Returns:
            The page custom code keyed by snippet.
        """
        return dict(self.module_code)


@dataclasses.dataclass(slots=True, kw_only=True)
class CompileContext(BaseContext):
    """Mutable compilation state for an entire compile run."""

    app: App | None = None
    pages: Sequence[PageDefinition]
    hooks: CompilerHooks = dataclasses.field(default_factory=CompilerHooks)
    compiled_pages: dict[str, PageContext] = dataclasses.field(default_factory=dict)
    all_imports: ParsedImportDict = dataclasses.field(default_factory=dict)
    app_wrap_components: dict[tuple[int, str], Component] = dataclasses.field(
        default_factory=dict
    )
    stateful_routes: dict[str, None] = dataclasses.field(default_factory=dict)
    # Auto-memoize wrapper tags seen during the tree walk (populated by
    # ``MemoizeStatefulPlugin``).
    memoize_wrappers: dict[str, None] = dataclasses.field(default_factory=dict)
    # Compiler-generated experimental memo definitions for auto-memoized
    # stateful wrappers. Stored as ``Any`` to keep ``reflex_base`` decoupled
    # from ``reflex.experimental.memo``.
    auto_memo_components: dict[str, Any] = dataclasses.field(default_factory=dict)

    def compile(
        self,
        *,
        evaluate_progress: Callable[[], None] | None = None,
        render_progress: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> dict[str, PageContext]:
        """Compile all configured pages through the plugin pipeline.

        Args:
            evaluate_progress: Callback invoked after each page evaluation.
            render_progress: Callback invoked after each page render.
            kwargs: Additional compiler-specific context.

        Returns:
            The compiled page contexts keyed by route.
        """
        from reflex.compiler import compiler
        from reflex.state import all_base_state_classes

        self.ensure_context_attached()
        self.compiled_pages.clear()
        self.all_imports.clear()
        self.app_wrap_components.clear()
        self.stateful_routes.clear()
        self.memoize_wrappers.clear()
        self.auto_memo_components.clear()

        for page in self.pages:
            page_fn = page.component
            n_states_before = len(all_base_state_classes)
            page_ctx = self.hooks.eval_page(
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

            if len(all_base_state_classes) > n_states_before:
                self.stateful_routes[page.route] = None

            self.compiled_pages[page_ctx.route] = page_ctx

            if evaluate_progress is not None:
                evaluate_progress()

        for page, page_ctx in zip(
            self.pages,
            self.compiled_pages.values(),
            strict=True,
        ):
            with page_ctx:
                page_ctx.root_component = self.hooks.compile_component(
                    page_ctx.root_component,
                    page_context=page_ctx,
                    compile_context=self,
                )
                self.hooks.compile_page(
                    page_ctx,
                    page=page,
                    compile_context=self,
                    **kwargs,
                )

            page_ctx.frontend_imports = page_ctx.merged_imports(collapse=True)
            self.all_imports = merge_imports(
                self.all_imports, page_ctx.frontend_imports
            )
            self.app_wrap_components.update(page_ctx.app_wrap_components)
            page_ctx.output_path, page_ctx.output_code = (
                compiler.compile_page_from_context(page_ctx)
            )

            if render_progress is not None:
                render_progress()

        return self.compiled_pages


__all__ = [
    "BaseContext",
    "CompileContext",
    "CompilerHooks",
    "ComponentAndChildren",
    "PageContext",
    "PageDefinition",
]
