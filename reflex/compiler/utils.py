"""Common utility functions used in the compiler."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type, Union
from urllib.parse import urlparse

from reflex.utils.prerequisites import get_web_dir
from reflex.vars.base import Var

try:
    from pydantic.v1.fields import ModelField
except ModuleNotFoundError:
    from pydantic.fields import ModelField  # type: ignore

from reflex import constants
from reflex.components.base import (
    Body,
    Description,
    DocumentHead,
    Head,
    Html,
    Image,
    Main,
    Meta,
    NextScript,
    Title,
)
from reflex.components.component import Component, ComponentStyle, CustomComponent
from reflex.istate.storage import Cookie, LocalStorage, SessionStorage
from reflex.state import BaseState
from reflex.style import Style
from reflex.utils import console, format, imports, path_ops
from reflex.utils.imports import ImportVar, ParsedImportDict

# To re-export this function.
merge_imports = imports.merge_imports


def compile_import_statement(fields: list[ImportVar]) -> tuple[str, list[str]]:
    """Compile an import statement.

    Args:
        fields: The set of fields to import from the library.

    Raises:
        ValueError: If there is more than one default import.

    Returns:
        The libraries for default and rest.
        default: default library. When install "import def from library".
        rest: rest of libraries. When install "import {rest1, rest2} from library"
    """
    # ignore the ImportVar fields with render=False during compilation
    fields_set = {field for field in fields if field.render}

    # Check for default imports.
    defaults = {field for field in fields_set if field.is_default}
    if len(defaults) >= 2:
        raise ValueError("Only one default import is allowed.")

    # Get the default import, and the specific imports.
    default = next(iter({field.name for field in defaults}), "")
    rest = {field.name for field in fields_set - defaults}

    return default, list(rest)


def validate_imports(import_dict: ParsedImportDict):
    """Verify that the same Tag is not used in multiple import.

    Args:
        import_dict: The dict of imports to validate

    Raises:
        ValueError: if a conflict on "tag/alias" is detected for an import.
    """
    used_tags = {}
    for lib, _imports in import_dict.items():
        for _import in _imports:
            import_name = (
                f"{_import.tag}/{_import.alias}" if _import.alias else _import.tag
            )
            if import_name in used_tags:
                already_imported = used_tags[import_name]
                if (already_imported[0] == "$" and already_imported[1:] == lib) or (
                    lib[0] == "$" and lib[1:] == already_imported
                ):
                    used_tags[import_name] = lib if lib[0] == "$" else already_imported
                    continue
                raise ValueError(
                    f"Can not compile, the tag {import_name} is used multiple time from {lib} and {used_tags[import_name]}"
                )
            if import_name is not None:
                used_tags[import_name] = lib


def compile_imports(import_dict: ParsedImportDict) -> list[dict]:
    """Compile an import dict.

    Args:
        import_dict: The import dict to compile.

    Raises:
        ValueError: If an import in the dict is invalid.

    Returns:
        The list of import dict.
    """
    collapsed_import_dict: ParsedImportDict = imports.collapse_imports(import_dict)
    validate_imports(collapsed_import_dict)
    import_dicts = []
    for lib, fields in collapsed_import_dict.items():
        default, rest = compile_import_statement(fields)

        # prevent lib from being rendered on the page if all imports are non rendered kind
        if not any(f.render for f in fields):  # type: ignore
            continue

        if not lib:
            if default:
                raise ValueError("No default field allowed for empty library.")
            if rest is None or len(rest) == 0:
                raise ValueError("No fields to import.")
            import_dicts.extend(get_import_dict(module) for module in sorted(rest))
            continue

        # remove the version before rendering the package imports
        lib = format.format_library_name(lib)

        import_dicts.append(get_import_dict(lib, default, rest))
    return import_dicts


def get_import_dict(lib: str, default: str = "", rest: list[str] | None = None) -> dict:
    """Get dictionary for import template.

    Args:
        lib: The importing react library.
        default: The default module to import.
        rest: The rest module to import.

    Returns:
        A dictionary for import template.
    """
    return {
        "lib": lib,
        "default": default,
        "rest": rest if rest else [],
    }


def compile_state(state: Type[BaseState]) -> dict:
    """Compile the state of the app.

    Args:
        state: The app state object.

    Returns:
        A dictionary of the compiled state.
    """
    try:
        initial_state = state(_reflex_internal_init=True).dict(initial=True)
    except Exception as e:
        console.warn(
            f"Failed to compile initial state with computed vars, excluding them: {e}"
        )
        initial_state = state(_reflex_internal_init=True).dict(
            initial=True, include_computed=False
        )
    return initial_state


def _compile_client_storage_field(
    field: ModelField,
) -> tuple[
    Type[Cookie] | Type[LocalStorage] | Type[SessionStorage] | None,
    dict[str, Any] | None,
]:
    """Compile the given cookie, local_storage or session_storage field.

    Args:
        field: The possible cookie field to compile.

    Returns:
        A dictionary of the compiled cookie or None if the field is not cookie-like.
    """
    for field_type in (Cookie, LocalStorage, SessionStorage):
        if isinstance(field.default, field_type):
            cs_obj = field.default
        elif isinstance(field.type_, type) and issubclass(field.type_, field_type):
            cs_obj = field.type_()
        else:
            continue
        return field_type, cs_obj.options()
    return None, None


def _compile_client_storage_recursive(
    state: Type[BaseState],
) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    """Compile the client-side storage for the given state recursively.

    Args:
        state: The app state object.

    Returns:
        A tuple of the compiled client-side storage info:
            (
                cookies: dict[str, dict],
                local_storage: dict[str, dict[str, str]]
                session_storage: dict[str, dict[str, str]]
            ).
    """
    cookies = {}
    local_storage = {}
    session_storage = {}
    state_name = state.get_full_name()
    for name, field in state.__fields__.items():
        if name in state.inherited_vars:
            # only include vars defined in this state
            continue
        state_key = f"{state_name}.{name}"
        field_type, options = _compile_client_storage_field(field)
        if field_type is Cookie:
            cookies[state_key] = options
        elif field_type is LocalStorage:
            local_storage[state_key] = options
        elif field_type is SessionStorage:
            session_storage[state_key] = options
        else:
            continue
    for substate in state.get_substates():
        (
            substate_cookies,
            substate_local_storage,
            substate_session_storage,
        ) = _compile_client_storage_recursive(substate)
        cookies.update(substate_cookies)
        local_storage.update(substate_local_storage)
        session_storage.update(substate_session_storage)
    return cookies, local_storage, session_storage


def compile_client_storage(state: Type[BaseState]) -> dict[str, dict]:
    """Compile the client-side storage for the given state.

    Args:
        state: The app state object.

    Returns:
        A dictionary of the compiled client-side storage info.
    """
    cookies, local_storage, session_storage = _compile_client_storage_recursive(state)
    return {
        constants.COOKIES: cookies,
        constants.LOCAL_STORAGE: local_storage,
        constants.SESSION_STORAGE: session_storage,
    }


def compile_custom_component(
    component: CustomComponent,
) -> tuple[dict, ParsedImportDict]:
    """Compile a custom component.

    Args:
        component: The custom component to compile.

    Returns:
        A tuple of the compiled component and the imports required by the component.
    """
    # Render the component.
    render = component.get_component(component)

    # Get the imports.
    imports: ParsedImportDict = {
        lib: fields
        for lib, fields in render._get_all_imports().items()
        if lib != component.library
    }

    # Concatenate the props.
    props = [prop._js_expr for prop in component.get_prop_vars()]

    # Compile the component.
    return (
        {
            "name": component.tag,
            "props": props,
            "render": render.render(),
            "hooks": {**render._get_all_hooks_internal(), **render._get_all_hooks()},
            "custom_code": render._get_all_custom_code(),
        },
        imports,
    )


def create_document_root(
    head_components: list[Component] | None = None,
    html_lang: Optional[str] = None,
    html_custom_attrs: Optional[Dict[str, Union[Var, str]]] = None,
) -> Component:
    """Create the document root.

    Args:
        head_components: The components to add to the head.
        html_lang: The language of the document, will be added to the html root element.
        html_custom_attrs: custom attributes added to the html root element.

    Returns:
        The document root.
    """
    head_components = head_components or []
    return Html.create(
        DocumentHead.create(*head_components),
        Body.create(
            Main.create(),
            NextScript.create(),
        ),
        lang=html_lang or "en",
        custom_attrs=html_custom_attrs or {},
    )


def create_theme(style: ComponentStyle) -> dict:
    """Create the base style for the app.

    Args:
        style: The style dict for the app.

    Returns:
        The base style for the app.
    """
    # Get the global style from the style dict.
    style_rules = Style({k: v for k, v in style.items() if not isinstance(k, Callable)})

    root_style = {
        # Root styles.
        ":root": Style(
            {f"*{k}": v for k, v in style_rules.items() if k.startswith(":")}
        ),
        # Body styles.
        "body": Style(
            {k: v for k, v in style_rules.items() if not k.startswith(":")},
        ),
    }

    # Return the theme.
    return {"styles": {"global": root_style}}


def get_page_path(path: str) -> str:
    """Get the path of the compiled JS file for the given page.

    Args:
        path: The path of the page.

    Returns:
        The path of the compiled JS file.
    """
    return str(get_web_dir() / constants.Dirs.PAGES / (path + constants.Ext.JS))


def get_theme_path() -> str:
    """Get the path of the base theme style.

    Returns:
        The path of the theme style.
    """
    return str(
        get_web_dir()
        / constants.Dirs.UTILS
        / (constants.PageNames.THEME + constants.Ext.JS)
    )


def get_root_stylesheet_path() -> str:
    """Get the path of the app root file.

    Returns:
        The path of the app root file.
    """
    return str(
        get_web_dir()
        / constants.Dirs.STYLES
        / (constants.PageNames.STYLESHEET_ROOT + constants.Ext.CSS)
    )


def get_context_path() -> str:
    """Get the path of the context / initial state file.

    Returns:
        The path of the context module.
    """
    return str(get_web_dir() / (constants.Dirs.CONTEXTS_PATH + constants.Ext.JS))


def get_components_path() -> str:
    """Get the path of the compiled components.

    Returns:
        The path of the compiled components.
    """
    return str(
        get_web_dir()
        / constants.Dirs.UTILS
        / (constants.PageNames.COMPONENTS + constants.Ext.JS),
    )


def get_stateful_components_path() -> str:
    """Get the path of the compiled stateful components.

    Returns:
        The path of the compiled stateful components.
    """
    return str(
        get_web_dir()
        / constants.Dirs.UTILS
        / (constants.PageNames.STATEFUL_COMPONENTS + constants.Ext.JS)
    )


def add_meta(
    page: Component,
    title: str,
    image: str,
    meta: list[dict],
    description: str | None = None,
) -> Component:
    """Add metadata to a page.

    Args:
        page: The component for the page.
        title: The title of the page.
        image: The image for the page.
        meta: The metadata list.
        description: The description of the page.

    Returns:
        The component with the metadata added.
    """
    meta_tags = [
        item if isinstance(item, Component) else Meta.create(**item) for item in meta
    ]

    children: list[Any] = [Title.create(title)]
    if description:
        children.append(Description.create(content=description))
    children.append(Image.create(content=image))

    page.children.append(
        Head.create(
            *children,
            *meta_tags,
        )
    )

    return page


def write_page(path: str | Path, code: str):
    """Write the given code to the given path.

    Args:
        path: The path to write the code to.
        code: The code to write.
    """
    path = Path(path)
    path_ops.mkdir(path.parent)
    path.write_text(code, encoding="utf-8")


def empty_dir(path: str | Path, keep_files: list[str] | None = None):
    """Remove all files and folders in a directory except for the keep_files.

    Args:
        path: The path to the directory that will be emptied
        keep_files: List of filenames or foldernames that will not be deleted.
    """
    path = Path(path)

    # If the directory does not exist, return.
    if not path.exists():
        return

    # Remove all files and folders in the directory.
    keep_files = keep_files or []
    for element in path.iterdir():
        if element.name not in keep_files:
            path_ops.rm(element)


def is_valid_url(url) -> bool:
    """Check if a url is valid.

    Args:
        url: The Url to check.

    Returns:
        Whether url is valid.
    """
    result = urlparse(url)
    return all([result.scheme, result.netloc])
