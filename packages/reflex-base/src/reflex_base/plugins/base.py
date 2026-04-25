"""Base class for all plugins."""

from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, ParamSpec, Protocol, TypedDict

from typing_extensions import Unpack


class HookOrder(str, Enum):
    """Dispatch bucket for a compiler ``enter_component`` / ``leave_component`` hook."""

    PRE = "pre"
    NORMAL = "normal"
    POST = "post"


if TYPE_CHECKING:
    from reflex.app import App, UnevaluatedPage
    from reflex_base.components.component import BaseComponent
    from reflex_base.plugins.compiler import ComponentAndChildren, PageContext


class CommonContext(TypedDict):
    """Common context for all plugins."""


P = ParamSpec("P")


class AddTaskProtocol(Protocol):
    """Protocol for adding a task to the pre-compile context."""

    def __call__(
        self,
        task: Callable[P, list[tuple[str, str]] | tuple[str, str] | None],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        """Add a task to the pre-compile context.

        Args:
            task: The task to add.
            args: The arguments to pass to the task
            kwargs: The keyword arguments to pass to the task
        """


class PreCompileContext(CommonContext):
    """Context for pre-compile hooks."""

    add_save_task: AddTaskProtocol
    add_modify_task: Callable[[str, Callable[[str], str]], None]
    radix_themes_plugin: Any
    unevaluated_pages: Sequence["UnevaluatedPage"]


class PostCompileContext(CommonContext):
    """Context for post-compile hooks."""

    app: "App"


class Plugin:
    """Base class for all plugins."""

    # Dispatch position for ``enter_component`` and ``leave_component`` hooks.
    # Plugins run in ``PRE`` → ``NORMAL`` → ``POST`` order. Within a bucket,
    # enter hooks fire in plugin-chain order while leave hooks fire in
    # reverse plugin-chain order (mirroring an enter/leave stack).
    _compiler_enter_component_order: ClassVar[HookOrder] = HookOrder.NORMAL
    _compiler_leave_component_order: ClassVar[HookOrder] = HookOrder.NORMAL

    def get_frontend_development_dependencies(
        self, **context: Unpack[CommonContext]
    ) -> list[str] | set[str] | tuple[str, ...]:
        """Get the NPM packages required by the plugin for development.

        Args:
            context: The context for the plugin.

        Returns:
            A list of packages required by the plugin for development.
        """
        return []

    def get_frontend_dependencies(
        self, **context: Unpack[CommonContext]
    ) -> list[str] | set[str] | tuple[str, ...]:
        """Get the NPM packages required by the plugin.

        Args:
            context: The context for the plugin.

        Returns:
            A list of packages required by the plugin.
        """
        return []

    def get_static_assets(
        self, **context: Unpack[CommonContext]
    ) -> Sequence[tuple[Path, str | bytes]]:
        """Get the static assets required by the plugin.

        Args:
            context: The context for the plugin.

        Returns:
            A list of static assets required by the plugin.
        """
        return []

    def get_stylesheet_paths(self, **context: Unpack[CommonContext]) -> Sequence[str]:
        """Get the paths to the stylesheets required by the plugin relative to the styles directory.

        Args:
            context: The context for the plugin.

        Returns:
            A list of paths to the stylesheets required by the plugin.
        """
        return []

    def pre_compile(self, **context: Unpack[PreCompileContext]) -> None:
        """Called before the compilation of the plugin.

        Args:
            context: The context for the plugin.
        """

    def post_compile(self, **context: Unpack[PostCompileContext]) -> None:
        """Called after the compilation of the plugin.

        Args:
            context: The context for the plugin.
        """

    def eval_page(
        self,
        page_fn: Any,
        /,
        **kwargs: Any,
    ) -> "PageContext | None":
        """Evaluate a page-like object into a page context.

        Args:
            page_fn: The page-like object to evaluate.
            kwargs: Additional compiler-specific context.

        Returns:
            A page context when the plugin can evaluate the page, otherwise ``None``.
        """
        return None

    def compile_page(
        self,
        page_ctx: "PageContext",
        /,
        **kwargs: Any,
    ) -> None:
        """Finalize a page context after its component tree has been traversed."""
        return

    def enter_component(
        self,
        comp: "BaseComponent",
        /,
        *,
        page_context: "PageContext",
        compile_context: Any,
        in_prop_tree: bool = False,
    ) -> "BaseComponent | ComponentAndChildren | None":
        """Inspect or transform a component before visiting its descendants.

        Args:
            comp: The component being compiled.
            page_context: The active page compilation state.
            compile_context: The active compile-run state.
            in_prop_tree: Whether the component is being visited through a prop subtree.

        Returns:
            An optional replacement component and/or structural children.
        """
        return None

    def leave_component(
        self,
        comp: "BaseComponent",
        children: tuple["BaseComponent", ...],
        /,
        *,
        page_context: "PageContext",
        compile_context: Any,
        in_prop_tree: bool = False,
    ) -> "BaseComponent | ComponentAndChildren | None":
        """Inspect or transform a component after visiting its descendants.

        Args:
            comp: The component being compiled.
            children: The compiled structural children for the component.
            page_context: The active page compilation state.
            compile_context: The active compile-run state.
            in_prop_tree: Whether the component is being visited through a prop subtree.

        Returns:
            An optional replacement component and/or structural children.
        """
        return None

    def __repr__(self):
        """Return a string representation of the plugin.

        Returns:
            A string representation of the plugin.
        """
        return f"{self.__class__.__name__}()"
