"""Components that are dynamically generated on the backend."""

from reflex.components.component import Component
from reflex.utils.imports import ImportVar


def make_component(component: Component) -> str:
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

    imports = {}
    for lib, names in component._get_all_imports().items():
        if (
            not lib.startswith((".", "/"))
            and not lib.startswith("http")
            and lib != "react"
        ):
            imports[f"https://cdn.jsdelivr.net/npm/{lib}" + "/+esm"] = names
        else:
            imports[lib] = names
    if "react" not in imports:
        imports["react"] = []
    imports["react"].append(ImportVar("*", is_default=True, alias="React"))

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
            elif 'from "react"' in line:
                module_code_lines[ix] = line.replace("import ", "const ", 1).replace(
                    ' from "react"', " = window.__reflex.react", 1
                )
        if line.startswith("export function"):
            module_code_lines[ix] = line.replace(
                "export function", "export default function", 1
            )
    return "//__reflex_evaluate\n" + "\n".join(module_code_lines)
