"""Compiler for the reflex apps."""
from __future__ import annotations

from typing import List, Set, Tuple, Type

from reflex import constants
from reflex.compiler import templates, utils
from reflex.components.component import Component, ComponentStyle, CustomComponent
from reflex.state import State
from reflex.utils import imports
from reflex.vars import ImportVar

# Imports to be included in every Reflex app.
DEFAULT_IMPORTS: imports.ImportDict = {
    "react": {
        ImportVar(tag="Fragment"),
        ImportVar(tag="useEffect"),
        ImportVar(tag="useRef"),
        ImportVar(tag="useState"),
    },
    "next/router": {ImportVar(tag="useRouter")},
    f"/{constants.STATE_PATH}": {
        ImportVar(tag="connect"),
        ImportVar(tag="processEvent"),
        ImportVar(tag="uploadFiles"),
        ImportVar(tag="E"),
        ImportVar(tag="isTrue"),
        ImportVar(tag="preventDefault"),
        ImportVar(tag="refs"),
        ImportVar(tag="getRefValue"),
        ImportVar(tag="getAllLocalStorageItems"),
    },
    "": {ImportVar(tag="focus-visible/dist/focus-visible")},
    "@chakra-ui/react": {
        ImportVar(tag=constants.USE_COLOR_MODE),
        ImportVar(tag="Box"),
        ImportVar(tag="Text"),
    },
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


def _compile_page(
    component: Component, state: Type[State], connect_error_component
) -> str:
    """Compile the component given the app state.

    Args:
        component: The component to compile.
        state: The app state.
        connect_error_component: The component to render on sever connection error.


    Returns:
        The compiled component.
    """
    # Merge the default imports with the app-specific imports.
    imports = utils.merge_imports(DEFAULT_IMPORTS, component.get_imports())
    utils.validate_imports(imports)
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
        err_comp=connect_error_component.render() if connect_error_component else None,
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


def _compile_tailwind(
    config: dict,
) -> str:
    """Compile the Tailwind config.

    Args:
        config: The Tailwind config.

    Returns:
        The compiled Tailwind config.
    """
    return templates.TAILWIND_CONFIG.render(
        **config,
    )


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


def compile_theme(style: ComponentStyle) -> Tuple[str, str]:
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


def compile_page(
    path: str,
    component: Component,
    state: Type[State],
    connect_error_component: Component,
) -> Tuple[str, str]:
    """Compile a single page.

    Args:
        path: The path to compile the page to.
        component: The component to compile.
        state: The app state.
        connect_error_component: The component to render on sever connection error.

    Returns:
        The path and code of the compiled page.
    """
    # Get the path for the output file.
    output_path = utils.get_page_path(path)

    # Add the style to the component.
    code = _compile_page(component, state, connect_error_component)
    return output_path, code


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


def compile_tailwind(
    config: dict,
):
    """Compile the Tailwind config.

    Args:
        config: The Tailwind config.

    Returns:
        The compiled Tailwind config.
    """
    # Get the path for the output file.
    output_path = constants.TAILWIND_CONFIG

    # Compile the config.
    code = _compile_tailwind(config)
    return output_path, code


def purge_web_pages_dir():
    """Empty out .web directory."""
    template_files = ["_app.js", "404.js"]
    utils.empty_dir(constants.WEB_PAGES_DIR, keep_files=template_files)
