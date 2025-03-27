"""Compiler for the reflex apps."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Sequence, Type

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
from reflex.config import environment, get_config
from reflex.state import BaseState
from reflex.style import SYSTEM_COLOR_MODE
from reflex.utils import console, path_ops
from reflex.utils.exceptions import ReflexError
from reflex.utils.exec import is_prod_mode
from reflex.utils.imports import ImportVar
from reflex.utils.prerequisites import get_web_dir
from reflex.vars.base import LiteralVar, Var


def _compile_document_root(root: Component) -> str:
    """Compile the document root.

    Args:
        root: The document root to compile.

    Returns:
        The compiled document root.
    """
    return templates.DOCUMENT_ROOT.render(
        imports=utils.compile_imports(root._get_all_imports()),
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
    return lib.replace("@", "").replace("/", "_").replace("-", "_")


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
    ] + [
        ("utils_context", f"$/{constants.Dirs.UTILS}/context"),
        ("utils_state", f"$/{constants.Dirs.UTILS}/state"),
    ]

    return templates.APP_ROOT.render(
        imports=utils.compile_imports(app_root._get_all_imports()),
        custom_codes=app_root._get_all_custom_code(),
        hooks=app_root._get_all_hooks(),
        window_libraries=window_libraries,
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


def _compile_contexts(state: Type[BaseState] | None, theme: Component | None) -> str:
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

    last_compiled_time = str(datetime.now())
    return (
        templates.CONTEXT.render(
            initial_state=utils.compile_state(state),
            state_name=state.get_name(),
            client_storage=utils.compile_client_storage(state),
            is_dev_mode=not is_prod_mode(),
            last_compiled_time=last_compiled_time,
            default_color_mode=appearance,
        )
        if state
        else templates.CONTEXT.render(
            is_dev_mode=not is_prod_mode(),
            default_color_mode=appearance,
            last_compiled_time=last_compiled_time,
        )
    )


def _compile_page(
    component: BaseComponent,
    state: Type[BaseState] | None,
) -> str:
    """Compile the component given the app state.

    Args:
        component: The component to compile.
        state: The app state.

    Returns:
        The compiled component.
    """
    imports = component._get_all_imports()
    imports = utils.compile_imports(imports)

    # Compile the code to render the component.
    kwargs = {"state_name": state.get_name()} if state is not None else {}

    return templates.PAGE.render(
        imports=imports,
        dynamic_imports=component._get_all_dynamic_imports(),
        custom_codes=component._get_all_custom_code(),
        hooks=component._get_all_hooks(),
        render=component.render(),
        **kwargs,
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

    failed_to_import_sass = False
    for stylesheet in stylesheets:
        if not utils.is_valid_url(stylesheet):
            # check if stylesheet provided exists.
            assets_app_path = Path.cwd() / constants.Dirs.APP_ASSETS
            stylesheet_full_path = assets_app_path / stylesheet.strip("/")

            if not stylesheet_full_path.exists():
                raise FileNotFoundError(
                    f"The stylesheet file {stylesheet_full_path} does not exist."
                )

            if stylesheet_full_path.is_dir():
                # NOTE: this can create an infinite loop, for example:
                # assets/
                #   | dir_a/
                #   |   | dir_c/ (symlink to "assets/dir_a")
                #   | dir_b/
                # so to avoid the infinite loop, we don't include symbolic links
                stylesheets += [
                    str(p.relative_to(assets_app_path))
                    for p in stylesheet_full_path.iterdir()
                    if not (p.is_symlink() and p.is_dir())
                ]
                continue

            if (
                stylesheet_full_path.suffix[1:].lower()
                in constants.Reflex.STYLESHEETS_SUPPORTED
            ):
                target = (
                    get_web_dir()
                    / constants.Dirs.STYLES
                    / (stylesheet.rsplit(".", 1)[0].strip("/") + ".css")
                )
                target.parent.mkdir(parents=True, exist_ok=True)

                if stylesheet_full_path.suffix == ".css":
                    path_ops.cp(src=stylesheet_full_path, dest=target, overwrite=True)
                else:
                    try:
                        from sass import compile as sass_compile

                        target.write_text(
                            data=sass_compile(
                                filename=str(stylesheet_full_path),
                                output_style="compressed",
                            ),
                            encoding="utf8",
                        )
                    except ImportError:
                        failed_to_import_sass = True
            else:
                raise FileNotFoundError(
                    f'The stylesheet file "{stylesheet_full_path}" is not a valid file.'
                )

            stylesheet = f"./{stylesheet.rsplit('.', 1)[0].strip('/')}.css"

        sheets.append(stylesheet) if stylesheet not in sheets else None

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
    components: set[CustomComponent],
) -> tuple[str, dict[str, list[ImportVar]]]:
    """Compile the components.

    Args:
        components: The components to compile.

    Returns:
        The compiled components.
    """
    imports = {
        "react": [ImportVar(tag="memo")],
        f"$/{constants.Dirs.STATE_PATH}": [ImportVar(tag="E"), ImportVar(tag="isTrue")],
    }
    component_renders = []

    # Compile each component.
    for component in components:
        component_render, component_imports = utils.compile_custom_component(component)
        component_renders.append(component_render)
        imports = utils.merge_imports(imports, component_imports)

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
                dict.fromkeys(component._get_all_custom_code()),
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

    return templates.STATEFUL_COMPONENTS.render(
        imports=utils.compile_imports(all_imports),
        memoized_code="\n".join(rendered_components),
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
    output_path = utils.get_page_path(constants.PageNames.DOCUMENT_ROOT)

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
    output_path = utils.get_page_path(constants.PageNames.APP_ROOT)

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
    state: Type[BaseState] | None,
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


def compile_page(
    path: str, component: BaseComponent, state: Type[BaseState] | None
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


def compile_components(
    components: set[CustomComponent],
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
) -> tuple[str, str, list[BaseComponent]]:
    """Separately compile components that depend on State vars.

    StatefulComponents are compiled as their own component functions with their own
    useContext declarations, which allows page components to be stateless and avoid
    re-rendering along with parts of the page that actually depend on state.

    Args:
        pages: The pages to extract stateful components from.

    Returns:
        The path and code of the compiled stateful components.
    """
    output_path = utils.get_stateful_components_path()

    # Compile the stateful components.
    page_components = [StatefulComponent.compile_from(page) or page for page in pages]
    code = _compile_stateful_components(page_components)
    return output_path, code, page_components


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
    output_path = str((get_web_dir() / constants.Tailwind.CONFIG).absolute())

    # Compile the config.
    code = _compile_tailwind(config)
    return output_path, code


def remove_tailwind_from_postcss() -> tuple[str, str]:
    """If tailwind is not to be used, remove it from postcss.config.js.

    Returns:
        The path and code of the compiled postcss.config.js.
    """
    # Get the path for the output file.
    output_path = str(get_web_dir() / constants.Dirs.POSTCSS_JS)

    code = [
        line
        for line in Path(output_path).read_text().splitlines(keepends=True)
        if "tailwindcss: " not in line
    ]

    # Compile the config.
    return output_path, "".join(code)


def purge_web_pages_dir():
    """Empty out .web/pages directory."""
    if not is_prod_mode() and environment.REFLEX_PERSIST_WEB_DIR.get():
        # Skip purging the web directory in dev mode if REFLEX_PERSIST_WEB_DIR is set.
        return

    # Empty out the web pages directory.
    utils.empty_dir(get_web_dir() / constants.Dirs.PAGES, keep_files=["_app.js"])


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
    try:
        if (
            callable(component)
            and (converted := _into_component_once(component())) is not None
        ):
            return converted
    except KeyError as e:
        if isinstance(e, ReflexError):
            raise
        key = e.args[0] if e.args else None
        if key is not None and isinstance(key, Var):
            raise TypeError(
                "Cannot access a primitive map with a Var. Consider calling rx.Var.create() on the map."
            ).with_traceback(e.__traceback__) from None
        raise
    except TypeError as e:
        if isinstance(e, ReflexError):
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
                "indices must be integers or slices, not NumberCastedVar"
            ) or message.endswith(
                "indices must be integers or slices, not BooleanCastedVar"
            ):
                raise TypeError(
                    "Cannot index into a primitive sequence with a Var. Consider calling rx.Var.create() on the sequence."
                ).with_traceback(e.__traceback__) from None
        if "CastedVar" in str(e):
            raise TypeError(
                "Cannot pass a Var to a built-in function. Consider moving the operation to the backend, using existing Var operations, or defining a custom Var operation."
            ).with_traceback(e.__traceback__) from None
        raise

    raise TypeError(f"Expected a Component, got {type(component)}")


def compile_unevaluated_page(
    route: str,
    page: UnevaluatedPage,
    state: Type[BaseState] | None = None,
    style: ComponentStyle | None = None,
    theme: Component | None = None,
) -> tuple[Component, bool]:
    """Compiles an uncompiled page into a component and adds meta information.

    Args:
        route: The route of the page.
        page: The uncompiled page object.
        state: The state of the app.
        style: The style of the page.
        theme: The theme of the page.

    Returns:
        The compiled component and whether state should be enabled.
    """
    # Generate the component if it is a callable.
    component = into_component(page.component)

    component._add_style_recursive(style or {}, theme)

    enable_state = False
    # Ensure state is enabled if this page uses state.
    if state is None:
        if page.on_load or component._has_stateful_event_triggers():
            enable_state = True
        else:
            for var in component._get_vars(include_children=True):
                var_data = var._get_all_var_data()
                if not var_data:
                    continue
                if not var_data.state:
                    continue
                enable_state = True
                break

    from reflex.app import OverlayFragment
    from reflex.utils.format import make_default_page_title

    component = OverlayFragment.create(component)

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

    return component, enable_state


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
    STATE: Type[BaseState] | None = None

    @classmethod
    def compile_page(cls, route: str) -> tuple[str, str]:
        """Compile a page.

        Args:
            route: The route of the page to compile.

        Returns:
            The path and code of the compiled page.
        """
        return compile_page(route, cls.COMPONENTS[route], cls.STATE)

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
        component, enable_state = compile_unevaluated_page(
            route, cls.UNCOMPILED_PAGES[route], cls.STATE, style, theme
        )
        return route, component, compile_page(route, component, cls.STATE)

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
            raise ValueError("STYLE should be set")
        return compile_theme(style)
