"""Compiler for the pynecone apps."""

import json
from typing import Type

from pynecone import constants
from pynecone.compiler import templates, utils
from pynecone.components.component import Component, ImportDict
from pynecone.state import State

# Imports to be included in every Pynecone app.
DEFAULT_IMPORTS: ImportDict = {
    "react": {"useEffect", "useState"},
    "next/router": {"useRouter"},
    f"/{constants.STATE_PATH}": {"updateState", "E"},
    "": {"focus-visible/dist/focus-visible"},
}


def compile_document_root(root: Component) -> str:
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


def compile_theme(theme: dict) -> str:
    """Compile the theme.

    Args:
        theme: The theme to compile.

    Returns:
        The compiled theme.
    """
    return templates.THEME(theme=json.dumps(theme))


def compile_component(component: Component, state: Type[State]) -> str:
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
    return templates.COMPONENT(
        imports=utils.compile_imports(imports),
        custom_code=component.get_custom_code(),
        constants=utils.compile_constants(),
        state=utils.compile_state(state),
        events=utils.compile_events(state),
        effects=utils.compile_effects(state),
        render=component.render(),
    )
