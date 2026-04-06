"""Compiler plugin infrastructure: protocols, contexts, and dispatch."""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable, Sequence
from contextvars import ContextVar, Token
from types import TracebackType
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeAlias, cast

from typing_extensions import Self

from reflex_base.components.component import BaseComponent, Component, StatefulComponent
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
    [BaseComponent, bool, StatefulComponent | None],
    ComponentReplacement,
]
CompiledLeaveHook: TypeAlias = Callable[
    [BaseComponent, tuple[BaseComponent, ...], bool, StatefulComponent | None],
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


class CompilerPlugin(Protocol):
    """Protocol for compiler plugins that participate in page compilation."""

    def eval_page(
        self,
        page_fn: PageComponent,
        /,
        *,
        page: PageDefinition,
        **kwargs: Any,
    ) -> PageContext | None:
        """Evaluate a page-like object into a page context.

        Args:
            page_fn: The page-like object to evaluate.
            page: The page definition being compiled.
            kwargs: Additional compiler-specific context.

        Returns:
            A page context when the plugin can evaluate the page, otherwise ``None``.
        """
        return None

    def compile_page(
        self,
        page_ctx: PageContext,
        /,
        **kwargs: Any,
    ) -> None:
        """Finalize a page context after its component tree has been traversed."""
        return

    def enter_component(
        self,
        comp: BaseComponent,
        /,
        *,
        page_context: PageContext,
        compile_context: CompileContext,
        in_prop_tree: bool = False,
        stateful_component: StatefulComponent | None = None,
    ) -> ComponentReplacement:
        """Inspect or transform a component before visiting its descendants.

        Args:
            comp: The component being compiled.
            page_context: The active page compilation state.
            compile_context: The active compile-run state.
            in_prop_tree: Whether the component belongs to a prop subtree.
            stateful_component: The active surrounding stateful component.

        Returns:
            An optional replacement component and/or structural children.
        """
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
    ) -> ComponentReplacement:
        """Inspect or transform a component after visiting its descendants.

        Args:
            comp: The component being compiled.
            children: The compiled structural children for the component.
            page_context: The active page compilation state.
            compile_context: The active compile-run state.
            in_prop_tree: Whether the component belongs to a prop subtree.
            stateful_component: The active surrounding stateful component.

        Returns:
            An optional replacement component and/or structural children.
        """
        return None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class CompilerHooks:
    """Dispatch compiler hooks across an ordered plugin chain."""

    plugins: tuple[CompilerPlugin, ...] = ()
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
    _leave_component_hook_binders: tuple[tuple[LeaveHookBinder, bool], ...] = (
        dataclasses.field(
            init=False,
            repr=False,
        )
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
        leave_hook_binders: list[tuple[LeaveHookBinder, bool]] = []

        for plugin in self.plugins:
            if (
                hook_impl := self._get_hook_impl(plugin, "enter_component")
            ) is not None:
                enter_hook_binders.append(
                    self._get_enter_hook_binder(plugin, hook_impl)
                )

            if (
                hook_impl := self._get_hook_impl(plugin, "leave_component")
            ) is not None:
                stateful_only = bool(
                    getattr(
                        type(plugin),
                        "_compiler_stateful_only_leave_component",
                        False,
                    )
                )
                leave_hook_binders.append((
                    self._get_leave_hook_binder(plugin, hook_impl),
                    stateful_only,
                ))

        reversed_leave_hook_binders = tuple(reversed(tuple(leave_hook_binders)))
        object.__setattr__(
            self,
            "_enter_component_hook_binders",
            tuple(enter_hook_binders),
        )
        object.__setattr__(
            self,
            "_leave_component_hook_binders",
            reversed_leave_hook_binders,
        )

    @staticmethod
    def _get_hook_impl(
        plugin: CompilerPlugin,
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

        for base_cls in (CompilerPlugin, Plugin):
            base_impl = inspect.getattr_static(base_cls, hook_name, None)
            if plugin_impl is base_impl:
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
        plugin: CompilerPlugin,
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
                stateful_component: StatefulComponent | None,
            ) -> ComponentReplacement:
                return cast(
                    ComponentReplacement,
                    hook_impl(
                        comp,
                        page_context=page_context,
                        compile_context=compile_context,
                        in_prop_tree=in_prop_tree,
                        stateful_component=stateful_component,
                    ),
                )

            return enter_component

        return bind

    @staticmethod
    def _get_leave_hook_binder(
        plugin: CompilerPlugin,
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
                stateful_component: StatefulComponent | None,
            ) -> ComponentReplacement:
                return cast(
                    ComponentReplacement,
                    hook_impl(
                        comp,
                        children,
                        page_context=page_context,
                        compile_context=compile_context,
                        in_prop_tree=in_prop_tree,
                        stateful_component=stateful_component,
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
        stateful_component: StatefulComponent | None = None,
    ) -> BaseComponent:
        """Walk a component tree once while dispatching cached enter/leave hooks.

        Returns:
            The compiled component root for this subtree.
        """
        enter_hooks = tuple(
            hook_binder(page_context, compile_context)
            for hook_binder in self._enter_component_hook_binders
        )
        leave_hooks = tuple(
            (hook_binder(page_context, compile_context), stateful_only)
            for hook_binder, stateful_only in self._leave_component_hook_binders
        )

        return self._compile_component_tree(
            comp,
            enter_hooks=enter_hooks,
            leave_hooks=leave_hooks,
            in_prop_tree=in_prop_tree,
            stateful_component=stateful_component,
        )

    def _compile_component_tree(
        self,
        comp: BaseComponent,
        /,
        *,
        enter_hooks: tuple[CompiledEnterHook, ...],
        leave_hooks: tuple[tuple[CompiledLeaveHook, bool], ...],
        in_prop_tree: bool = False,
        stateful_component: StatefulComponent | None = None,
    ) -> BaseComponent:
        """Walk a component tree dispatching enter/leave hooks.

        Returns:
            The compiled component root for this subtree.
        """

        def visit_children(
            children: Sequence[BaseComponent],
            current_in_prop_tree: bool,
            current_stateful_component: StatefulComponent | None,
        ) -> tuple[BaseComponent, ...]:
            if not children:
                return ()

            updated_children: list[BaseComponent] | None = None
            for index, child in enumerate(children):
                compiled_child = visit(
                    child,
                    current_in_prop_tree,
                    current_stateful_component,
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
            current_stateful_component: StatefulComponent | None,
        ) -> BaseComponent:
            compiled_component = current_comp
            structural_children: tuple[BaseComponent, ...] | None = None

            for hook_impl in enter_hooks:
                replacement = hook_impl(
                    compiled_component,
                    current_in_prop_tree,
                    current_stateful_component,
                )
                if replacement is not None:
                    if isinstance(replacement, tuple):
                        compiled_component = cast(BaseComponent, replacement[0])
                        structural_children = cast(
                            tuple[BaseComponent, ...], replacement[1]
                        )
                    else:
                        compiled_component = replacement

            if isinstance(compiled_component, StatefulComponent):
                if not compiled_component.rendered_as_shared:
                    compiled_component.component = cast(
                        Component,
                        visit(
                            compiled_component.component,
                            current_in_prop_tree,
                            compiled_component,
                        ),
                    )
                compiled_children = tuple(compiled_component.children)
            else:
                if structural_children is None:
                    structural_children = tuple(compiled_component.children)
                compiled_children = visit_children(
                    structural_children,
                    current_in_prop_tree,
                    current_stateful_component,
                )
                if isinstance(compiled_component, Component):
                    for prop_component in compiled_component._get_components_in_props():
                        visit(
                            prop_component,
                            True,
                            current_stateful_component,
                        )

            is_stateful_component = isinstance(compiled_component, StatefulComponent)
            for hook_impl, stateful_only in leave_hooks:
                if stateful_only and not is_stateful_component:
                    continue
                replacement = hook_impl(
                    compiled_component,
                    compiled_children,
                    current_in_prop_tree,
                    current_stateful_component,
                )
                if replacement is not None:
                    if isinstance(replacement, tuple):
                        compiled_component = cast(BaseComponent, replacement[0])
                        new_children = cast(tuple[BaseComponent, ...], replacement[1])
                    else:
                        compiled_component = replacement
                        new_children = compiled_children
                    if new_children is not compiled_children:
                        compiled_children = visit_children(
                            new_children,
                            current_in_prop_tree,
                            current_stateful_component,
                        )

            compiled_component.children = list(compiled_children)
            return compiled_component

        return visit(
            comp,
            in_prop_tree,
            stateful_component,
        )


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
    stateful_components_path: str | None = None
    stateful_components_code: str = ""

    def compile(
        self,
        *,
        evaluate_progress: Callable[[], None] | None = None,
        render_progress: Callable[[], None] | None = None,
        apply_overlay: bool = False,
        **kwargs: Any,
    ) -> dict[str, PageContext]:
        """Compile all configured pages through the plugin pipeline.

        Args:
            evaluate_progress: Callback invoked after each page evaluation.
            render_progress: Callback invoked after each page render.
            apply_overlay: Whether to apply the app overlay during evaluation.
            kwargs: Additional compiler-specific context.

        Returns:
            The compiled page contexts keyed by route.
        """
        from reflex.compiler import compiler
        from reflex.state import all_base_state_classes
        from reflex.utils.exec import is_prod_mode

        self.ensure_context_attached()
        self.compiled_pages.clear()
        self.all_imports.clear()
        self.app_wrap_components.clear()
        self.stateful_routes.clear()
        self.stateful_components_path = compiler.utils.get_stateful_components_path()
        self.stateful_components_code = ""
        stateful_component_cache: dict[str, StatefulComponent] = {}

        overlay_component: Component | None = None
        if (
            apply_overlay
            and self.app is not None
            and self.app.overlay_component is not None
        ):
            overlay_component = self.app._generate_component(self.app.overlay_component)

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

            if overlay_component is not None and self.app is not None:
                if not isinstance(page_ctx.root_component, Component):
                    msg = (
                        f"Compiled page {page_ctx.route!r} root must be a Component "
                        "to apply the overlay."
                    )
                    raise TypeError(msg)
                page_ctx.root_component = self.app._add_overlay_to_component(
                    page_ctx.root_component,
                    overlay_component,
                )

            if isinstance(page_ctx.root_component, StatefulComponent):
                self.app_wrap_components.update(
                    page_ctx.root_component.component._get_all_app_wrap_components()
                )
            elif isinstance(page_ctx.root_component, Component):
                self.app_wrap_components.update(
                    page_ctx.root_component._get_all_app_wrap_components()
                )

            page_ctx.root_component = (
                StatefulComponent.compile_from(
                    page_ctx.root_component,
                    stateful_component_cache=stateful_component_cache,
                )
                or page_ctx.root_component
            )
            self.compiled_pages[page_ctx.route] = page_ctx

            if evaluate_progress is not None:
                evaluate_progress()

        page_components = [
            page_ctx.root_component for page_ctx in self.compiled_pages.values()
        ]
        stateful_imports: ParsedImportDict = {}
        if is_prod_mode():
            self.stateful_components_code, stateful_imports = (
                compiler._compile_stateful_components(page_components)
            )
            self.all_imports = merge_imports(self.all_imports, stateful_imports)
        else:
            self.stateful_components_code = ""

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
    "CompilerPlugin",
    "ComponentAndChildren",
    "PageContext",
    "PageDefinition",
]
