"""Compiler for the reflex apps."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Type

from reflex import constants
from reflex.compiler import templates, utils
from reflex.components.component import Component, ComponentStyle, CustomComponent
from reflex.config import get_config
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
        ImportVar(tag="useContext"),
    },
    "next/router": {ImportVar(tag="useRouter")},
    f"/{constants.Dirs.STATE_PATH}": {
        ImportVar(tag="uploadFiles"),
        ImportVar(tag="Event"),
        ImportVar(tag="isTrue"),
        ImportVar(tag="spreadArraysOrObjects"),
        ImportVar(tag="preventDefault"),
        ImportVar(tag="refs"),
        ImportVar(tag="getRefValue"),
        ImportVar(tag="getRefValues"),
        ImportVar(tag="getAllLocalStorageItems"),
        ImportVar(tag="useEventLoop"),
    },
    "/utils/context.js": {
        ImportVar(tag="EventLoopContext"),
        ImportVar(tag="initialEvents"),
        ImportVar(tag="StateContext"),
    },
    "": {ImportVar(tag="focus-visible/dist/focus-visible", install=False)},
    "@chakra-ui/react": {
        ImportVar(tag=constants.ColorMode.USE),
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


def _compile_contexts(state: Type[State]) -> str:
    """Compile the initial state and contexts.

    Args:
        state: The app state.

    Returns:
        The compiled context file.
    """
    return templates.CONTEXT.render(
        initial_state=utils.compile_state(state),
        state_name=state.get_name(),
        client_storage=utils.compile_client_storage(state),
    )


def _compile_page(
    component: Component,
    state: Type[State],
) -> str:
    """Compile the component given the app state.

    Args:
        component: The component to compile.
        state: The app state.

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
        dynamic_imports=component.get_dynamic_imports(),
        custom_codes=component.get_custom_code(),
        state_name=state.get_name(),
        hooks=component.get_hooks(),
        render=component.render(),
    )


def compile_root_stylesheet(stylesheets: list[str]) -> tuple[str, str]:
    """Compile the root stylesheet.

    Args:
        stylesheets: The stylesheets to include in the root stylesheet.

    Returns:
        The path and code of the compiled root stylesheet.
    """
    output_path = utils.get_root_stylesheet_path()

    code = _compile_root_stylesheet(stylesheets)

    return output_path, code


def _compile_root_stylesheet(stylesheets: list[str]) -> str:
    """Compile the root stylesheet.

    Args:
        stylesheets: The stylesheets to include in the root stylesheet.

    Returns:
        The compiled root stylesheet.

    Raises:
        FileNotFoundError: If a specified stylesheet in assets directory does not exist.
    """
    # Add tailwind css if enabled.
    sheets = (
        [constants.Tailwind.ROOT_STYLE_PATH]
        if get_config().tailwind is not None
        else []
    )
    for stylesheet in stylesheets:
        if not utils.is_valid_url(stylesheet):
            # check if stylesheet provided exists.
            stylesheet_full_path = (
                Path.cwd() / constants.Dirs.APP_ASSETS / stylesheet.strip("/")
            )
            if not os.path.exists(stylesheet_full_path):
                raise FileNotFoundError(
                    f"The stylesheet file {stylesheet_full_path} does not exist."
                )
            stylesheet = f"@/{stylesheet.strip('/')}"
        sheets.append(stylesheet) if stylesheet not in sheets else None
    return templates.STYLE.render(stylesheets=sheets)


def _compile_component(component: Component) -> str:
    """Compile a single component.

    Args:
        component: The component to compile.

    Returns:
        The compiled component.
    """
    return templates.COMPONENT.render(component=component)


def _compile_components(components: set[CustomComponent]) -> str:
    """Compile the components.

    Args:
        components: The components to compile.

    Returns:
        The compiled components.
    """
    imports = {
        "react": {ImportVar(tag="memo")},
        f"/{constants.Dirs.STATE_PATH}": {ImportVar(tag="E"), ImportVar(tag="isTrue")},
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


def compile_document_root(head_components: list[Component]) -> tuple[str, str]:
    """Compile the document root.

    Args:
        head_components: The components to include in the head.

    Returns:
        The path and code of the compiled document root.
    """
    # Get the path for the output file.
    output_path = utils.get_page_path(constants.PageNames.DOCUMENT_ROOT)

    # Create the document root.
    document_root = utils.create_document_root(head_components)

    # Compile the document root.
    code = _compile_document_root(document_root)
    return output_path, code


def compile_theme(style: ComponentStyle) -> tuple[str, str]:
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


def compile_contexts(state: Type[State]) -> tuple[str, str]:
    """Compile the initial state / context.

    Args:
        state: The app state.

    Returns:
        The path and code of the compiled context.
    """
    # Get the path for the output file.
    output_path = utils.get_context_path()

    return output_path, _compile_contexts(state)


def compile_page(
    path: str, component: Component, state: Type[State]
) -> tuple[str, str]:
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


def compile_components(components: set[CustomComponent]):
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
    output_path = constants.Tailwind.CONFIG

    # Compile the config.
    code = _compile_tailwind(config)
    return output_path, code


def purge_web_pages_dir():
    """Empty out .web directory."""
    utils.empty_dir(constants.Dirs.WEB_PAGES, keep_files=["_app.js"])
