"""Compiler for the reflex apps."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Sequence
from inspect import getmodule
from pathlib import Path
from typing import TYPE_CHECKING

from reflex import constants
from reflex.compiler import templates, utils
from reflex.components.base.fragment import Fragment
from reflex.components.component import (
    BaseComponent,
    Component,
    ComponentStyle,
    CustomComponent,
    StatefulComponent,
)
from reflex.config import get_config
from reflex.constants.compiler import PageNames, ResetStylesheet
from reflex.constants.state import FIELD_MARKER
from reflex.environment import environment
from reflex.state import BaseState
from reflex.style import SYSTEM_COLOR_MODE
from reflex.utils import console, path_ops
from reflex.utils.exceptions import ReflexError
from reflex.utils.exec import is_prod_mode
from reflex.utils.format import to_title_case
from reflex.utils.imports import ImportVar
from reflex.utils.prerequisites import get_web_dir
from reflex.vars.base import LiteralVar, Var


def _apply_common_imports(
    imports: dict[str, list[ImportVar]],
):
    imports.setdefault("@emotion/react", []).append(ImportVar("jsx"))
    imports.setdefault("react", []).extend(
        [ImportVar("Fragment"), ImportVar("useEffect")],
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
    return templates.DOCUMENT_ROOT.render(
        imports=utils.compile_imports(document_root_imports),
        document=root.render(),
    )


def _normalize_library_name(lib: str) -> str:
    """Normalize the library name.

    Args:
        lib: The library name to normalize.

    Returns:
        The normalized library name.
    """
    if lib == "react":
        return "React"
    return lib.replace("$/", "").replace("@", "").replace("/", "_").replace("-", "_")


def _compile_app(app_root: Component) -> str:
    """Compile the app template component.

    Args:
        app_root: The app root to compile.

    Returns:
        The compiled app.
    """
    from reflex.components.dynamic import bundled_libraries

    window_libraries = [
        (_normalize_library_name(name), name) for name in bundled_libraries
    ]

    window_libraries_deduped = list(dict.fromkeys(window_libraries))

    app_root_imports = app_root._get_all_imports()
    _apply_common_imports(app_root_imports)

    return templates.APP_ROOT.render(
        imports=utils.compile_imports(app_root_imports),
        custom_codes=app_root._get_all_custom_code(),
        hooks=app_root._get_all_hooks(),
        window_libraries=window_libraries_deduped,
        render=app_root.render(),
        dynamic_imports=app_root._get_all_dynamic_imports(),
    )


def _compile_theme(theme: str) -> str:
    """Compile the theme.

    Args:
        theme: The theme to compile.

    Returns:
        The compiled theme.
    """
    return templates.THEME.render(theme=theme)


def _compile_contexts(state: type[BaseState] | None, theme: Component | None) -> str:
    """Compile the initial state and contexts.

    Args:
        state: The app state.
        theme: The top-level app theme.

    Returns:
        The compiled context file.
    """
    appearance = getattr(theme, "appearance", None)
    if appearance is None or str(LiteralVar.create(appearance)) == '"inherit"':
        appearance = LiteralVar.create(SYSTEM_COLOR_MODE)

    return (
        templates.CONTEXT.render(
            initial_state=utils.compile_state(state),
            state_name=state.get_name(),
            client_storage=utils.compile_client_storage(state),
            is_dev_mode=not is_prod_mode(),
            default_color_mode=appearance,
        )
        if state
        else templates.CONTEXT.render(
            is_dev_mode=not is_prod_mode(),
            default_color_mode=appearance,
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
    return templates.PAGE.render(
        imports=imports,
        dynamic_imports=component._get_all_dynamic_imports(),
        custom_codes=component._get_all_custom_code(),
        hooks=component._get_all_hooks(),
        render=component.render(),
    )


def compile_root_stylesheet(
    stylesheets: list[str], reset_style: bool = True
) -> tuple[str, str]:
    """Compile the root stylesheet.

    Args:
        stylesheets: The stylesheets to include in the root stylesheet.
        reset_style: Whether to include CSS reset for margin and padding.

    Returns:
        The path and code of the compiled root stylesheet.
    """
    output_path = utils.get_root_stylesheet_path()

    code = _compile_root_stylesheet(stylesheets, reset_style)

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
            stylesheet_full_path.absolute()
            .relative_to(assets_app_path.absolute())
            .parts
        )
        == 1
        and stylesheet_full_path.stem == PageNames.STYLESHEET_ROOT
    ):
        msg = f"Stylesheet file name cannot be '{PageNames.STYLESHEET_ROOT}': {stylesheet_full_path}"
        raise ValueError(msg)


RADIX_THEMES_STYLESHEET = "@radix-ui/themes/styles.css"


def _compile_root_stylesheet(stylesheets: list[str], reset_style: bool = True) -> str:
    """Compile the root stylesheet.

    Args:
        stylesheets: The stylesheets to include in the root stylesheet.
        reset_style: Whether to include CSS reset for margin and padding.

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

    sheets.extend(
        [RADIX_THEMES_STYLESHEET]
        + [
            sheet
            for plugin in get_config().plugins
            for sheet in plugin.get_stylesheet_paths()
        ]
    )

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

    return templates.STYLE.render(stylesheets=sheets)


def _compile_component(component: Component | StatefulComponent) -> str:
    """Compile a single component.

    Args:
        component: The component to compile.

    Returns:
        The compiled component.
    """
    return templates.COMPONENT.render(component=component)


def _compile_components(
    components: Iterable[CustomComponent],
) -> tuple[str, dict[str, list[ImportVar]]]:
    """Compile the components.

    Args:
        components: The components to compile.

    Returns:
        The compiled components.
    """
    imports = {
        "react": [ImportVar(tag="memo")],
        f"$/{constants.Dirs.STATE_PATH}": [ImportVar(tag="isTrue")],
    }
    component_renders = []

    # Compile each component.
    for component in components:
        component_render, component_imports = utils.compile_custom_component(component)
        component_renders.append(component_render)
        imports = utils.merge_imports(imports, component_imports)

    _apply_common_imports(imports)

    dynamic_imports = {
        comp_import: None
        for comp_render in component_renders
        if "dynamic_imports" in comp_render
        for comp_import in comp_render["dynamic_imports"]
    }

    custom_codes = {
        comp_custom_code: None
        for comp_render in component_renders
        for comp_custom_code in comp_render.get("custom_code", [])
    }

    # Compile the components page.
    return (
        templates.COMPONENTS.render(
            imports=utils.compile_imports(imports),
            components=component_renders,
            dynamic_imports=dynamic_imports,
            custom_codes=custom_codes,
        ),
        imports,
    )


def _compile_stateful_components(
    page_components: list[BaseComponent],
) -> str:
    """Walk the page components and extract shared stateful components.

    Any StatefulComponent that is shared by more than one page will be rendered
    to a separate module and marked rendered_as_shared so subsequent
    renderings will import the component from the shared module instead of
    directly including the code for it.

    Args:
        page_components: The Components or StatefulComponents to compile.

    Returns:
        The rendered stateful components code.
    """
    all_import_dicts = []
    rendered_components = {}

    def get_shared_components_recursive(component: BaseComponent):
        """Get the shared components for a component and its children.

        A shared component is a StatefulComponent that appears in 2 or more
        pages and is a candidate for writing to a common file and importing
        into each page where it is used.

        Args:
            component: The component to collect shared StatefulComponents for.
        """
        for child in component.children:
            # Depth-first traversal.
            get_shared_components_recursive(child)

        # When the component is referenced by more than one page, render it
        # to be included in the STATEFUL_COMPONENTS module.
        # Skip this step in dev mode, thereby avoiding potential hot reload errors for larger apps
        if (
            isinstance(component, StatefulComponent)
            and component.references > 1
            and is_prod_mode()
        ):
            # Reset this flag to render the actual component.
            component.rendered_as_shared = False

            # Include dynamic imports in the shared component.
            if dynamic_imports := component._get_all_dynamic_imports():
                rendered_components.update(dict.fromkeys(dynamic_imports))

            # Include custom code in the shared component.
            rendered_components.update(
                dict.fromkeys(component._get_all_custom_code(export=True)),
            )

            # Include all imports in the shared component.
            all_import_dicts.append(component._get_all_imports())

            # Indicate that this component now imports from the shared file.
            component.rendered_as_shared = True

    for page_component in page_components:
        get_shared_components_recursive(page_component)

    # Don't import from the file that we're about to create.
    all_imports = utils.merge_imports(*all_import_dicts)
    all_imports.pop(
        f"$/{constants.Dirs.UTILS}/{constants.PageNames.STATEFUL_COMPONENTS}", None
    )
    if rendered_components:
        _apply_common_imports(all_imports)

    return templates.STATEFUL_COMPONENTS.render(
        imports=utils.compile_imports(all_imports),
        memoized_code="\n".join(rendered_components),
    )


def compile_document_root(
    head_components: list[Component],
    html_lang: str | None = None,
    html_custom_attrs: dict[str, Var | str] | None = None,
) -> tuple[str, str]:
    """Compile the document root.

    Args:
        head_components: The components to include in the head.
        html_lang: The language of the document, will be added to the html root element.
        html_custom_attrs: custom attributes added to the html root element.

    Returns:
        The path and code of the compiled document root.
    """
    # Get the path for the output file.
    output_path = str(
        get_web_dir() / constants.Dirs.PAGES / constants.PageNames.DOCUMENT_ROOT
    )

    # Create the document root.
    document_root = utils.create_document_root(
        head_components, html_lang=html_lang, html_custom_attrs=html_custom_attrs
    )

    # Compile the document root.
    code = _compile_document_root(document_root)
    return output_path, code


def compile_app(app_root: Component) -> tuple[str, str]:
    """Compile the app root.

    Args:
        app_root: The app root component to compile.

    Returns:
        The path and code of the compiled app wrapper.
    """
    # Get the path for the output file.
    output_path = str(
        get_web_dir() / constants.Dirs.PAGES / constants.PageNames.APP_ROOT
    )

    # Compile the document root.
    code = _compile_app(app_root)
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


def compile_components(
    components: Iterable[CustomComponent],
) -> tuple[str, str, dict[str, list[ImportVar]]]:
    """Compile the custom components.

    Args:
        components: The custom components to compile.

    Returns:
        The path and code of the compiled components.
    """
    # Get the path for the output file.
    output_path = utils.get_components_path()

    # Compile the components.
    code, imports = _compile_components(components)
    return output_path, code, imports


def compile_stateful_components(
    pages: Iterable[Component],
    progress_function: Callable[[], None],
) -> tuple[str, str, list[BaseComponent]]:
    """Separately compile components that depend on State vars.

    StatefulComponents are compiled as their own component functions with their own
    useContext declarations, which allows page components to be stateless and avoid
    re-rendering along with parts of the page that actually depend on state.

    Args:
        pages: The pages to extract stateful components from.
        progress_function: A function to call to indicate progress, called once per page.

    Returns:
        The path and code of the compiled stateful components.
    """
    output_path = utils.get_stateful_components_path()

    page_components = []
    for page in pages:
        # Compile the stateful components
        page_component = StatefulComponent.compile_from(page) or page
        progress_function()
        page_components.append(page_component)

    code = _compile_stateful_components(page_components)
    return output_path, code, page_components


def purge_web_pages_dir():
    """Empty out .web/pages directory."""
    if not is_prod_mode() and environment.REFLEX_PERSIST_WEB_DIR.get():
        # Skip purging the web directory in dev mode if REFLEX_PERSIST_WEB_DIR is set.
        return

    # Empty out the web pages directory.
    utils.empty_dir(get_web_dir() / constants.Dirs.PAGES, keep_files=["routes.js"])


if TYPE_CHECKING:
    from reflex.app import ComponentCallable, UnevaluatedPage


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
            if message.endswith(
                (
                    "indices must be integers or slices, not NumberCastedVar",
                    "indices must be integers or slices, not BooleanCastedVar",
                )
            ):
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

        from reflex.utils.format import make_default_page_title

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


class ExecutorSafeFunctions:
    """Helper class to allow parallelisation of parts of the compilation process.

    This class (and its class attributes) are available at global scope.

    In a multiprocessing context (like when using a ProcessPoolExecutor), the content of this
    global class is logically replicated to any FORKED process.

    How it works:
    * Before the child process is forked, ensure that we stash any input data required by any future
      function call in the child process.
    * After the child process is forked, the child process will have a copy of the global class, which
      includes the previously stashed input data.
    * Any task submitted to the child process simply needs a way to communicate which input data the
      requested function call requires.

    Why do we need this? Passing input data directly to child process often not possible because the input data is not picklable.
    The mechanic described here removes the need to pickle the input data at all.

    Limitations:
    * This can never support returning unpicklable OUTPUT data.
    * Any object mutations done by the child process will not propagate back to the parent process (fork goes one way!).

    """

    COMPONENTS: dict[str, BaseComponent] = {}
    UNCOMPILED_PAGES: dict[str, UnevaluatedPage] = {}

    @classmethod
    def compile_page(cls, route: str) -> tuple[str, str]:
        """Compile a page.

        Args:
            route: The route of the page to compile.

        Returns:
            The path and code of the compiled page.
        """
        return compile_page(route, cls.COMPONENTS[route])

    @classmethod
    def compile_unevaluated_page(
        cls,
        route: str,
        style: ComponentStyle,
        theme: Component | None,
    ) -> tuple[str, Component, tuple[str, str]]:
        """Compile an unevaluated page.

        Args:
            route: The route of the page to compile.
            style: The style of the page.
            theme: The theme of the page.

        Returns:
            The route, compiled component, and compiled page.
        """
        component = compile_unevaluated_page(
            route, cls.UNCOMPILED_PAGES[route], style, theme
        )
        return route, component, compile_page(route, component)

    @classmethod
    def compile_theme(cls, style: ComponentStyle | None) -> tuple[str, str]:
        """Compile the theme.

        Args:
            style: The style to compile.

        Returns:
            The path and code of the compiled theme.

        Raises:
            ValueError: If the style is not set.
        """
        if style is None:
            msg = "STYLE should be set"
            raise ValueError(msg)
        return compile_theme(style)
