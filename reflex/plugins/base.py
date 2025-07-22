"""Base class for all plugins."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, ParamSpec, Protocol, TypedDict

from typing_extensions import Unpack

if TYPE_CHECKING:
    from reflex.app import UnevaluatedPage


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
    unevaluated_pages: Sequence["UnevaluatedPage"]


class Plugin:
    """Base class for all plugins."""

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

    def __repr__(self):
        """Return a string representation of the plugin.

        Returns:
            A string representation of the plugin.
        """
        return f"{self.__class__.__name__}()"
