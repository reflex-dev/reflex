"""Compiler for the reflex apps."""

from __future__ import annotations

import collections
import dataclasses
import json
import sys
from collections.abc import Callable, Iterable, Sequence
from inspect import getmodule
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any

from reflex_base import constants
from reflex_base.components.component import (
    BaseComponent,
    Component,
    ComponentStyle,
    evaluate_style_namespaces,
)
from reflex_base.components.dynamic import bundled_libraries, dynamic_component_imports
from reflex_base.components.memo import (
    MEMOS,
    MemoComponentDefinition,
    MemoDefinition,
    MemoFunctionDefinition,
    create_component_memo,
    reset_memo_component_classes,
)
from reflex_base.config import get_config
from reflex_base.constants.compiler import PageNames, ResetStylesheet
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.environment import environment
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext, Plugin
from reflex_base.utils import memo_paths
from reflex_base.utils.exceptions import ReflexError
from reflex_base.utils.format import format_library_name, to_title_case
from reflex_base.utils.imports import ABSOLUTE_IMPORT_PREFIXES, ImportVar
from reflex_base.vars.base import LiteralVar, Var
from reflex_base.vars.sequence import LiteralStringVar
from reflex_components_core.base.app_wrap import AppWrap
from reflex_components_core.base.fragment import Fragment
from reflex_components_radix.plugin import RadixThemesPlugin
from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn

from reflex.compiler import templates, utils
from reflex.compiler.plugins import default_page_plugins
from reflex.compiler.plugins.builtin import collect_var_app_wraps_in_subtree
from reflex.compiler.plugins.memoize import MemoizeStatefulPlugin
from reflex.state import BaseState, code_uses_state_contexts
from reflex.utils import console, frontend_skeleton, path_ops, prerequisites
from reflex.utils.exec import get_compile_context, is_prod_mode
from reflex.utils.prerequisites import get_web_dir


def _set_progress_total(
    progress: Progress | console.PoorProgress,
    task: Any,
    total: int,
) -> None:
    """Update a task total for either rich or fallback progress bars."""
    progress.update(task, total=total)


def _apply_common_imports(
    imports: dict[str, list[ImportVar]],
):
    imports.setdefault("@emotion/react", []).append(ImportVar("jsx"))
    imports.setdefault("react", []).extend(
        [ImportVar("Fragment"), ImportVar("useEffect")],
    )


def _extend_imports_in_place(
    target: dict[str, list[ImportVar]],
    import_dict: dict[str, Any] | tuple[tuple[str, Any], ...],
) -> None:
    """Append imports to an existing parsed import dict.

    Args:
        target: The import dictionary to update.
        import_dict: The imports to append.
    """
    for lib, fields in (
        import_dict if isinstance(import_dict, tuple) else import_dict.items()
    ):
        lib = "$" + lib if lib.startswith(ABSOLUTE_IMPORT_PREFIXES) else lib
        target_fields = target.setdefault(lib, [])
        if isinstance(fields, (list, tuple, set)):
            target_fields.extend(
                ImportVar(field) if isinstance(field, str) else field
                for field in fields
            )
        else:
            target_fields.append(
                ImportVar(fields) if isinstance(fields, str) else fields
            )


def _compile_document_root(root: Component) -> str:
    """Compile the document root.

    Args:
        root: The document root to compile.

    Returns:
        The compiled document root.
    """
    document_root_imports = root._get_all_imports()
    _apply_common_imports(document_root_imports)
    return templates.document_root_template(
        imports=utils.compile_imports(document_root_imports),
        document=root.render(),
    )


# Path-like prefixes mark Reflex-controlled internal modules (e.g. "$/utils/...");
# the rest are external npm libraries where star imports defeat tree-shaking.
_INTERNAL_LIB_PREFIXES = ("$/", "/", ".")

# Runtime-eval'd dynamic components reach for ``window.__reflex.react`` and
# ``window.__reflex['@emotion/react']`` as if they were the whole module
# (``state.js`` aliases ``window.React = window.__reflex.react``). Tree-shaking
# these to the host app's static surface drops APIs that user custom_code or
# third-party libraries may legitimately read at runtime, so always star-import.
_ALWAYS_STAR_IMPORT_LIBS = frozenset({"react", "@emotion/react"})


def collect_window_library_imports(
    import_sources: Iterable[dict[str, list[ImportVar]]],
) -> dict[str, set[str] | None]:
    """Build the ``window.__reflex`` surface for runtime-eval'd code.

    Each bundled library gets either a set of named exports (for external libs,
    collected from the app's actual static usage so Rolldown can tree-shake) or
    ``None`` (for internal Reflex modules, which use a star import).

    External library tags come from two sources: (1) static page / app-root
    imports, and (2) tags captured during compile-time serialization of
    dynamic Component values (Component-typed state field defaults, computed
    Component vars evaluated when generating the initial state) -- see
    ``reflex_base.components.dynamic.dynamic_component_imports``.

    Takes an iterable of import dicts (one per page / app_root / memo group)
    rather than a pre-merged dict so callers don't have to fold the same
    library's named exports across sources before calling.

    Args:
        import_sources: One import dict per source (page, app_root, etc).

    Returns:
        Mapping from library path to either the set of named exports to expose
        (external libs) or None (internal libs, use star import).
    """
    per_lib_tags: dict[str, set[str]] = {}
    for source in chain(import_sources, (dynamic_component_imports,)):
        for imported_lib, import_vars in source.items():
            key = format_library_name(imported_lib)
            for iv in import_vars:
                if iv.tag and not iv.is_default:
                    per_lib_tags.setdefault(key, set()).add(iv.tag)

    result: dict[str, set[str] | None] = {}
    for lib in bundled_libraries:
        if lib.startswith(_INTERNAL_LIB_PREFIXES) or lib in _ALWAYS_STAR_IMPORT_LIBS:
            result[lib] = None
            continue
        tags = per_lib_tags.get(lib)
        if tags:
            result[lib] = tags
    return result


def _compile_app(
    app_root: Component,
    hydrate_fallback_export: str | None = None,
    window_library_imports: dict[str, set[str] | None] | None = None,
    app_root_imports: dict[str, list[ImportVar]] | None = None,
) -> str:
    """Compile the app template component.

    Args:
        app_root: The app root to compile.
        hydrate_fallback_export: The exported name of the hydrate-fallback memo
            component to re-export as ``HydrateFallback``, or None for no fallback.
        window_library_imports: Per-library named-export surface to expose on
            ``window.__reflex`` for dynamic components. Empty/None skips the
            bootstrap entirely.
        app_root_imports: Precomputed result of ``app_root._get_all_imports()``;
            pass it to avoid a second full-tree walk on the hot path.

    Returns:
        The compiled app.
    """
    if app_root_imports is None:
        app_root_imports = app_root._get_all_imports()
    _apply_common_imports(app_root_imports)

    return templates.app_root_template(
        imports=utils.compile_imports(app_root_imports),
        custom_codes=app_root._get_all_custom_code(),
        hooks=app_root._get_all_hooks(),
        window_library_imports=window_library_imports or {},
        render=app_root.render(),
        dynamic_imports=app_root._get_all_dynamic_imports(),
        hydrate_fallback_export=hydrate_fallback_export,
    )


def _compile_theme(theme: str) -> str:
    """Compile the theme.

    Args:
        theme: The theme to compile.

    Returns:
        The compiled theme.
    """
    return templates.theme_template(theme=theme)


def _resolve_default_color_mode(theme: Component | None) -> str:
    """Resolve the app's compile-time default color mode.

    An explicit theme appearance ("light"/"dark") takes precedence over the
    ``Config.default_color_mode`` option; "inherit", no appearance, or a
    non-literal appearance Var falls back to the config value.

    Args:
        theme: The top-level app theme, if any.

    Returns:
        One of "system", "light", or "dark".
    """
    appearance = getattr(theme, "appearance", None)
    if appearance is not None:
        appearance_var = LiteralVar.create(appearance)
        if (
            isinstance(appearance_var, LiteralStringVar)
            and appearance_var._var_value != "inherit"
        ):
            return appearance_var._var_value
    return get_config().default_color_mode


def _compile_contexts(state: type[BaseState] | None, theme: Component | None) -> str:
    """Compile the initial state and contexts.

    Args:
        state: The app state.
        theme: The top-level app theme.

    Returns:
        The compiled context file.
    """
    default_color_mode = str(LiteralVar.create(_resolve_default_color_mode(theme)))

    return (
        templates.context_template(
            initial_state=utils.compile_state(state),
            state_name=state.get_name(),
            client_storage=utils.compile_client_storage(state),
            is_dev_mode=not is_prod_mode(),
            default_color_mode=default_color_mode,
        )
        if state
        else templates.context_template(
            is_dev_mode=not is_prod_mode(),
            default_color_mode=default_color_mode,
        )
    )


def _compile_page(component: BaseComponent) -> str:
    """Compile the component.

    Args:
        component: The component to compile.

    Returns:
        The compiled component.
    """
    imports = component._get_all_imports()
    _apply_common_imports(imports)
    imports = utils.compile_imports(imports)

    # Compile the code to render the component.
    return templates.page_template(
        imports=imports,
        dynamic_imports=sorted(component._get_all_dynamic_imports()),
        custom_codes=component._get_all_custom_code(),
        hooks=component._get_all_hooks(),
        render=component.render(),
    )


def compile_root_stylesheet(
    stylesheets: list[str],
    reset_style: bool = True,
    plugins: Sequence[Plugin] | None = None,
) -> tuple[str, str]:
    """Compile the root stylesheet.

    Args:
        stylesheets: The stylesheets to include in the root stylesheet.
        reset_style: Whether to include CSS reset for margin and padding.
        plugins: The effective plugins for the active compile.

    Returns:
        The path and code of the compiled root stylesheet.
    """
    output_path = utils.get_root_stylesheet_path()

    code = _compile_root_stylesheet(stylesheets, reset_style, plugins)

    return output_path, code


def _validate_stylesheet(stylesheet_full_path: Path, assets_app_path: Path) -> None:
    """Validate the stylesheet.

    Args:
        stylesheet_full_path: The stylesheet to validate.
        assets_app_path: The path to the assets directory.

    Raises:
        ValueError: If the stylesheet is not supported.
        FileNotFoundError: If the stylesheet is not found.
    """
    suffix = stylesheet_full_path.suffix[1:] if stylesheet_full_path.suffix else ""
    if suffix not in constants.Reflex.STYLESHEETS_SUPPORTED:
        msg = f"Stylesheet file {stylesheet_full_path} is not supported."
        raise ValueError(msg)
    if not stylesheet_full_path.absolute().is_relative_to(assets_app_path.absolute()):
        msg = f"Cannot include stylesheets from outside the assets directory: {stylesheet_full_path}"
        raise FileNotFoundError(msg)
    if not stylesheet_full_path.name:
        msg = f"Stylesheet file name cannot be empty: {stylesheet_full_path}"
        raise ValueError(msg)
    if (
        len(
            stylesheet_full_path
            .absolute()
            .relative_to(assets_app_path.absolute())
            .parts
        )
        == 1
        and stylesheet_full_path.stem == PageNames.STYLESHEET_ROOT
    ):
        msg = f"Stylesheet file name cannot be '{PageNames.STYLESHEET_ROOT}': {stylesheet_full_path}"
        raise ValueError(msg)


def _compile_root_stylesheet(
    stylesheets: list[str],
    reset_style: bool = True,
    plugins: Sequence[Plugin] | None = None,
) -> str:
    """Compile the root stylesheet.

    Args:
        stylesheets: The stylesheets to include in the root stylesheet.
        reset_style: Whether to include CSS reset for margin and padding.
        plugins: The effective plugins for the active compile.

    Returns:
        The compiled root stylesheet.

    Raises:
        FileNotFoundError: If a specified stylesheet in assets directory does not exist.
    """
    # Add stylesheets from plugins.
    sheets = []

    # Add CSS reset if enabled
    if reset_style:
        # Reference the vendored style reset file (automatically copied from .templates/web)
        sheets.append(f"./{ResetStylesheet.FILENAME}")

    active_plugins = get_config().plugins if plugins is None else plugins
    sheets.extend([
        sheet for plugin in active_plugins for sheet in plugin.get_stylesheet_paths()
    ])

    failed_to_import_sass = False
    assets_app_path = Path.cwd() / constants.Dirs.APP_ASSETS

    stylesheets_files: list[Path] = []
    stylesheets_urls = []

    for stylesheet in stylesheets:
        if not utils.is_valid_url(stylesheet):
            # check if stylesheet provided exists.
            stylesheet_full_path = assets_app_path / stylesheet.strip("/")

            if not stylesheet_full_path.exists():
                msg = f"The stylesheet file {stylesheet_full_path} does not exist."
                raise FileNotFoundError(msg)

            if stylesheet_full_path.is_dir():
                all_files = (
                    file
                    for ext in constants.Reflex.STYLESHEETS_SUPPORTED
                    for file in stylesheet_full_path.rglob("*." + ext)
                )
                for file in all_files:
                    if file.is_dir():
                        continue
                    # Validate the stylesheet.
                    _validate_stylesheet(file, assets_app_path)
                    stylesheets_files.append(file)

            else:
                # Validate the stylesheet.
                _validate_stylesheet(stylesheet_full_path, assets_app_path)
                stylesheets_files.append(stylesheet_full_path)
        else:
            stylesheets_urls.append(stylesheet)

    sheets.extend(dict.fromkeys(stylesheets_urls))

    for stylesheet in stylesheets_files:
        target_path = stylesheet.relative_to(assets_app_path).with_suffix(".css")
        target = get_web_dir() / constants.Dirs.STYLES / target_path

        target.parent.mkdir(parents=True, exist_ok=True)

        if stylesheet.suffix == ".css":
            path_ops.cp(src=stylesheet, dest=target, overwrite=True)
        else:
            try:
                from sass import compile as sass_compile

                target.write_text(
                    data=sass_compile(
                        filename=str(stylesheet),
                        output_style="compressed",
                    ),
                    encoding="utf8",
                )
            except ImportError:
                failed_to_import_sass = True

        str_target_path = "./" + str(target_path)
        sheets.append(str_target_path) if str_target_path not in sheets else None

    if failed_to_import_sass:
        console.error(
            'The `libsass` package is required to compile sass/scss stylesheet files. Run `pip install "libsass>=0.23.0"`.'
        )

    return templates.styles_template(stylesheets=sheets)


def _compile_component(component: Component) -> str:
    """Compile a single component.

    Args:
        component: The component to compile.

    Returns:
        The compiled component.
    """
    return templates.component_template(component=component)


@dataclasses.dataclass
class _MemoGroup:
    """Accumulator for memos that share a mirrored output path."""

    components: list[dict] = dataclasses.field(default_factory=list)
    functions: list[dict] = dataclasses.field(default_factory=list)
    imports: dict[str, list[ImportVar]] = dataclasses.field(default_factory=dict)
    dynamic_imports: list[str] = dataclasses.field(default_factory=list)
    custom_code: list[str] = dataclasses.field(default_factory=list)

    def add_component(
        self, render: dict, memo_imports: dict[str, list[ImportVar]]
    ) -> None:
        self.components.append(render)
        _extend_imports_in_place(self.imports, memo_imports)
        self.dynamic_imports.extend(sorted(render.get("dynamic_imports", []) or []))
        self.custom_code.extend(render.get("custom_code", []) or [])

    def add_function(
        self, render: dict, memo_imports: dict[str, list[ImportVar]]
    ) -> None:
        self.functions.append(render)
        _extend_imports_in_place(self.imports, memo_imports)


# Imports every memo module needs regardless of its body: ``isTrue`` for prop
# coercion. The component wrapper import (``memo`` from React by default)
# rides on each definition's ``wrapper`` var data instead, so a module whose
# memos swap or drop the default wrapper doesn't import it. Shared by the
# grouped and un-mirrored compile paths so they can't drift apart.
_MEMO_BASE_IMPORTS: dict[str, list[ImportVar]] = {
    f"$/{constants.Dirs.STATE_PATH}": [ImportVar(tag="isTrue")],
}


def _compile_memo_components(
    memos: Iterable[MemoDefinition] = (),
) -> tuple[list[tuple[str, str]], dict[str, list[ImportVar]]]:
    """Compile memos grouped by their source module's mirrored output path.

    Memos that captured a source module land in a single combined file at
    ``.web/app_components/<segments>.jsx`` so the page-side import surface
    matches the source layout. Memos that can't be mirrored (``__main__``,
    unsafe module names) fall back to one file per memo at
    ``.web/utils/components/<name>.jsx`` that page-side code imports directly.

    Args:
        memos: The memos to compile.

    Returns:
        A list of ``(path, code)`` pairs to write and the aggregated imports
        across all memo modules.
    """
    output_files: list[tuple[str, str]] = []
    aggregate_imports: dict[str, list[ImportVar]] = {}
    unmirrored_files: list[tuple[str, str]] = []
    unmirrored_base_dir = utils.get_memo_components_dir()
    groups: collections.defaultdict[tuple[str, ...], _MemoGroup] = (
        collections.defaultdict(_MemoGroup)
    )

    def _emit_unmirrored(
        compile_fn: Callable[[dict, dict], tuple[str, dict[str, list[ImportVar]]]],
        render: dict,
        render_imports: dict,
    ) -> None:
        code, file_imports = compile_fn(render, render_imports)
        unmirrored_files.append((
            _memo_component_file_path(unmirrored_base_dir, render["name"]),
            code,
        ))
        _extend_imports_in_place(aggregate_imports, file_imports)

    for memo in memos:
        if isinstance(memo, MemoComponentDefinition):
            memo_render, memo_imports = utils.compile_experimental_component_memo(memo)
            segments = memo_paths.module_to_mirrored_segments(memo.source_module)
            if segments is None:
                _emit_unmirrored(
                    _compile_single_memo_component, memo_render, memo_imports
                )
            else:
                groups[segments].add_component(memo_render, memo_imports)
        elif isinstance(memo, MemoFunctionDefinition):
            memo_render, memo_imports = utils.compile_experimental_function_memo(memo)
            segments = memo_paths.module_to_mirrored_segments(memo.source_module)
            if segments is None:
                _emit_unmirrored(
                    _compile_single_memo_function, memo_render, memo_imports
                )
            else:
                groups[segments].add_function(memo_render, memo_imports)

    if groups:
        _extend_imports_in_place(aggregate_imports, _MEMO_BASE_IMPORTS)
        _apply_common_imports(aggregate_imports)

    # Maps a case-folded output path to the module that claimed it, so two
    # modules differing only by case (which collide on case-insensitive
    # filesystems) are caught instead of one silently overwriting the other.
    claimed_paths: dict[str, str] = {}
    for segments, group in groups.items():
        module_path = utils.get_memo_module_path(segments)
        module_name = ".".join(segments)
        case_key = module_path.casefold()
        if (clash := claimed_paths.get(case_key)) is not None:
            msg = (
                f"Memoized component modules {clash!r} and {module_name!r} both "
                f"mirror to {module_path!r} (their paths differ only by case), "
                f"which collides on case-insensitive filesystems. Rename one of "
                f"the source modules."
            )
            raise ReflexError(msg)
        claimed_paths[case_key] = module_name
        # Strip self-imports — when memos in this group reference each other,
        # their compiled imports point at this group's own mirrored specifier.
        # Importing from the same file would shadow the module's own exports.
        self_specifier = memo_paths.mirrored_library_specifier(segments)
        group.imports.pop(self_specifier, None)
        merged_imports = utils.merge_imports(_MEMO_BASE_IMPORTS, group.imports)
        _apply_common_imports(merged_imports)
        code = templates.memo_components_template(
            imports=utils.compile_imports(merged_imports),
            components=group.components,
            functions=group.functions,
            dynamic_imports=sorted(set(group.dynamic_imports)),
            custom_codes=list(dict.fromkeys(group.custom_code)),
        )
        output_files.append((module_path, code))
        _extend_imports_in_place(aggregate_imports, group.imports)

    return [*unmirrored_files, *output_files], aggregate_imports


def _compile_single_memo_component(
    component_render: dict,
    component_imports: dict[str, list[ImportVar]],
) -> tuple[str, dict[str, list[ImportVar]]]:
    """Render one memoized component as a standalone module.

    Args:
        component_render: The component's render dict.
        component_imports: The component's imports before common/common-memo
            additions.

    Returns:
        The file contents and the full import dict used to compile it.
    """
    imports = utils.merge_imports(_MEMO_BASE_IMPORTS, component_imports)
    _apply_common_imports(imports)
    code = templates.memo_single_component_template(
        imports=utils.compile_imports(imports),
        component=component_render,
        dynamic_imports=sorted(component_render.get("dynamic_imports", []) or []),
        custom_codes=component_render.get("custom_code", []) or [],
    )
    return code, imports


def _compile_single_memo_function(
    function_render: dict,
    function_imports: dict[str, list[ImportVar]],
) -> tuple[str, dict[str, list[ImportVar]]]:
    """Render one function memo as a standalone module.

    Args:
        function_render: The function's render dict.
        function_imports: The function's imports.

    Returns:
        The file contents and the full import dict used to compile it.
    """
    imports = utils.merge_imports({}, function_imports)
    code = templates.memo_single_function_template(
        imports=utils.compile_imports(imports),
        function=function_render,
    )
    return code, imports


def _memo_component_file_path(base_dir: str, name: str) -> str:
    """Return the on-disk path for a per-memo module.

    Args:
        base_dir: The directory that holds per-memo files.
        name: The memo's export name.

    Returns:
        The absolute path for the memo's ``.jsx`` file.
    """
    return str(Path(base_dir) / f"{name}{constants.Ext.JSX}")


def compile_document_root(
    head_components: list[Component],
    html_lang: str | None = None,
    html_custom_attrs: dict[str, Var | Any] | None = None,
    default_color_mode: str = "system",
) -> tuple[str, str]:
    """Compile the document root.

    Args:
        head_components: The components to include in the head.
        html_lang: The language of the document, will be added to the html root element.
        html_custom_attrs: custom attributes added to the html root element.
        default_color_mode: The color mode applied before hydration when no theme
            is saved in the browser.

    Returns:
        The path and code of the compiled document root.
    """
    # Get the path for the output file.
    output_path = str(
        get_web_dir() / constants.Dirs.PAGES / constants.PageNames.DOCUMENT_ROOT
    )

    # Create the document root.
    document_root = utils.create_document_root(
        head_components,
        html_lang=html_lang,
        html_custom_attrs=html_custom_attrs,
        default_color_mode=default_color_mode,
    )

    # Compile the document root.
    code = _compile_document_root(document_root)
    return output_path, code


def compile_app_root(
    app_root: Component,
    hydrate_fallback_export: str | None = None,
    window_library_imports: dict[str, set[str] | None] | None = None,
    app_root_imports: dict[str, list[ImportVar]] | None = None,
) -> tuple[str, str]:
    """Compile the app root.

    Args:
        app_root: The app root component to compile.
        hydrate_fallback_export: The exported name of the hydrate-fallback memo
            component to re-export as ``HydrateFallback``, or None for no fallback.
        window_library_imports: Per-library named-export surface for
            ``window.__reflex`` (see ``collect_window_library_imports``). Pass
            ``None`` to skip emitting ``window.__reflex`` entirely.
        app_root_imports: Precomputed ``app_root._get_all_imports()``; reused
            from the caller to avoid a second tree walk.

    Returns:
        The path and code of the compiled app wrapper.
    """
    output_path = str(
        get_web_dir() / constants.Dirs.PAGES / constants.PageNames.APP_ROOT
    )

    code = _compile_app(
        app_root,
        hydrate_fallback_export=hydrate_fallback_export,
        window_library_imports=window_library_imports,
        app_root_imports=app_root_imports,
    )
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
    code = _compile_theme(str(LiteralVar.create(theme)))
    return output_path, code


def compile_contexts(
    state: type[BaseState] | None,
    theme: Component | None,
) -> tuple[str, str]:
    """Compile the initial state / context.

    Args:
        state: The app state.
        theme: The top-level app theme.

    Returns:
        The path and code of the compiled context.
    """
    # Get the path for the output file.
    output_path = utils.get_context_path()

    return output_path, _compile_contexts(state, theme)


def compile_page(path: str, component: BaseComponent) -> tuple[str, str]:
    """Compile a single page.

    Args:
        path: The path to compile the page to.
        component: The component to compile.

    Returns:
        The path and code of the compiled page.
    """
    # Get the path for the output file.
    output_path = utils.get_page_path(path)

    # Add the style to the component.
    code = _compile_page(component)
    return output_path, code


def compile_page_from_context(page_ctx: PageContext) -> tuple[str, str]:
    """Compile a single page from a collected page context.

    Args:
        page_ctx: The collected page context to render.

    Returns:
        The path and code of the compiled page.
    """
    output_path = utils.get_page_path(page_ctx.route)
    imports = {
        lib: list(fields)
        for lib, fields in (
            page_ctx.frontend_imports or page_ctx.merged_imports(collapse=True)
        ).items()
    }
    _apply_common_imports(imports)

    code = templates.page_template(
        imports=utils.compile_imports(imports),
        dynamic_imports=sorted(page_ctx.dynamic_imports),
        custom_codes=page_ctx.custom_code_dict(),
        hooks=page_ctx.hooks,
        render=page_ctx.root_component.render(),
    )
    return output_path, code


def compile_memo_components(
    memos: Iterable[MemoDefinition] = (),
) -> tuple[list[tuple[str, str]], dict[str, list[ImportVar]]]:
    """Compile the memos into one module per memo.

    Args:
        memos: The memos to compile.

    Returns:
        A list of ``(path, code)`` pairs (one per memo module) alongside the
        aggregated imports across all memo modules.
    """
    return _compile_memo_components(memos)


def purge_web_pages_dir():
    """Empty out .web/pages directory."""
    if not is_prod_mode() and environment.REFLEX_PERSIST_WEB_DIR.get():
        # Skip purging the web directory in dev mode if REFLEX_PERSIST_WEB_DIR is set.
        return

    # Empty out the web pages directory.
    utils.empty_dir(
        get_web_dir() / constants.Dirs.PAGES,
        keep_files=["routes.js", "entry.client.js"],
    )


if TYPE_CHECKING:
    from reflex.app import App, ComponentCallable, UnevaluatedPage


def _into_component_once(
    component: Component
    | ComponentCallable
    | tuple[Component, ...]
    | str
    | Var
    | int
    | float,
) -> Component | None:
    """Convert a component to a Component.

    Args:
        component: The component to convert.

    Returns:
        The converted component.
    """
    if isinstance(component, Component):
        return component
    if isinstance(component, (Var, int, float, str)):
        return Fragment.create(component)
    if isinstance(component, Sequence):
        return Fragment.create(*component)
    return None


def readable_name_from_component(
    component: Component | ComponentCallable,
) -> str | None:
    """Get the readable name of a component.

    Args:
        component: The component to get the name of.

    Returns:
        The readable name of the component.
    """
    if isinstance(component, Component):
        return type(component).__name__
    if isinstance(component, (Var, int, float, str)):
        return str(component)
    if isinstance(component, Sequence):
        return ", ".join(str(c) for c in component)
    if callable(component):
        module_name = getattr(component, "__module__", None)
        if module_name is not None:
            module = getmodule(component)
            if module is not None:
                module_name = module.__name__
        if module_name is not None:
            return f"{module_name}.{component.__name__}"
        return component.__name__
    return None


def _modify_exception(e: Exception) -> None:
    """Modify the exception to make it more readable.

    Args:
        e: The exception to modify.
    """
    if len(e.args) == 1 and isinstance((msg := e.args[0]), str):
        while (state_index := msg.find("reflex___")) != -1:
            dot_index = msg.find(".", state_index)
            if dot_index == -1:
                break
            state_name = msg[state_index:dot_index]
            module_dot_state_name = state_name.replace("___", ".").rsplit("__", 1)[-1]
            module_path, _, state_snake_case = module_dot_state_name.rpartition(".")
            if not state_snake_case:
                break
            actual_state_name = to_title_case(state_snake_case)
            msg = (
                f"{msg[:state_index]}{module_path}.{actual_state_name}{msg[dot_index:]}"
            )

        msg = msg.replace(FIELD_MARKER, "")

        e.args = (msg,)


def into_component(component: Component | ComponentCallable) -> Component:
    """Convert a component to a Component.

    Args:
        component: The component to convert.

    Returns:
        The converted component.

    Raises:
        TypeError: If the component is not a Component.

    # noqa: DAR401
    """
    if (converted := _into_component_once(component)) is not None:
        return converted
    if not callable(component):
        msg = f"Expected a Component or callable, got {component!r} of type {type(component)}"
        raise TypeError(msg)

    try:
        component_called = component()
    except KeyError as e:
        if isinstance(e, ReflexError):
            _modify_exception(e)
            raise
        key = e.args[0] if e.args else None
        if key is not None and isinstance(key, Var):
            raise TypeError(
                "Cannot access a primitive map with a Var. Consider calling rx.Var.create() on the map."
            ).with_traceback(e.__traceback__) from None
        raise
    except TypeError as e:
        if isinstance(e, ReflexError):
            _modify_exception(e)
            raise
        message = e.args[0] if e.args else None
        if message and isinstance(message, str):
            if message.endswith("has no len()") and (
                "ArrayCastedVar" in message
                or "ObjectCastedVar" in message
                or "StringCastedVar" in message
            ):
                raise TypeError(
                    "Cannot pass a Var to a built-in function. Consider using .length() for accessing the length of an iterable Var."
                ).with_traceback(e.__traceback__) from None
            if message.endswith((
                "indices must be integers or slices, not NumberCastedVar",
                "indices must be integers or slices, not BooleanCastedVar",
            )):
                raise TypeError(
                    "Cannot index into a primitive sequence with a Var. Consider calling rx.Var.create() on the sequence."
                ).with_traceback(e.__traceback__) from None
        if "CastedVar" in str(e):
            raise TypeError(
                "Cannot pass a Var to a built-in function. Consider moving the operation to the backend, using existing Var operations, or defining a custom Var operation."
            ).with_traceback(e.__traceback__) from None
        raise
    except ReflexError as e:
        _modify_exception(e)
        raise

    if (converted := _into_component_once(component_called)) is not None:
        return converted

    msg = f"Expected a Component, got {component_called!r} of type {type(component_called)}"
    raise TypeError(msg)


def compile_unevaluated_page(
    route: str,
    page: UnevaluatedPage,
    style: ComponentStyle | None = None,
    theme: Component | None = None,
) -> Component:
    """Compiles an uncompiled page into a component and adds meta information.

    Args:
        route: The route of the page.
        page: The uncompiled page object.
        style: The style of the page.
        theme: The theme of the page.

    Returns:
        The compiled component and whether state should be enabled.

    Raises:
        Exception: If an error occurs while evaluating the page.
    """
    try:
        # Generate the component if it is a callable.
        component = into_component(page.component)

        component._add_style_recursive(style or {}, theme)

        from reflex_base.utils.format import make_default_page_title

        component = Fragment.create(component)

        meta_args = {
            "title": (
                page.title
                if page.title is not None
                else make_default_page_title(get_config().app_name, route)
            ),
            "image": page.image,
            "meta": page.meta,
        }

        if page.description is not None:
            meta_args["description"] = page.description

        # Add meta information to the component.
        utils.add_meta(
            component,
            **meta_args,
        )

    except Exception as e:
        if sys.version_info >= (3, 11):
            e.add_note(f"Happened while evaluating page {route!r}")
        raise
    else:
        return component


def _resolve_app_wrap_components(
    app: App,
    page_app_wrap_components: dict[tuple[int, str], Component],
) -> dict[tuple[int, str], Component]:
    """Build the full app-wrap registry for compilation.

    Args:
        app: The app being compiled.
        page_app_wrap_components: App-wrap components collected from pages.

    Returns:
        The merged app-wrap component registry.
    """
    config = get_config()

    app_wrappers: dict[tuple[int, str], Component] = {
        (0, "AppWrap"): AppWrap.create(),
    }
    app_wrappers.update(page_app_wrap_components)

    if config.react_strict_mode:
        from reflex_components_core.base.strict_mode import StrictMode

        app_wrappers[200, "StrictMode"] = StrictMode.create()

    if (toaster := app.toaster) is not None:
        from reflex_base.components.memo import memo

        @memo
        def memoized_toast_provider() -> Component:
            return toaster

        app_wrappers[44, "ToasterProvider"] = Fragment.create(memoized_toast_provider())

    for wrap_mapping in (app.app_wraps, app.extra_app_wraps):
        for key, app_wrap in wrap_mapping.items():
            component = app_wrap(app._state is not None)
            if component is not None:
                app_wrappers[key] = component

    # The page collector only walks pages, but app-wrap components have their
    # own subtrees (e.g. ``ErrorBoundary``'s fallback render). Surface their
    # Var-declared ``app_wraps`` here, fixpoint-iterating because newly added
    # wraps may themselves contain further declarations.
    pending: list[Component] = list(app_wrappers.values())
    while pending:
        next_pending: list[Component] = []
        for wrapper in pending:
            before = set(app_wrappers)
            collect_var_app_wraps_in_subtree(app_wrappers, wrapper)
            next_pending.extend(
                app_wrappers[key] for key in app_wrappers.keys() - before
            )
        pending = next_pending

    return app_wrappers


def _memoize_stateful_app_wraps(
    app_root: Component,
    compile_context: CompileContext,
) -> Component:
    """Extract stateful app wraps from the app root into memo components.

    The app root compiles outside the page plugin pipeline, so hooks from
    every wrap in the chain hoist into the single generated ``AppWrap``
    function — above the ``StateProvider`` rendered in that same function,
    where a state ``useContext`` can never resolve. Walking the assembled
    chain with the auto-memoize plugin moves each stateful wrap (and any
    stateful descendant) into its own memo module, which renders below the
    provider — the same treatment page trees get.

    Args:
        app_root: The assembled app-wrap chain from ``App._app_root``.
        compile_context: The active compile context; generated memo
            definitions are registered on ``auto_memo_components``.

    Returns:
        The app root with stateful wraps replaced by memo wrappers.
    """
    hooks = CompilerHooks(plugins=(MemoizeStatefulPlugin(),))
    page_context = PageContext(
        name="app_root",
        route=constants.PageNames.APP_ROOT,
        root_component=app_root,
    )
    compiled_root = hooks.compile_component(
        app_root,
        page_context=page_context,
        compile_context=compile_context,
    )
    if not isinstance(compiled_root, Component):
        msg = "Compiled app root must be a Component."
        raise TypeError(msg)
    return compiled_root


def _resolve_radix_themes_plugin(
    app: App,
    plugins: Sequence[Plugin],
) -> tuple[tuple[Plugin, ...], RadixThemesPlugin]:
    """Resolve the effective Radix Themes plugin for the active compile.

    Returns:
        The compiler plugin chain and the effective Radix Themes plugin.
    """
    explicit_plugin = next(
        (plugin for plugin in plugins if isinstance(plugin, RadixThemesPlugin)),
        None,
    )
    if explicit_plugin is not None:
        radix_plugin = explicit_plugin
        plugin_chain = tuple(plugins)
    else:
        radix_plugin = RadixThemesPlugin.create_implicit()
        plugin_chain = (*plugins, radix_plugin)

    if app.theme is not None:
        radix_plugin.apply_app_theme(app.theme)

    return plugin_chain, radix_plugin


def compile_app(
    app: App,
    *,
    prerender_routes: bool = False,
    dry_run: bool = False,
    use_rich: bool = True,
) -> bool:
    """Compile an app using the compiler plugin pipeline.

    Returns:
        ``True`` when a real frontend compile ran, ``False`` when the call
        short-circuited (backend-only paths that only re-evaluate pages).
    """
    from reflex_base.components.dynamic import (
        bundle_library,
        reset_bundled_libraries,
        reset_dynamic_component_imports,
    )
    from reflex_base.utils.exceptions import ReflexRuntimeError

    reset_dynamic_component_imports()
    app._apply_decorated_pages()
    app._pages = {}

    should_compile = app._should_compile()
    backend_dir = prerequisites.get_backend_dir()
    if not dry_run and not should_compile and backend_dir.exists():
        stateful_pages_marker = backend_dir / constants.Dirs.STATEFUL_PAGES
        if stateful_pages_marker.exists():
            with stateful_pages_marker.open("r") as file:
                stateful_pages = json.load(file)
            for route in stateful_pages:
                console.debug(f"BE Evaluating stateful page: {route}")
                app._compile_page(route, save_page=False)
        app._add_optional_endpoints()
        return False

    if constants.Page404.SLUG not in app._unevaluated_pages:
        app.add_page(route=constants.Page404.SLUG)

    app.style = evaluate_style_namespaces(app.style)
    config = get_config()

    if not should_compile and not dry_run:
        with console.timing("Evaluate Pages (Backend)"):
            for route in app._unevaluated_pages:
                console.debug(f"Evaluating page: {route}")
                app._compile_page(route, save_page=False)

        app._write_stateful_pages_marker()
        app._add_optional_endpoints()
        return False

    progress = (
        Progress(
            *Progress.get_default_columns()[:-1],
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        )
        if use_rich
        else console.PoorProgress()
    )
    fixed_steps = 7
    compiler_plugins, radix_themes_plugin = _resolve_radix_themes_plugin(
        app,
        config.plugins,
    )
    reset_bundled_libraries()
    # Drop cached memo wrapper classes so each compile recomputes a memo's
    # ``library`` from the current module layout (handles a module flipping to
    # a package across hot reloads).
    reset_memo_component_classes()
    for plugin in compiler_plugins:
        for dependency in plugin.get_frontend_dependencies():
            bundle_library(dependency)
    base_total = (len(app._unevaluated_pages) * 2) + fixed_steps + len(config.plugins)
    progress.start()
    task = progress.add_task("Compiling:", total=base_total)
    compile_ctx = CompileContext(
        app=app,
        pages=list(app._unevaluated_pages.values()),
        hooks=CompilerHooks(
            plugins=default_page_plugins(style=app.style, plugins=compiler_plugins)
        ),
    )

    with console.timing("Compile pages"), compile_ctx:
        compile_ctx.compile(
            evaluate_progress=lambda: progress.advance(task),
            render_progress=lambda: progress.advance(task),
        )

    for route, page_ctx in compile_ctx.compiled_pages.items():
        app._check_routes_conflict(route)
        if not isinstance(page_ctx.root_component, Component):
            msg = (
                f"Compiled page {route!r} root must be a Component before it can "
                "be registered on the app."
            )
            raise TypeError(msg)
        app._pages[route] = page_ctx.root_component

    app._evaluated_pages.update(compile_ctx.compiled_pages)
    app._stateful_pages.update(compile_ctx.stateful_routes)
    app._write_stateful_pages_marker()
    app._add_optional_endpoints()
    app._validate_var_dependencies()

    if config.show_built_with_reflex is None:
        if (
            get_compile_context() == constants.CompileContext.DEPLOY
            and prerequisites.get_user_tier() in ["pro", "team", "enterprise"]
        ):
            config.show_built_with_reflex = False
        else:
            config.show_built_with_reflex = True

    if is_prod_mode() and config.show_built_with_reflex:
        app._setup_sticky_badge()

    progress.advance(task)

    compile_results = [
        (page_ctx.output_path, page_ctx.output_code)
        for page_ctx in compile_ctx.compiled_pages.values()
        if page_ctx.output_path is not None and page_ctx.output_code is not None
    ]

    # Reinitialize vite config in case runtime options have changed.
    compile_results.append((
        constants.ReactRouter.VITE_CONFIG_FILE,
        frontend_skeleton._compile_vite_config(config),
    ))

    all_imports = compile_ctx.all_imports

    if app._state is None and any(
        code_uses_state_contexts(page_ctx.output_code or "")
        for page_ctx in compile_ctx.compiled_pages.values()
    ):
        msg = (
            "To access rx.State in frontend components, at least one "
            "subclass of rx.State must be defined in the app."
        )
        raise ReflexRuntimeError(msg)
    progress.advance(task)

    app_wrappers = _resolve_app_wrap_components(app, compile_ctx.app_wrap_components)
    app_root = _memoize_stateful_app_wraps(app._app_root(app_wrappers), compile_ctx)
    app_root_imports = app_root._get_all_imports()
    all_imports = utils.merge_imports(all_imports, app_root_imports)

    hydrate_fallback = app._resolve_hydrate_fallback()
    hydrate_fallback_export = None
    if hydrate_fallback is not None:
        hydrate_fallback._add_style_recursive(app.style)
        # Compile the fallback through the memo pipeline so it lands in its own
        # JS module; root.jsx then re-exports it as HydrateFallback.
        hydrate_fallback_definition = create_component_memo(
            hydrate_fallback, "hydrate_fallback"
        )
        compile_ctx.auto_memo_components[
            hydrate_fallback_definition.export_name, None
        ] = hydrate_fallback_definition
        hydrate_fallback_export = hydrate_fallback_definition.export_name

    memo_component_files, memo_components_imports = compile_memo_components(
        (
            *MEMOS.values(),
            *compile_ctx.auto_memo_components.values(),
        ),
    )
    compile_results.extend(memo_component_files)
    all_imports = utils.merge_imports(all_imports, memo_components_imports)
    progress.advance(task)

    compile_results.append(
        compile_document_root(
            app.head_components,
            html_lang=app.html_lang,
            html_custom_attrs=(
                {"suppressHydrationWarning": True, **app.html_custom_attrs}
                if app.html_custom_attrs
                else {"suppressHydrationWarning": True}
            ),
            default_color_mode=_resolve_default_color_mode(
                radix_themes_plugin.get_theme()
            ),
        )
    )
    progress.advance(task)

    assets_src = Path.cwd() / constants.Dirs.APP_ASSETS
    if assets_src.is_dir() and not dry_run:
        with console.timing("Copy assets"):
            path_ops.update_directory_tree(
                src=assets_src,
                dest=Path.cwd() / prerequisites.get_web_dir() / constants.Dirs.PUBLIC,
            )

    save_tasks: list[
        tuple[
            Callable[..., list[tuple[str, str]] | tuple[str, str] | None],
            tuple[Any, ...],
            dict[str, Any],
        ]
    ] = []
    modify_files_tasks: list[tuple[str, str, Callable[[str], str]]] = []

    def add_save_task(
        task_fn: Callable[..., list[tuple[str, str]] | tuple[str, str] | None],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        save_tasks.append((task_fn, args, kwargs))

    for plugin in config.plugins:
        plugin.pre_compile(
            add_save_task=add_save_task,
            add_modify_task=lambda *args, plugin=plugin: modify_files_tasks.append((
                plugin.__class__.__module__ + plugin.__class__.__name__,
                *args,
            )),
            radix_themes_plugin=radix_themes_plugin,
            unevaluated_pages=list(app._unevaluated_pages.values()),
        )

    if save_tasks:
        _set_progress_total(progress, task, base_total + len(save_tasks))

    progress.advance(task, advance=len(config.plugins))

    compile_results.append(
        compile_root_stylesheet(
            app.stylesheets,
            app.reset_style,
            plugins=compiler_plugins,
        )
    )
    progress.advance(task)

    compile_results.append(compile_theme(app.style))
    progress.advance(task)

    for task_fn, args, kwargs in save_tasks:
        result = task_fn(*args, **kwargs)
        if result is None:
            progress.advance(task)
            continue
        if isinstance(result, list):
            compile_results.extend(result)
        else:
            compile_results.append(result)
        progress.advance(task)

    compile_results.append(
        compile_contexts(app._state, radix_themes_plugin.get_theme())
    )
    progress.advance(task)

    window_library_imports = collect_window_library_imports(
        chain(
            (app_root_imports,),
            (p.frontend_imports for p in compile_ctx.compiled_pages.values()),
        )
    )
    compile_results.append(
        compile_app_root(
            app_root,
            hydrate_fallback_export=hydrate_fallback_export,
            window_library_imports=window_library_imports,
            app_root_imports=app_root_imports,
        )
    )
    progress.advance(task)

    progress.stop()

    if dry_run:
        return True

    # Delete memo files this compile no longer emits. Done here (not before the
    # dry-run return) so ``--dry`` never mutates ``.web`` or the manifest.
    utils.prune_stale_memo_files(path for path, _ in memo_component_files)

    with console.timing("Install Frontend Packages"):
        app._get_frontend_packages(all_imports)

    frontend_skeleton.update_react_router_config(
        prerender_routes=prerender_routes,
    )

    if is_prod_mode():
        purge_web_pages_dir()
    else:
        keep_files = [Path(output_path) for output_path, _ in compile_results]
        for page_file in Path(
            prerequisites.get_web_dir() / constants.Dirs.PAGES / constants.Dirs.ROUTES
        ).rglob("*"):
            if page_file.is_file() and page_file not in keep_files:
                page_file.unlink()

    frontend_skeleton.update_entry_client()

    output_mapping: dict[Path, str] = {}
    for output_path, code in compile_results:
        path = utils.resolve_path_of_web_dir(output_path)
        if path in output_mapping:
            console.warn(
                f"Path {path} has two different outputs. The last one will be used."
            )
        output_mapping[path] = code

    for plugin in config.plugins:
        for static_file_path, content in plugin.get_static_assets():
            path = utils.resolve_path_of_web_dir(static_file_path)
            if path in output_mapping:
                console.warn(
                    f"Plugin {plugin.__class__.__name__} is overwriting existing files at {path}."
                )
            output_mapping[path] = (
                content.decode("utf-8") if isinstance(content, bytes) else content
            )

    for plugin_name, file_path, modify_fn in modify_files_tasks:
        path = utils.resolve_path_of_web_dir(file_path)
        file_content = output_mapping.get(path)
        if file_content is None:
            if path.exists():
                file_content = path.read_text()
            else:
                msg = f"Plugin {plugin_name} is trying to modify {path} but it does not exist."
                raise FileNotFoundError(msg)
        output_mapping[path] = modify_fn(file_content)

    with console.timing("Write to Disk"):
        for output_path, code in output_mapping.items():
            utils.write_file(output_path, code)

    return True
