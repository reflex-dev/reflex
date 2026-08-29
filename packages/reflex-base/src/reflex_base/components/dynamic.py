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
    bundled = RegistrationContext.ensure_context().bundled_libraries
    bundled[:] = _default_bundled_libraries()


def bundle_library(component: Union["Component", str]):
    """Bundle a library with the component.

    Args:
        component: The component to bundle the library with.

    Raises:
        DynamicComponentMissingLibraryError: Raised when a dynamic component is missing a library.
    """
    bundled = RegistrationContext.ensure_context().bundled_libraries
    if isinstance(component, str):
        bundled.append(format_library_name(component))
        return
    if component.library is None:
        msg = "Component must have a library to bundle."
        raise DynamicComponentMissingLibraryError(msg)
    bundled.append(format_library_name(component.library))


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
        for lib, names in component_imports.items():
            formatted_lib_name = format_library_name(lib)
            if (
                not lib.startswith((".", "/", "$/"))
                and not lib.startswith("http")
                and formatted_lib_name not in libs_in_window
            ):
                imports[get_cdn_url(lib)] = names
            else:
                imports[lib] = names

        module_code_lines = templates.dynamic_components_module_template(
            imports=utils.compile_imports(imports),
            memoized_code="\n".join(rendered_components),
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
