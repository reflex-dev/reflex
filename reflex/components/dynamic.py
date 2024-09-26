"""Components that are dynamically generated on the backend."""

from reflex import constants
from reflex.utils import imports
from reflex.utils.serializers import serializer
from reflex.vars import Var, get_unique_variable_name
from reflex.vars.base import VarData, transform


def get_cdn_url(lib: str) -> str:
    """Get the CDN URL for a library.

    Args:
        lib: The library to get the CDN URL for.

    Returns:
        The CDN URL for the library.
    """
    return f"https://cdn.jsdelivr.net/npm/{lib}" + "/+esm"


def load_dynamic_serializer():
    """Load the serializer for dynamic components."""
    # Causes a circular import, so we import here.
    from reflex.components.component import Component

    @serializer
    def make_component(component: Component) -> str:
        """Generate the code for a dynamic component.

        Args:
            component: The component to generate code for.

        Returns:
            The generated code
        """
        # Causes a circular import, so we import here.
        from reflex.compiler import templates, utils

        rendered_components = {}
        # Include dynamic imports in the shared component.
        if dynamic_imports := component._get_all_dynamic_imports():
            rendered_components.update(
                {dynamic_import: None for dynamic_import in dynamic_imports}
            )

        # Include custom code in the shared component.
        rendered_components.update(
            {code: None for code in component._get_all_custom_code()},
        )

        rendered_components[
            templates.STATEFUL_COMPONENT.render(
                tag_name="MySSRComponent",
                memo_trigger_hooks=[],
                component=component,
            )
        ] = None

        libs_in_window = [
            "react",
            "@radix-ui/themes",
        ]

        imports = {}
        for lib, names in component._get_all_imports().items():
            if (
                not lib.startswith((".", "/"))
                and not lib.startswith("http")
                and all(
                    not lib.startswith(lib_in_window)
                    for lib_in_window in libs_in_window
                )
            ):
                imports[get_cdn_url(lib)] = names
            else:
                imports[lib] = names

        module_code_lines = templates.STATEFUL_COMPONENTS.render(
            imports=utils.compile_imports(imports),
            memoized_code="\n".join(rendered_components),
        ).splitlines()[1:]

        # Rewrite imports from `/` to destructure from window
        for ix, line in enumerate(module_code_lines[:]):
            if line.startswith("import "):
                if 'from "/' in line:
                    module_code_lines[ix] = (
                        line.replace("import ", "const ", 1).replace(
                            " from ", " = window['__reflex'][", 1
                        )
                        + "]"
                    )
                else:
                    for lib in libs_in_window:
                        if f'from "{lib}"' in line:
                            module_code_lines[ix] = (
                                line.replace("import ", "const ", 1)
                                .replace(
                                    f' from "{lib}"', f" = window.__reflex['{lib}']", 1
                                )
                                .replace(" as ", ": ")
                            )
            if line.startswith("export function"):
                module_code_lines[ix] = line.replace(
                    "export function", "export default function", 1
                )

        module_code_lines.insert(0, "const React = window.__reflex.react;")

        return "//__reflex_evaluate\n" + "\n".join(module_code_lines)

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
                        f"/{constants.Dirs.STATE_PATH}": [
                            imports.ImportVar(tag="evalReactComponent"),
                        ],
                        "react": [
                            imports.ImportVar(tag="useState"),
                            imports.ImportVar(tag="useEffect"),
                        ],
                    },
                    hooks={
                        f"const [{unique_var_name}, set_{unique_var_name}] = useState(null);": None,
                        "useEffect(() => {"
                        "let isMounted = true;"
                        f"evalReactComponent({str(js_string)})"
                        ".then((component) => {"
                        "if (isMounted) {"
                        f"set_{unique_var_name}(component);"
                        "}"
                        "});"
                        "return () => {"
                        "isMounted = false;"
                        "};"
                        "}"
                        f", [{str(js_string)}]);": None,
                    },
                ),
            ),
        )
