"""Components that are dynamically generated on the backend."""

from typing import TYPE_CHECKING, Any, Union

from reflex_base import constants
from reflex_base.registry import RegistrationContext, _default_bundled_libraries
from reflex_base.utils import console, imports
from reflex_base.utils.exceptions import DynamicComponentMissingLibraryError
from reflex_base.utils.format import format_library_name
from reflex_base.utils.serializers import serializer
from reflex_base.vars import Var, get_unique_variable_name
from reflex_base.vars.base import VarData, transform

if TYPE_CHECKING:
    from reflex_base.components.component import Component


def __getattr__(name: str) -> Any:
    """Provide the module-level globals that moved onto `RegistrationContext`.

    Kept so downstream packages pinned to an older Reflex (notably
    reflex-enterprise, which reads `dynamic.bundled_libraries`) keep working.

    Args:
        name: The name of the attribute to look up.

    Returns:
        The relocated value, resolved against the active `RegistrationContext`.

    Raises:
        AttributeError: If the attribute is not a relocated global.
    """
    if name == "bundled_libraries":
        console.deprecate(
            feature_name="reflex_base.components.dynamic.bundled_libraries",
            reason=(
                "The bundled library list now lives on the active RegistrationContext. "
                "Use RegistrationContext.ensure_context().bundled_libraries to read it, "
                "or bundle_library()/reset_bundled_libraries() to modify it"
            ),
            deprecation_version="0.9.9",
            removal_version="1.0",
        )
        return RegistrationContext.ensure_context().bundled_libraries
    if name == "DEFAULT_BUNDLED_LIBRARIES":
        console.deprecate(
            feature_name="reflex_base.components.dynamic.DEFAULT_BUNDLED_LIBRARIES",
            reason=(
                "Every RegistrationContext starts with these libraries bundled; call "
                "reset_bundled_libraries() to restore them on the active context"
            ),
            deprecation_version="0.9.9",
            removal_version="1.0",
        )
        return _default_bundled_libraries()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def get_cdn_url(lib: str) -> str:
    """Get the CDN URL for a library.

    Args:
        lib: The library to get the CDN URL for.

    Returns:
        The CDN URL for the library.
    """
    return f"https://cdn.jsdelivr.net/npm/{lib}" + "/+esm"


def reset_bundled_libraries() -> None:
    """Reset the bundled library registry to its default values."""
    context = RegistrationContext.ensure_context()
    context.bundled_libraries[:] = _default_bundled_libraries()
    context._explicit_bundled_libraries.clear()


def _reset_bundled_libraries_for_compile() -> None:
    """Clear compiler-derived libraries while retaining app registrations."""
    context = RegistrationContext.ensure_context()
    libraries = dict.fromkeys(_default_bundled_libraries())
    libraries.update(context._explicit_bundled_libraries)
    context.bundled_libraries[:] = libraries


def bundle_library(component: Union["Component", str]) -> None:
    """Register a library for dynamic components.

    Explicit app registrations survive compilation, including registrations in
    modules first imported while evaluating a page. Passing a component bundles
    its rendered library imports, including subpaths, even when it is absent
    from the initial state.

    Args:
        component: The component to bundle the library with.

    Raises:
        DynamicComponentMissingLibraryError: Raised when a dynamic component is missing a library.
    """
    if isinstance(component, str):
        _bundle_library(component, explicit=True)
        return
    component_imports = component._get_imports()
    if not component_imports:
        msg = "Component must have a library to bundle."
        raise DynamicComponentMissingLibraryError(msg)
    for library, fields in component_imports.items():
        if not library:
            continue
        library = format_library_name(library)
        for field in fields:
            if field.render:
                subpath = field.package_path if field.package_path != "/" else ""
                _bundle_library(library + subpath, explicit=True)


def _bundle_library(library: str, *, explicit: bool = False) -> None:
    """Register a library, optionally retaining it across compiler resets.

    Args:
        library: The library or subpath to bundle.
        explicit: Whether this registration belongs to the app rather than a compile.
    """
    library = format_library_name(library)
    context = RegistrationContext.ensure_context()
    if explicit:
        context._explicit_bundled_libraries[library] = None
    if library not in context.bundled_libraries:
        context.bundled_libraries.append(library)


def load_dynamic_serializer():
    """Load the serializer for dynamic components."""
    # Causes a circular import, so we import here.
    from reflex_base.components.component import Component

    @serializer
    def make_component(component: Component) -> str:
        """Generate the code for a dynamic component.

        Args:
            component: The component to generate code for.

        Returns:
            The generated code
        """
        # Causes a circular import, so we import here.
        from reflex_components_core.base.bare import Bare

        from reflex.compiler import compiler, templates, utils

        libs_in_window = RegistrationContext.ensure_context().bundled_libraries

        component = Bare.create(Var.create(component))

        rendered_components = {}
        # Include dynamic imports in the shared component.
        if dynamic_imports := component._get_all_dynamic_imports():
            rendered_components.update(dict.fromkeys(dynamic_imports))

        # Include custom code in the shared component.
        rendered_components.update(component._get_all_custom_code())

        rendered_components[
            templates.dynamic_component_template(
                tag_name="MySSRComponent",
                component=component,
                export=True,
            )
        ] = None

        component_imports = component._get_all_imports()
        compiler._apply_common_imports(component_imports)

        imports = {}
        bundled_subpaths: set[str] = set()
        for lib, names in component_imports.items():
            formatted_lib_name = format_library_name(lib)
            root_is_bundled = formatted_lib_name in libs_in_window
            fallback = (
                lib
                if root_is_bundled or lib.startswith((".", "/", "$/", "http"))
                else get_cdn_url(lib)
            )
            for name in names:
                subpath = name.package_path if name.package_path != "/" else ""
                import_path = formatted_lib_name + subpath
                is_bundled = root_is_bundled or import_path in libs_in_window
                imports.setdefault(lib if is_bundled else fallback, []).append(name)
                if subpath and is_bundled:
                    _bundle_library(import_path)
                    bundled_subpaths.add(import_path)

        module_imports = []
        bundled_declarations = []
        for module in utils.compile_imports(imports):
            if module["lib"] not in bundled_subpaths:
                module_imports.append(module)
                continue

            window_library = f"window.__reflex['{module['lib']}']"
            if module["default"]:
                bundled_declarations.append(
                    f"const {module['default']} = {window_library}.default"
                )
            named_imports = []
            for name in module["rest"]:
                if name.startswith("* as "):
                    bundled_declarations.append(
                        f"const {name.removeprefix('* as ')} = {window_library}"
                    )
                else:
                    named_imports.append(name.replace(" as ", ": "))
            if named_imports:
                bundled_declarations.append(
                    f"const {{{','.join(named_imports)}}} = {window_library}"
                )
        bundled_declarations.extend(rendered_components)

        module_code_lines = templates.dynamic_components_module_template(
            imports=module_imports,
            memoized_code="\n".join(bundled_declarations),
        ).splitlines()

        # Rewrite imports from `/` to destructure from window
        for ix, line in enumerate(module_code_lines[:]):
            if line.startswith("import "):
                if 'from "$/' in line or 'from "/' in line:
                    module_code_lines[ix] = (
                        line
                        .replace("import ", "const ", 1)
                        .replace(" as ", ": ")
                        .replace(" from ", " = window['__reflex'][", 1)
                        + "]"
                    )
                else:
                    for lib in libs_in_window:
                        if f'from "{lib}"' in line:
                            module_code_lines[ix] = (
                                line
                                .replace("import ", "const ", 1)
                                .replace(
                                    f' from "{lib}"', f" = window.__reflex['{lib}']", 1
                                )
                                .replace(" as ", ": ")
                            )
            if line.startswith("export function"):
                module_code_lines[ix] = line.replace(
                    "export function", "export default function", 1
                )
            line_stripped = line.strip()
            if line_stripped.startswith("{") and line_stripped.endswith("}"):
                module_code_lines[ix] = line_stripped[1:-1]

        module_code_lines.insert(0, "const React = window.__reflex.react;")

        function_line = next(
            index
            for index, line in enumerate(module_code_lines)
            if line.startswith("export default function")
        )

        module_code_lines = [
            line
            for _, line in sorted(
                enumerate(module_code_lines),
                key=lambda x: (
                    not (x[1].startswith("import ") and x[0] < function_line),
                    x[0],
                ),
            )
        ]

        return "\n".join([
            "//__reflex_evaluate",
            *module_code_lines,
        ])

    @transform
    def evaluate_component(js_string: Var[str]) -> Var[Component]:
        """Evaluate a component.

        Args:
            js_string: The JavaScript string to evaluate.

        Returns:
            The evaluated JavaScript string.
        """
        unique_var_name = get_unique_variable_name()

        return js_string._replace(
            _js_expr=unique_var_name,
            _var_type=Component,
            merge_var_data=VarData.merge(
                VarData(
                    imports={
                        f"$/{constants.Dirs.STATE_PATH}": [
                            imports.ImportVar(tag="evalReactComponent"),
                        ],
                        "react": [
                            imports.ImportVar(tag="createElement"),
                            imports.ImportVar(tag="useState"),
                            imports.ImportVar(tag="useEffect"),
                        ],
                    },
                    hooks={
                        f"const [{unique_var_name}, set_{unique_var_name}] = useState(null);": None,
                        "useEffect(() => {"
                        "let isMounted = true;"
                        f"evalReactComponent({js_string!s})"
                        ".then((component) => {"
                        "if (isMounted) {"
                        f"set_{unique_var_name}(() => createElement(component));"
                        "}"
                        "});"
                        "return () => {"
                        "isMounted = false;"
                        "};"
                        "}"
                        f", [{js_string!s}]);": None,
                    },
                ),
            ),
        )
