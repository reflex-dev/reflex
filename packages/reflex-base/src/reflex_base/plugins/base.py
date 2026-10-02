"""Base class for all plugins."""

from collections.abc import Callable, Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, ParamSpec, Protocol, TypedDict, TypeVar

from typing_extensions import Unpack

from reflex_base.utils.exceptions import ConfigError


class HookOrder(str, Enum):
    """Dispatch bucket for a compiler ``enter_component`` / ``leave_component`` hook."""

    PRE = "pre"
    NORMAL = "normal"
    POST = "post"


if TYPE_CHECKING:
    from reflex.app import App, UnevaluatedPage
    from reflex_base.components.component import BaseComponent, Component
    from reflex_base.event import EventType
    from reflex_base.plugins.compiler import ComponentAndChildren, PageContext
    from reflex_base.vars.base import Var


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


class AddPageProtocol(Protocol):
    """Protocol for staging a page contribution during route registration.

    Mirrors the keyword surface of ``App.add_page``; page options are
    keyword-only. Concrete ``App`` subclasses may accept extra keywords, which
    are forwarded to their ``_prepare_page`` extension.
    """

    def __call__(
        self,
        component: "Component | Callable[[], Any] | None" = None,
        route: str | None = None,
        *,
        title: "str | Var | None" = None,
        description: "str | Var | None" = None,
        image: str = ...,
        on_load: "EventType[()] | None" = None,
        meta: Sequence["Mapping[str, Any] | Component"] = ...,
        context: dict[str, Any] | None = None,
        **extra_page_args: Any,
    ) -> None:
        """Stage a page contribution owned by the calling plugin.

        Args:
            component: The component or component callable to display.
            route: The route to display the component at.
            title: The title of the page.
            description: The description of the page.
            image: The image to display on the page.
            on_load: The event handler(s) called each time the page loads.
            meta: The metadata of the page.
            context: Values passed to the page for custom page-specific logic.
            extra_page_args: Keyword arguments added by concrete ``App``
                subclasses that extend page registration.
        """


class RegisterRouteContext(CommonContext):
    """Context for the ``register_route`` hook."""

    app_type: type["App"]
    add_page: AddPageProtocol
    has_app_page: Callable[[str], bool]


class PostCompileContext(CommonContext):
    """Context for post-compile hooks."""

    app: "App"


class PostBuildContext(CommonContext):
    """Context for post-build hooks."""

    static_dir: Path


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

    def register_route(self, **context: Unpack[RegisterRouteContext]) -> None:
        """Contribute pages before the app's first compilation.

        The hook runs once per app, after app-defined pages are collected and
        before any page is evaluated. Calls to ``context["add_page"]`` are
        prepared without mutating app route state, then committed after every
        plugin hook succeeds. ``context["app_type"]`` supports concrete-app
        compatibility checks without exposing the mutable app. Use
        ``context["has_app_page"]`` to let an app-defined page override an
        optional plugin page; it intentionally ignores other plugins so
        plugin-versus-plugin route conflicts cannot be hidden by ordering.

        Args:
            context: The route registration context.
        """

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

    def post_build(self, **context: Unpack[PostBuildContext]) -> None:
        """Called after the production frontend build finishes.

        Fires after ``npm run export`` so plugins can inspect or post-process
        the Vite output (``context["static_dir"]``).

        Args:
            context: The context for the plugin.
        """

    def provides_entry_client(self) -> bool:
        """Return whether this plugin emits its own ``entry.client.js``.

        The framework calls this during ``setup_frontend`` to decide whether
        to skip its default ``entry.client.js`` write. Plugins that register
        a save task for the same path should return ``True`` so the framework
        write doesn't race with (or overwrite) theirs.

        Returns:
            ``True`` if the plugin owns ``entry.client.js`` for this build.
        """
        return False

    def update_env_json(
        self, **context: Unpack[CommonContext]
    ) -> dict[str, Any] | None:
        """Return entries to merge into ``.web/env.json``.

        The framework merges each plugin's contribution on top of the base
        ``env.json`` it writes during ``setup_frontend``. Later plugins
        override earlier ones. Return ``None`` (the default) to contribute
        nothing.

        Args:
            context: The context for the plugin.

        Returns:
            A mapping of env entries to add or override, or ``None``.
        """
        return None

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


_PluginT = TypeVar("_PluginT", bound=Plugin)


def get_plugin(plugin_cls: type[_PluginT]) -> _PluginT | None:
    """Return the configured plugin instance of the given type, if any.

    Args:
        plugin_cls: The plugin type (or base type) to look up.

    Returns:
        The configured plugin that is an instance of ``plugin_cls``, or
        ``None`` when no such plugin is configured.

    Raises:
        ConfigError: When more than one configured plugin matches — behavior
            must not silently depend on the configuration order.
    """
    # Inline import: reflex_base.config imports this module for the Plugin type.
    from reflex_base.config import get_config

    matches = (p for p in get_config().plugins if isinstance(p, plugin_cls))
    match = next(matches, None)
    if next(matches, None) is not None:
        msg = (
            f"Multiple {plugin_cls.__name__} instances are configured, but "
            "get_plugin() requires an unambiguous match. Request a more specific "
            "type or remove duplicate entries from the rxconfig plugins list."
        )
        raise ConfigError(msg)
    return match
