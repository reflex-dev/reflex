"""Compiler for the pynecone apps."""
from __future__ import annotations

import inspect
import json
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, List, Set, Tuple, Type

from pynecone import constants
from pynecone.compiler import templates, utils
from pynecone.components.component import Component, CustomComponent, ImportDict
from pynecone.state import State
from pynecone.var import BaseVar

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


def _compile_components(components: Set[CustomComponent]) -> str:
    """Compile the components.

    Args:
        components: The components to compile.

    Returns:
        The compiled components.
    """
    # Get the imports for the components.
    imports = {"react": {"memo"}}
    component_defs = []

    for component in components:
        args = []
        argspec = inspect.getfullargspec(component.component_fn)
        annoations = argspec.annotations
        for arg in argspec.args:
            name = utils.utils.to_camel_case(arg)
            type_ = annoations.get(arg, Any)
            args.append(BaseVar(name=name, type_=type_, is_local=True))
        render = component.component_fn(*args)
        imports = utils.merge_imports(imports, render.get_imports())
        props = ", ".join([arg.name for arg in args])
        component = templates.COMPONENT(
            name=component.tag,
            props=props,
            render=render,
        )
        component_defs.append(component)
    return templates.COMPONENTS(
        imports=utils.compile_imports(imports),
        components=templates.join(component_defs),
    )


def write_output(fn: Callable[..., Tuple[str, str]]):
    """Decorator to write the output of a function to a file.

    Args:
        fn: The function to decorate.

    Returns:
        The decorated function.
    """

    @wraps(fn)
    def wrapper(*args, write: bool = True) -> Tuple[str, str]:
        """Write the output of the function to a file.

        Args:
            write: Whether to write the output to a file.

        Returns:
            The path and code of the output.
        """
        path, code = fn(*args)
        if write:
            utils.write_page(path, code)
        return path, code

    return wrapper


@write_output
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


@write_output
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


@write_output
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
    code = _compile_page(component, state)
    return output_path, code


@write_output
def compile_components(components: Set[CustomComponent]):
    """Compile the custom components.

    Args:
        components: The custom components to compile.

    Returns:
        The path and code of the compiled components.
    """
    # Get the path for the output file.
    output_path = utils.get_components_path()

    # Compile the components.
    code = _compile_components(components)
    return output_path, code
