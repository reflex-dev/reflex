"""Compiler for the pynecone apps."""
from __future__ import annotations

import json
from functools import wraps
from typing import TYPE_CHECKING, Callable, List, Tuple, Type

from pynecone import constants
from pynecone.compiler import templates, utils
from pynecone.components.component import Component, ImportDict
from pynecone.state import State

if TYPE_CHECKING:
    from pynecone.components.component import ComponentStyle

# Imports to be included in every Pynecone app.
DEFAULT_IMPORTS: ImportDict = {
    "react": {"useEffect", "useRef", "useState"},
    "next/router": {"useRouter"},
    f"/{constants.STATE_PATH}": {"connect", "updateState", "E"},
    "": {"focus-visible/dist/focus-visible"},
}


def _compile_document_root(root: Component) -> str:
    """Compile the document root.

    Args:
        root: The document root to compile.

    Returns:
        The compiled document root.
    """
    return templates.DOCUMENT_ROOT(
        imports=utils.compile_imports(root.get_imports()),
        document=root.render(),
    )


def _compile_theme(theme: dict) -> str:
    """Compile the theme.

    Args:
        theme: The theme to compile.

    Returns:
        The compiled theme.
    """
    return templates.THEME(theme=json.dumps(theme))


def _compile_page(component: Component, state: Type[State]) -> str:
    """Compile the component given the app state.

    Args:
        component: The component to compile.
        state: The app state.

    Returns:
        The compiled component.
    """
    # Merge the default imports with the app-specific imports.
    imports = utils.merge_imports(DEFAULT_IMPORTS, component.get_imports())

    # Compile the code to render the component.
    return templates.PAGE(
        imports=utils.compile_imports(imports),
        custom_code=templates.join(component.get_custom_code()),
        constants=utils.compile_constants(),
        state=utils.compile_state(state),
        events=utils.compile_events(state),
        effects=utils.compile_effects(state),
        render=component.render(),
    )


def write_fn(fn: Callable[..., Tuple[str, str]]):
    """Decorator to write the output of a function to a file."""

    @wraps(fn)
    def wrapper(*args, write: bool = True) -> Tuple[str, str]:
        """Write the output of the function to a file."""
        path, code = fn(*args)
        if write:
            utils.write_page(path, code)
        return path, code

    return wrapper


@write_fn
def compile_document_root(stylesheets: List[str]) -> Tuple[str, str]:
    """Compile the document root.

    Args:
        document_root: The document root to compile.

    Returns:
        The path and code of the compiled document root.
    """
    # Get the path for the output file.
    output_path = utils.get_page_path(constants.DOCUMENT_ROOT)

    # Create the document root.
    document_root = utils.create_document_root(stylesheets)

    # Compile the document root.
    code = _compile_document_root(document_root)
    return output_path, code


@write_fn
def compile_theme(style: ComponentStyle) -> Tuple[str, str]:
    """Compile the theme.

    Args:
        theme: The theme to compile.

    Returns:
        The path and code of the compiled theme.
    """
    output_path = utils.get_theme_path()

    # Create the theme.
    theme = utils.create_theme(style)

    # Compile the theme.
    code = _compile_theme(theme)
    return output_path, code


@write_fn
def compile_page(
    path: str, component: Component, state: Type[State]
) -> Tuple[str, str]:
    """Compile a single page.

    Args:
        path: The path to compile the page to.
        component: The component to compile.
        state: The app state.

    Returns:
        The path and code of the compiled page.
    """
    # Get the path for the output file.
    output_path = utils.get_page_path(path)

    # Add the style to the component.
    code = _compile_page(
        component=component,
        state=state,
    )
    return output_path, code
