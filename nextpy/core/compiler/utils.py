"""Common utility functions used in the compiler."""
from __future__ import annotations

import os
from typing import Any, Type
from urllib.parse import urlparse

from pydantic.fields import ModelField

from nextpy import constants
from nextpy.components.base import (
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
from nextpy.components.component import Component, ComponentStyle, CustomComponent
from nextpy.core.state import Cookie, LocalStorage, State
from nextpy.core.style import Style
from nextpy.utils import console, format, imports, path_ops
from nextpy.core.vars import ImportVar

# To re-export this function.
merge_imports = imports.merge_imports


def compile_import_statement(fields: set[ImportVar]) -> tuple[str, set[str]]:
    """Compile an import statement.

    Args:
        fields: The set of fields to import from the library.

    Returns:
        The libraries for default and rest.
        default: default library. When install "import def from library".
        rest: rest of libraries. When install "import {rest1, rest2} from library"
    """
    # ignore the ImportVar fields with render=False during compilation
    fields = {field for field in fields if field.render}

    # Check for default imports.
    defaults = {field for field in fields if field.is_default}
    assert len(defaults) < 2

    # Get the default import, and the specific imports.
    default = next(iter({field.name for field in defaults}), "")
    rest = {field.name for field in fields - defaults}

    return default, rest


def validate_imports(imports: imports.ImportDict):
    """Verify that the same Tag is not used in multiple import.

    Args:
        imports: The dict of imports to validate

    Raises:
        ValueError: if a conflict on "tag/alias" is detected for an import.
    """
    used_tags = {}
    for lib, _imports in imports.items():
        for _import in _imports:
            import_name = (
                f"{_import.tag}/{_import.alias}" if _import.alias else _import.tag
            )
            if import_name in used_tags:
                raise ValueError(
                    f"Can not compile, the tag {import_name} is used multiple time from {lib} and {used_tags[import_name]}"
                )
            if import_name is not None:
                used_tags[import_name] = lib


def compile_imports(imports: imports.ImportDict) -> list[dict]:
    """Compile an import dict.

    Args:
        imports: The import dict to compile.

    Returns:
        The list of import dict.
    """
    import_dicts = []
    for lib, fields in imports.items():
        default, rest = compile_import_statement(fields)

        # prevent lib from being rendered on the page if all imports are non rendered kind
        if not any({f.render for f in fields}):  # type: ignore
            continue

        if not lib:
            assert not default, "No default field allowed for empty library."
            assert rest is not None and len(rest) > 0, "No fields to import."
            for module in sorted(rest):
                import_dicts.append(get_import_dict(module))
            continue

        # remove the version before rendering the package imports
        lib = format.format_library_name(lib)

        import_dicts.append(get_import_dict(lib, default, rest))
    return import_dicts


def get_import_dict(lib: str, default: str = "", rest: set[str] | None = None) -> dict:
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
        "rest": rest if rest else set(),
    }


def compile_state(state: Type[State]) -> dict:
    """Compile the state of the app.

    Args:
        state: The app state object.

    Returns:
        A dictionary of the compiled state.
    """
    try:
        initial_state = state().dict()
    except Exception as e:
        console.warn(
            f"Failed to compile initial state with computed vars, excluding them: {e}"
        )
        initial_state = state().dict(include_computed=False)
    return format.format_state(initial_state)


def _compile_client_storage_field(
    field: ModelField,
) -> tuple[Type[Cookie] | Type[LocalStorage] | None, dict[str, Any] | None]:
    """Compile the given cookie or local_storage field.

    Args:
        field: The possible cookie field to compile.

    Returns:
        A dictionary of the compiled cookie or None if the field is not cookie-like.
    """
    for field_type in (Cookie, LocalStorage):
        if isinstance(field.default, field_type):
            cs_obj = field.default
        elif isinstance(field.type_, type) and issubclass(field.type_, field_type):
            cs_obj = field.type_()
        else:
            continue
        return field_type, cs_obj.options()
    return None, None


def _compile_client_storage_recursive(
    state: Type[State],
) -> tuple[dict[str, dict], dict[str, dict[str, str]]]:
    """Compile the client-side storage for the given state recursively.

    Args:
        state: The app state object.

    Returns:
        A tuple of the compiled client-side storage info:
            (
                cookies: dict[str, dict],
                local_storage: dict[str, dict[str, str]]
            )
    """
    cookies = {}
    local_storage = {}
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
        else:
            continue
    for substate in state.get_substates():
        substate_cookies, substate_local_storage = _compile_client_storage_recursive(
            substate
        )
        cookies.update(substate_cookies)
        local_storage.update(substate_local_storage)
    return cookies, local_storage


def compile_client_storage(state: Type[State]) -> dict[str, dict]:
    """Compile the client-side storage for the given state.

    Args:
        state: The app state object.

    Returns:
        A dictionary of the compiled client-side storage info.
    """
    cookies, local_storage = _compile_client_storage_recursive(state)
    return {
        constants.COOKIES: cookies,
        constants.LOCAL_STORAGE: local_storage,
    }


def compile_custom_component(
    component: CustomComponent,
) -> tuple[dict, imports.ImportDict]:
    """Compile a custom component.

    Args:
        component: The custom component to compile.

    Returns:
        A tuple of the compiled component and the imports required by the component.
    """
    # Render the component.
    render = component.get_component()

    # Get the imports.
    imports = {
        lib: fields
        for lib, fields in render.get_imports().items()
        if lib != component.library
    }

    # Concatenate the props.
    props = [prop._var_name for prop in component.get_prop_vars()]

    # Compile the component.
    return (
        {
            "name": component.tag,
            "props": props,
            "render": render.render(),
        },
        imports,
    )


def create_document_root(head_components: list[Component] | None = None) -> Component:
    """Create the document root.

    Args:
        head_components: The components to add to the head.

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
    )


def create_theme(style: ComponentStyle) -> dict:
    """Create the base style for the app.

    Args:
        style: The style dict for the app.

    Returns:
        The base style for the app.
    """
    # Get the global style from the style dict.
    global_style = Style({k: v for k, v in style.items() if not isinstance(k, type)})

    # Root styles.
    root_style = Style({k: v for k, v in global_style.items() if k.startswith("::")})

    # Body styles.
    root_style["body"] = Style(
        {k: v for k, v in global_style.items() if k not in root_style}
    )

    # Return the theme.
    return {
        "styles": {"global": root_style},
    }


def get_page_path(path: str) -> str:
    """Get the path of the compiled JS file for the given page.

    Args:
        path: The path of the page.

    Returns:
        The path of the compiled JS file.
    """
    return os.path.join(constants.Dirs.WEB_PAGES, path + constants.Ext.JS)


def get_theme_path() -> str:
    """Get the path of the base theme style.

    Returns:
        The path of the theme style.
    """
    return os.path.join(
        constants.Dirs.WEB_UTILS, constants.PageNames.THEME + constants.Ext.JS
    )


def get_root_stylesheet_path() -> str:
    """Get the path of the app root file.

    Returns:
        The path of the app root file.
    """
    return os.path.join(
        constants.STYLES_DIR, constants.PageNames.STYLESHEET_ROOT + constants.Ext.CSS
    )


def get_context_path() -> str:
    """Get the path of the context / initial state file.

    Returns:
        The path of the context module.
    """
    return os.path.join(constants.Dirs.WEB_UTILS, "context" + constants.Ext.JS)


def get_components_path() -> str:
    """Get the path of the compiled components.

    Returns:
        The path of the compiled components.
    """
    return os.path.join(constants.Dirs.WEB_UTILS, "components" + constants.Ext.JS)


def get_asset_path(filename: str | None = None) -> str:
    """Get the path for an asset.

    Args:
        filename: If given, is added to the root path of assets dir.

    Returns:
        The path of the asset.
    """
    if filename is None:
        return constants.Dirs.WEB_ASSETS
    else:
        return os.path.join(constants.Dirs.WEB_ASSETS, filename)


def add_meta(
    page: Component, title: str, image: str, description: str, meta: list[dict]
) -> Component:
    """Add metadata to a page.

    Args:
        page: The component for the page.
        title: The title of the page.
        image: The image for the page.
        description: The description of the page.
        meta: The metadata list.

    Returns:
        The component with the metadata added.
    """
    meta_tags = [Meta.create(**item) for item in meta]

    page.children.append(
        Head.create(
            Title.create(title),
            Description.create(content=description),
            Image.create(content=image),
            *meta_tags,
        )
    )

    return page


def write_page(path: str, code: str):
    """Write the given code to the given path.

    Args:
        path: The path to write the code to.
        code: The code to write.
    """
    path_ops.mkdir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)


def empty_dir(path: str, keep_files: list[str] | None = None):
    """Remove all files and folders in a directory except for the keep_files.

    Args:
        path: The path to the directory that will be emptied
        keep_files: List of filenames or foldernames that will not be deleted.
    """
    # If the directory does not exist, return.
    if not os.path.exists(path):
        return

    # Remove all files and folders in the directory.
    keep_files = keep_files or []
    directory_contents = os.listdir(path)
    for element in directory_contents:
        if element not in keep_files:
            path_ops.rm(os.path.join(path, element))


def is_valid_url(url) -> bool:
    """Check if a url is valid.

    Args:
        url: The Url to check.

    Returns:
        Whether url is valid.
    """
    result = urlparse(url)
    return all([result.scheme, result.netloc])
