"""Common utility functions used in the compiler."""

from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import json
import operator
import os
import tempfile
import traceback
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urlparse

from reflex_base import constants
from reflex_base.components.component import Component, ComponentStyle
from reflex_base.components.memo import (
    MemoComponentDefinition,
    MemoFunctionDefinition,
    MemoParamKind,
)
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.style import Style
from reflex_base.utils import format, imports, memo_paths
from reflex_base.utils.imports import ImportVar, ParsedImportDict
from reflex_base.vars.base import Field, Var, VarData
from reflex_base.vars.function import DestructuredArg
from reflex_components_core.base import Description, Image, Scripts
from reflex_components_core.base.document import Links, ScrollRestoration
from reflex_components_core.base.document import Meta as ReactMeta
from reflex_components_core.el.elements.metadata import Head, Link, Meta, Title
from reflex_components_core.el.elements.other import Html
from reflex_components_core.el.elements.sectioning import Body

from reflex.istate.storage import Cookie, LocalStorage, SessionStorage
from reflex.state import BaseState, _resolve_delta
from reflex.utils import path_ops
from reflex.utils.prerequisites import get_web_dir

# To re-export this function.
merge_imports = imports.merge_imports


def compile_import_statement(fields: list[ImportVar]) -> tuple[str, list[str]]:
    """Compile an import statement.

    Args:
        fields: The set of fields to import from the library.

    Returns:
        The libraries for default and rest.
        default: default library. When install "import def from library".
        rest: rest of libraries. When install "import {rest1, rest2} from library"

    Raises:
        ValueError: If there is more than one default import.
    """
    # ignore the ImportVar fields with render=False during compilation
    fields_set = {field for field in fields if field.render}

    # Check for default imports.
    defaults = {field for field in fields_set if field.is_default}
    if len(defaults) >= 2:
        msg = "Only one default import is allowed."
        raise ValueError(msg)

    # Get the default import, and the specific imports.
    default = next(iter({field.name for field in defaults}), "")
    rest = {field.name for field in fields_set - defaults}

    return default, sorted(rest)


def validate_imports(import_dict: ParsedImportDict):
    """Verify that the same Tag is not used in multiple import.

    Args:
        import_dict: The dict of imports to validate

    Raises:
        ValueError: if a conflict on "tag/alias" is detected for an import.
    """
    used_tags = {}
    for lib, imported_items in import_dict.items():
        for imported_item in imported_items:
            import_name = (
                f"{imported_item.tag}/{imported_item.alias}"
                if imported_item.alias
                else imported_item.tag
            )
            if import_name in used_tags:
                already_imported = used_tags[import_name]
                if (already_imported[0] == "$" and already_imported[1:] == lib) or (
                    lib[0] == "$" and lib[1:] == already_imported
                ):
                    used_tags[import_name] = lib if lib[0] == "$" else already_imported
                    continue
                msg = f"Can not compile, the tag {import_name} is used multiple time from {lib} and {used_tags[import_name]}"
                raise ValueError(msg)
            if import_name is not None:
                used_tags[import_name] = lib


class _ImportDict(TypedDict):
    lib: str
    default: str
    rest: list[str]


def compile_imports(import_dict: ParsedImportDict) -> list[_ImportDict]:
    """Compile an import dict.

    Args:
        import_dict: The import dict to compile.

    Returns:
        The list of import dict.

    Raises:
        ValueError: If an import in the dict is invalid.
    """
    collapsed_import_dict: ParsedImportDict = imports.collapse_imports(import_dict)
    validate_imports(collapsed_import_dict)
    import_dicts: list[_ImportDict] = []
    for lib, fields in collapsed_import_dict.items():
        # prevent lib from being rendered on the page if all imports are non rendered kind
        if not any(f.render for f in fields):
            continue

        lib_paths: dict[str, list[ImportVar]] = {}

        for field in fields:
            lib_paths.setdefault(field.package_path, []).append(field)

        compiled = {
            path: compile_import_statement(fields) for path, fields in lib_paths.items()
        }

        for path, (default, rest) in compiled.items():
            if not lib:
                if default:
                    msg = "No default field allowed for empty library."
                    raise ValueError(msg)
                if rest is None or len(rest) == 0:
                    msg = "No fields to import."
                    raise ValueError(msg)
                import_dicts.extend(get_import_dict(module) for module in sorted(rest))
                continue

            # remove the version before rendering the package imports
            formatted_lib = format.format_library_name(lib) + (
                path if path != "/" else ""
            )

            import_dicts.append(get_import_dict(formatted_lib, default, rest))
    return import_dicts


def get_import_dict(
    lib: str, default: str = "", rest: list[str] | None = None
) -> _ImportDict:
    """Get dictionary for import template.

    Args:
        lib: The importing react library.
        default: The default module to import.
        rest: The rest module to import.

    Returns:
        A dictionary for import template.
    """
    return _ImportDict(
        lib=lib,
        default=default,
        rest=rest or [],
    )


def save_error(error: Exception) -> str:
    """Save the error to a file.

    Args:
        error: The error to save.

    Returns:
        The path of the saved error.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    constants.Reflex.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = constants.Reflex.LOGS_DIR / f"error_{timestamp}.log"
    traceback.TracebackException.from_exception(error).print(file=log_path.open("w+"))
    return str(log_path)


def _sorted_keys(d: Mapping[str, Any]) -> dict[str, Any]:
    """Sort the keys of a dictionary.

    Args:
        d: The dictionary to sort.

    Returns:
        A new dictionary with sorted keys.
    """
    return dict(sorted(d.items(), key=operator.itemgetter(0)))


def compile_state(state: type[BaseState]) -> dict:
    """Compile the state of the app.

    Args:
        state: The app state object.

    Returns:
        A dictionary of the compiled state.
    """
    initial_state = state(_reflex_internal_init=True).dict(initial=True)
    try:
        _ = asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            resolved_initial_state = pool.submit(
                asyncio.run, _resolve_delta(initial_state)
            ).result()
            return _sorted_keys(resolved_initial_state)

    # Normally the compile runs before any event loop starts, we asyncio.run is available for calling.
    return _sorted_keys(asyncio.run(_resolve_delta(initial_state)))


def _compile_client_storage_field(
    field: Field,
) -> (
    tuple[
        type[Cookie] | type[LocalStorage] | type[SessionStorage],
        dict[str, Any],
    ]
    | tuple[None, None]
):
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
    state: type[BaseState],
) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]
]:
    """Compile the client-side storage for the given state recursively.

    Args:
        state: The app state object.

    Returns:
        A tuple of the compiled client-side storage info: (cookies, local_storage, session_storage).
    """
    cookies: dict[str, dict[str, Any]] = {}
    local_storage: dict[str, dict[str, Any]] = {}
    session_storage: dict[str, dict[str, Any]] = {}
    state_name = state.get_full_name()
    for name, field in state.__fields__.items():
        if name in state.inherited_vars:
            # only include vars defined in this state
            continue
        state_key = f"{state_name}.{name}" + FIELD_MARKER
        field_type, options = _compile_client_storage_field(field)
        if field_type is None or options is None:
            continue
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


def compile_client_storage(
    state: type[BaseState],
) -> dict[str, dict[str, dict[str, Any]]]:
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


def _apply_component_style_for_compile(component: Component) -> Component:
    """Apply the app style to a compiled component tree.

    Args:
        component: The component tree.

    Returns:
        The styled component tree.
    """
    component._add_style_recursive(_app_style())
    return component


def _apply_root_style(component: Component) -> None:
    """Merge app-level style into ``component.style`` without recursing.

    Used for passthrough memo bodies where descendants render (and are styled)
    in the page scope — only the root's style needs merging here.

    Args:
        component: The root component to style in place.
    """
    if type(component)._add_style != Component._add_style:
        msg = "Do not override _add_style directly. Use add_style instead."
        raise UserWarning(msg)
    style = _app_style()
    new_style = component._add_style()
    style_vars = [new_style._var_data]
    component_style = component._get_component_style(style)
    if component_style:
        new_style.update(component_style)
        style_vars.append(component_style._var_data)
    new_style.update(component.style)
    style_vars.append(component.style._var_data)
    new_style._var_data = VarData.merge(*style_vars)
    component.style = new_style


def _app_style() -> ComponentStyle | Style:
    """Return the active app-level component style map, or an empty one.

    Returns:
        The app-level style map.
    """
    try:
        from reflex.utils.prerequisites import get_and_validate_app

        return get_and_validate_app().app.style
    except Exception:
        return {}


def compile_experimental_component_memo(
    definition: MemoComponentDefinition,
) -> tuple[dict, ParsedImportDict]:
    """Compile a memo component.

    Args:
        definition: The component memo definition.

    Returns:
        A tuple of the compiled component definition and its imports.
    """
    hole_child = definition.passthrough_hole_child
    if hole_child is not None:
        # Passthrough memo: shallow-copy the root only — ``render.children``
        # still aliases the user-authored descendants so root-level walkers
        # (e.g. ``Form._get_form_refs``) can introspect the real subtree, but
        # we skip the O(n) deepcopy + recursive style pass. Descendants are
        # rendered AND styled in the page scope, not here, so only the root
        # needs app-level style merged.
        render = copy.copy(definition.component)
        _apply_root_style(render)

        hooks = _root_only_hooks(render)
        custom_code = _root_only_custom_code(render)
        dynamic_imports = _root_only_dynamic_imports(render)
        # Strings returned by the root's ``add_hooks`` can reference symbols
        # (``refs``, ``StateContexts``, etc.) that normally reach this module
        # through descendants' ``_get_hooks_imports`` / ``_get_imports``. JS
        # imports are side-effect-free and dedup cleanly, so pulling the
        # whole subtree's imports here is safe even when some go unused.
        # ``_get_all_imports`` is read-only on the descendants, so the shallow
        # aliasing above is fine.
        all_imports = render._get_all_imports()

        # Swap children for JSX render: the memo body template emits a
        # ``{children}`` hole in place of the real descendants.
        render.children = [hole_child]
        rendered = render.render()
    else:
        render = _apply_component_style_for_compile(copy.deepcopy(definition.component))
        hooks = render._get_all_hooks()
        rendered = render.render()
        custom_code = render._get_all_custom_code()
        dynamic_imports = render._get_all_dynamic_imports()
        all_imports = render._get_all_imports()

    # Each un-mirrored memo lives in ``web/app_components/_internal/<name>.jsx``
    # and is imported from ``$/app_components/_internal/<name>``. Strip a
    # self-import so a memo body that references its own specifier doesn't recurse.
    self_module = memo_paths.unmirrored_library_specifier(definition.export_name)
    imports: ParsedImportDict = {
        lib: fields for lib, fields in all_imports.items() if lib != self_module
    }

    imports.setdefault("@emotion/react", []).append(ImportVar("jsx"))

    signature_fields = [
        field
        for param in definition.params
        if (field := param.signature_field()) is not None
    ]

    if any(p.kind is MemoParamKind.CHILDREN for p in definition.params):
        signature_fields.insert(0, "children")

    rest_param = next(
        (p for p in definition.params if p.kind is MemoParamKind.REST), None
    )

    return (
        {
            "kind": "component",
            "name": definition.export_name,
            "signature": DestructuredArg(
                fields=tuple(signature_fields),
                rest=rest_param.placeholder_name if rest_param is not None else None,
            ).to_javascript(),
            "render": rendered,
            "hooks": hooks,
            "custom_code": custom_code,
            "dynamic_imports": dynamic_imports,
        },
        imports,
    )


def _root_only_hooks(component: Component) -> dict[str, VarData | None]:
    """Return hooks contributed by ``component`` itself, not its subtree.

    Used by the passthrough memo compile path where descendants render in the
    page scope — only the wrapper's own hooks (internal + ``add_hooks`` +
    explicit ``_get_hooks``) belong in the memo body.

    Args:
        component: The root component whose own hooks to collect.

    Returns:
        The root-level hook map, keyed by hook source string.
    """
    code: dict[str, VarData | None] = {}
    code.update(component._get_hooks_internal())
    explicit = component._get_hooks()
    if explicit is not None:
        code[explicit] = None
    code.update(component._get_added_hooks())
    return code


def _root_only_custom_code(component: Component) -> dict[str, None]:
    """Return custom code contributed by ``component`` itself, not its subtree.

    Args:
        component: The root component whose own custom code to collect.

    Returns:
        The root-level custom code snippets.
    """
    code: dict[str, None] = {}
    own = component._get_custom_code()
    if own is not None:
        code[own] = None
    for clz in component._iter_parent_classes_with_method("add_custom_code"):
        for item in clz.add_custom_code(component):
            code[item] = None
    return code


def _root_only_dynamic_imports(component: Component) -> set[str]:
    """Return dynamic imports contributed by ``component`` itself.

    Args:
        component: The root component whose own dynamic imports to collect.

    Returns:
        The root-level dynamic imports.
    """
    own = component._get_dynamic_imports()
    return {own} if own else set()


def compile_experimental_function_memo(
    definition: MemoFunctionDefinition,
) -> tuple[dict, ParsedImportDict]:
    """Compile a memo function.

    Args:
        definition: The function memo definition.

    Returns:
        A tuple of the compiled function definition and its imports.
    """
    imports: ParsedImportDict = {}
    # Reading ``.function`` evaluates a deferred function-memo body on first use.
    function = definition.function
    if var_data := function._get_all_var_data():
        # Per-file memo modules live at ``$/app_components/_internal/<name>``;
        # strip only a self-import to this function memo's own module.
        self_module = memo_paths.unmirrored_library_specifier(definition.python_name)
        imports = {
            lib: list(fields)
            for lib, fields in dict(var_data.imports).items()
            if lib != self_module
        }

    return (
        {
            "kind": "function",
            "name": definition.python_name,
            "function": str(function),
        },
        imports,
    )


def create_document_root(
    head_components: Sequence[Component] | None = None,
    html_lang: str | None = None,
    html_custom_attrs: dict[str, Var | Any] | None = None,
) -> Component:
    """Create the document root.

    Args:
        head_components: The components to add to the head.
        html_lang: The language of the document, will be added to the html root element.
        html_custom_attrs: custom attributes added to the html root element.

    Returns:
        The document root.
    """
    from reflex.utils.misc import preload_color_theme

    existing_meta_types = set()

    for component in head_components or []:
        if isinstance(component, Meta):
            if component.char_set is not None:  # pyright: ignore[reportAttributeAccessIssue]
                existing_meta_types.add("char_set")
            if (
                (name := component.name) is not None  # pyright: ignore[reportAttributeAccessIssue]
                and name.equals(Var.create("viewport"))
            ):
                existing_meta_types.add("viewport")

    # Always include the framework meta and link tags.
    always_head_components = [
        ReactMeta.create(),
        Link.create(
            rel="stylesheet",
            type="text/css",
            href=Var(
                "reflexGlobalStyles",
                _var_data=VarData(
                    imports={
                        "$/styles/__reflex_global_styles.css?url": [
                            ImportVar(tag="reflexGlobalStyles", is_default=True)
                        ]
                    }
                ),
            ),
        ),
        Links.create(),
    ]
    maybe_head_components = []
    # Only include these if the user has not specified them.
    if "char_set" not in existing_meta_types:
        maybe_head_components.append(Meta.create(char_set="utf-8"))
    if "viewport" not in existing_meta_types:
        maybe_head_components.append(
            Meta.create(name="viewport", content="width=device-width, initial-scale=1")
        )

    # Add theme preload script as the very first component to prevent FOUC
    theme_preload_components = [preload_color_theme()]

    head_components = [
        *theme_preload_components,
        *(head_components or []),
        *maybe_head_components,
        *always_head_components,
    ]
    html_component = Html.create(
        Head.create(*head_components),
        Body.create(
            Var("children"),
            ScrollRestoration.create(),
            Scripts.create(),
        ),
        lang=html_lang or "en",
        custom_attrs=html_custom_attrs or {},
    )
    hooks = html_component._get_all_hooks()
    if hooks:
        msg = "You cannot use stateful components or hooks in the document root. Check your head components."
        raise ValueError(msg)
    return html_component


def create_theme(style: ComponentStyle) -> dict:
    """Create the base style for the app.

    Args:
        style: The style dict for the app.

    Returns:
        The base style for the app.
    """
    # Get the global style from the style dict.
    style_rules = Style({k: v for k, v in style.items() if isinstance(k, str)})

    root_style = {
        # Root styles.
        ":root": Style({
            f"*{k}": v for k, v in style_rules.items() if k.startswith(":")
        }),
        # Body styles.
        "body": Style(
            {k: v for k, v in style_rules.items() if not k.startswith(":")},
        ),
    }

    # Return the theme.
    return {"styles": {"global": root_style}}


def _format_route_part(part: str) -> str:
    if part.startswith("[") and part.endswith("]"):
        if part.startswith(("[...", "[[...")):
            return "$"
        if part.startswith("[["):
            return "($" + part.removeprefix("[[").removesuffix("]]") + ")"
        # We don't add [] here since we are reusing them from the input
        return "$" + part
    return "[" + part + "]"


def _path_to_file_stem(path: str) -> str:
    if path == "index":
        return "_index"
    path = path if path != "index" else "/"
    name = ".".join([_format_route_part(part) for part in path.split("/")]).lstrip(".")
    return name + "._index" if not name.endswith("$") else name


def get_page_path(path: str) -> str:
    """Get the path of the compiled JS file for the given page.

    Args:
        path: The path of the page.

    Returns:
        The path of the compiled JS file.
    """
    return str(
        get_web_dir()
        / constants.Dirs.PAGES
        / constants.Dirs.ROUTES
        / (_path_to_file_stem(path) + constants.Ext.JSX)
    )


def get_page_import_specifier(path: str) -> str:
    """Get the ``$``-aliased module specifier for the given page.

    Args:
        path: The path of the page.

    Returns:
        The import specifier (e.g. ``"$/pages/routes/users.$id._index"``).
    """
    return (
        f"$/{constants.Dirs.PAGES}/{constants.Dirs.ROUTES}/{_path_to_file_stem(path)}"
    )


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


def get_memo_components_dir() -> str:
    """Get the directory that holds per-memo module files.

    Returns:
        The directory used for per-memo ``.jsx`` modules. Pages import each
        wrapper directly from ``$/app_components/_internal/<name>``.
    """
    return str(get_web_dir() / constants.Dirs.APP_COMPONENTS_INTERNAL)


def get_memo_module_path(segments: tuple[str, ...]) -> str:
    """Get the on-disk path for a memo module mirrored from a Python module.

    Args:
        segments: Mirrored path segments produced by
            :func:`reflex_base.utils.memo_paths.module_to_mirrored_segments`.

    Returns:
        The absolute path the compiler should write the combined memo file to.
    """
    return str(memo_paths.mirrored_jsx_path(get_web_dir(), segments))


def add_meta(
    page: Component,
    title: str,
    image: str,
    meta: Sequence[Mapping[str, Any] | Component],
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

    page.children.extend(children)
    page.children.extend(meta_tags)

    return page


def resolve_path_of_web_dir(path: str | Path) -> Path:
    """Get the path under the web directory.

    Args:
        path: The path to get. It can be a relative or absolute path.

    Returns:
        The path under the web directory.
    """
    path = Path(path)
    web_dir = get_web_dir()
    if path.is_relative_to(web_dir):
        return path.absolute()
    return (web_dir / path).absolute()


def write_file(path: str | Path, code: str):
    """Write the given code to the given path.

    Args:
        path: The path to write the code to.
        code: The code to write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == code:
        return
    path.write_text(code, encoding="utf-8")


_MEMO_MANIFEST_FILENAME = ".memo-manifest.json"


def _read_memo_manifest(web_dir: Path) -> set[str]:
    """Read the previous compile's memo file manifest.

    Args:
        web_dir: The project's ``.web`` directory.

    Returns:
        The set of paths (relative to ``.web``) recorded by the previous
        compile, or an empty set if the manifest is absent or invalid.
    """
    manifest_path = web_dir / _MEMO_MANIFEST_FILENAME
    if not manifest_path.exists():
        return set()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(data, list):
        return set()
    return {entry for entry in data if isinstance(entry, str)}


def _write_memo_manifest(web_dir: Path, relative_paths: set[str]) -> None:
    """Atomically write the new memo file manifest.

    Args:
        web_dir: The project's ``.web`` directory.
        relative_paths: Paths emitted this run, relative to ``.web``.
    """
    manifest_path = web_dir / _MEMO_MANIFEST_FILENAME
    web_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".memo-manifest.", suffix=".json.tmp", dir=str(web_dir)
    )
    # Close the raw fd immediately and reopen the file by path. Wrapping the
    # fd via os.fdopen() would leak it if the wrap itself raised.
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(sorted(relative_paths), fh)
        tmp_path.replace(manifest_path)
    except Exception:
        # Best-effort cleanup; manifest write is recoverable on the next run.
        tmp_path.unlink(missing_ok=True)
        raise


def prune_stale_memo_files(emitted_paths: Iterable[str | Path]) -> None:
    """Delete memo files written previously that this compile no longer emits.

    Only paths that appear in the previous manifest are considered for
    deletion — never a fresh filesystem walk — so files this code did not
    emit are never touched. Empty parent directories created by mirrored
    output are removed up to (but not including) the ``.web`` root.

    Args:
        emitted_paths: Absolute (or ``.web``-relative) paths the current
            compile produced for the memo pipeline.
    """
    web_dir = get_web_dir()

    emitted_relative: set[str] = set()
    for path in emitted_paths:
        absolute = Path(path)
        if not absolute.is_absolute():
            absolute = web_dir / absolute
        try:
            relative = absolute.relative_to(web_dir)
        except ValueError:
            continue
        emitted_relative.add(str(relative).replace(os.sep, "/"))

    previous = _read_memo_manifest(web_dir)
    for relative in previous - emitted_relative:
        target = web_dir / relative
        if target.is_file():
            target.unlink()
            parent = target.parent
            while parent != web_dir and parent.is_relative_to(web_dir):
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent

    if emitted_relative != previous:
        _write_memo_manifest(web_dir, emitted_relative)


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


def is_valid_url(url: str) -> bool:
    """Check if a url is valid.

    Args:
        url: The Url to check.

    Returns:
        Whether url is valid.
    """
    result = urlparse(url)
    return all([result.scheme, result.netloc])
