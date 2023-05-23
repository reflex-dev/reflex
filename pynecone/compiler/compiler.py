"""Compiler for the pynecone apps."""
from __future__ import annotations

from functools import wraps
from typing import Callable, List, Set, Tuple, Type

from pynecone import constants
from pynecone.compiler import templates, utils
from pynecone.components.component import Component, CustomComponent
from pynecone.state import State
from pynecone.style import Style
from pynecone.utils import imports
from pynecone.vars import ImportVar

# Imports to be included in every Pynecone app.
DEFAULT_IMPORTS: imports.ImportDict = {
    "react": {
        ImportVar(tag="useEffect"),
        ImportVar(tag="useRef"),
        ImportVar(tag="useState"),
    },
    "next/router": {ImportVar(tag="useRouter")},
    f"/{constants.STATE_PATH}": {
        ImportVar(tag="connect"),
        ImportVar(tag="updateState"),
        ImportVar(tag="uploadFiles"),
        ImportVar(tag="E"),
        ImportVar(tag="isTrue"),
        ImportVar(tag="preventDefault"),
        ImportVar(tag="refs"),
    },
    "": {ImportVar(tag="focus-visible/dist/focus-visible")},
    "@chakra-ui/react": {ImportVar(tag=constants.USE_COLOR_MODE)},
}


def _compile_document_root(root: Component) -> str:
    """Compile the document root.

    Args:
        root: The document root to compile.

    Returns:
        The compiled document root.
    """
    return templates.DOCUMENT_ROOT.render(
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
    return templates.THEME.render(theme=theme)


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
    imports = utils.compile_imports(imports)

    # Compile the code to render the component.
    return templates.PAGE.render(
        imports=imports,
        custom_codes=component.get_custom_code(),
        initial_state=utils.compile_state(state),
        state_name=state.get_name(),
        hooks=component.get_hooks(),
        render=component.render(),
        transports=constants.Transports.POLLING_WEBSOCKET.get_transports(),
    )


def _compile_components(components: Set[CustomComponent]) -> str:
    """Compile the components.

    Args:
        components: The components to compile.

    Returns:
        The compiled components.
    """
    imports = {
        "react": {ImportVar(tag="memo")},
        f"/{constants.STATE_PATH}": {ImportVar(tag="E"), ImportVar(tag="isTrue")},
    }
    component_renders = []

    # Compile each component.
    for component in components:
        component_render, component_imports = utils.compile_custom_component(component)
        component_renders.append(component_render)
        imports = utils.merge_imports(imports, component_imports)

    # Compile the components page.
    return templates.COMPONENTS.render(
        imports=utils.compile_imports(imports),
        components=component_renders,
    )


def write_output(fn: Callable[..., Tuple[str, str]]):
    """Write the output of the function to a file.

    Args:
        fn: The function to decorate.

    Returns:
        The decorated function.
    """

    @wraps(fn)
    def wrapper(*args, write: bool = True) -> Tuple[str, str]:
        """Write the output of the function to a file.

        Args:
            *args: The arguments to pass to the function.
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
        stylesheets: The stylesheets to include in the document root.

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
def compile_theme(style: Style) -> Tuple[str, str]:
    """Compile the theme.

    Args:
        style: The style to compile.

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


def purge_web_pages_dir():
    """Empty out .web directory."""
    template_files = ["_app.js", "404.js"]
    utils.empty_dir(constants.WEB_PAGES_DIR, keep_files=template_files)
