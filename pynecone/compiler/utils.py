"""Common utility functions used in the compiler."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Dict, Set, Type

from pynecone import constants, utils
from pynecone.compiler import templates
from pynecone.components.base import (
    Body,
    DocumentHead,
    Head,
    Html,
    Link,
    Main,
    Script,
    Title,
)
from pynecone.components.component import ImportDict
from pynecone.state import State
from pynecone.style import Style

if TYPE_CHECKING:
    from pynecone.components.component import Component


# To re-export this function.
merge_imports = utils.merge_imports


def compile_import_statement(lib: str, fields: Set[str]) -> str:
    """Compile an import statement.

    Args:
        lib: The library to import from.
        fields: The set of fields to import from the library.

    Returns:
        The compiled import statement.
    """
    # Check for default imports.
    defaults = {
        field
        for field in fields
        if field.lower() == lib.lower().replace("-", "").replace("/", "")
    }
    assert len(defaults) < 2

    # Get the default import, and the specific imports.
    default = next(iter(defaults), "")
    rest = fields - defaults
    return templates.format_import(lib=lib, default=default, rest=rest)


def compile_imports(imports: ImportDict) -> str:
    """Compile an import dict.

    Args:
        imports: The import dict to compile.

    Returns:
        The compiled import dict.
    """
    return templates.join(
        [compile_import_statement(lib, fields) for lib, fields in imports.items()]
    )


def compile_constant_declaration(name: str, value: str) -> str:
    """Compile a constant declaration.

    Args:
        name: The name of the constant.
        value: The value of the constant.

    Returns:
        The compiled constant declaration.
    """
    return templates.CONST(name=name, value=json.dumps(value))


def compile_constants() -> str:
    """Compile all the necessary constants.

    Returns:
        A string of all the compiled constants.
    """
    endpoint = constants.Endpoint.EVENT
    return templates.join(
        [compile_constant_declaration(name=endpoint.name, value=endpoint.get_url())]
    )


import plotly.graph_objects as go


def compile_state(state: Type[State]) -> str:
    """Compile the state of the app.

    Args:
        state: The app state object.

    Returns:
        A string of the compiled state.
    """
    initial_state = state().dict()
    initial_state.update(
        {
            "events": [{"name": utils.get_hydrate_event(state)}],
        }
    )
    initial_state = utils.format_state(initial_state)
    synced_state = templates.format_state(
        state=state.get_name(), initial_state=json.dumps(initial_state)
    )
    initial_result = {
        constants.STATE: None,
        constants.EVENTS: [],
        constants.PROCESSING: False,
    }
    result = templates.format_state(
        state="result",
        initial_state=json.dumps(initial_result),
    )
    router = templates.ROUTER
    return templates.join([synced_state, result, router])


def compile_events(state: Type[State]) -> str:
    """Compile all the events for a given component.

    Args:
        state: The state class for the component.

    Returns:
        A string of the compiled events for the component.
    """
    state_name = state.get_name()
    state_setter = templates.format_state_setter(state_name)
    return templates.EVENT_FN(state=state_name, set_state=state_setter)


def compile_effects(state: Type[State]) -> str:
    """Compile all the effects for a given component.

    Args:
        state: The state class for the component.

    Returns:
        A string of the compiled effects for the component.
    """
    state_name = state.get_name()
    set_state = templates.format_state_setter(state_name)
    return templates.USE_EFFECT(state=state_name, set_state=set_state)


def compile_render(component: Component) -> str:
    """Compile the component's render method.

    Args:
        component: The component to compile the render method for.

    Returns:
        A string of the compiled render method.
    """
    return component.render()


def create_document_root(stylesheets) -> Component:
    """Create the document root.

    Args:
        stylesheets: The stylesheets to include in the document root.

    Returns:
        The document root.
    """
    sheets = [Link.create(rel="stylesheet", href=href) for href in stylesheets]
    return Html.create(
        DocumentHead.create(*sheets),
        Body.create(
            Main.create(),
            Script.create(),
        ),
    )


def create_theme(style: Style) -> Dict:
    """Create the base style for the app.

    Args:
        style: The style dict for the app.

    Returns:
        The base style for the app.
    """
    return {
        "styles": {
            "global": Style({k: v for k, v in style.items() if not isinstance(k, type)})
        },
    }


def add_title(page: Component, title: str) -> Component:
    """Add a title to a page.

    Args:
        page: The component for the page.
        title: The title to add.

    Returns:
        The component with the title added.
    """
    page.children.append(Head.create(Title.create(title)))
    return page
