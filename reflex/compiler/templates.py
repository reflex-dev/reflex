"""Templates to use in the reflex compiler."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from reflex import constants
from reflex.constants import Hooks
from reflex.utils.format import format_state_name, json_dumps
from reflex.vars.base import VarData


def _sort_hooks(hooks: dict[str, VarData | None]):
    """Sort the hooks by their position.

    Args:
        hooks: The hooks to sort.

    Returns:
        The sorted hooks.
    """
    sorted_hooks = {
        Hooks.HookPosition.INTERNAL: [],
        Hooks.HookPosition.PRE_TRIGGER: [],
        Hooks.HookPosition.POST_TRIGGER: [],
    }

    for hook, data in hooks.items():
        if data and data.position and data.position == Hooks.HookPosition.INTERNAL:
            sorted_hooks[Hooks.HookPosition.INTERNAL].append((hook, data))
        elif not data or (
            not data.position
            or data.position == constants.Hooks.HookPosition.PRE_TRIGGER
        ):
            sorted_hooks[Hooks.HookPosition.PRE_TRIGGER].append((hook, data))
        elif (
            data
            and data.position
            and data.position == constants.Hooks.HookPosition.POST_TRIGGER
        ):
            sorted_hooks[Hooks.HookPosition.POST_TRIGGER].append((hook, data))

    return sorted_hooks


class ReflexTemplateRenderer:
    """Template renderer using f-string formatting."""

    def __init__(self) -> None:
        """Initialize template renderer with helper functions."""
        self.filters = {
            "json_dumps": json_dumps,
            "react_setter": lambda state: f"set{state.capitalize()}",
            "var_name": format_state_name,
        }

        self.const = {
            "socket": constants.CompileVars.SOCKET,
            "result": constants.CompileVars.RESULT,
            "router": constants.CompileVars.ROUTER,
            "event_endpoint": constants.Endpoint.EVENT.name,
            "events": constants.CompileVars.EVENTS,
            "state": constants.CompileVars.STATE,
            "final": constants.CompileVars.FINAL,
            "processing": constants.CompileVars.PROCESSING,
            "initial_result": {
                constants.CompileVars.STATE: None,
                constants.CompileVars.EVENTS: [],
                constants.CompileVars.FINAL: True,
                constants.CompileVars.PROCESSING: False,
            },
            "color_mode": constants.ColorMode.NAME,
            "resolved_color_mode": constants.ColorMode.RESOLVED_NAME,
            "toggle_color_mode": constants.ColorMode.TOGGLE,
            "set_color_mode": constants.ColorMode.SET,
            "use_color_mode": constants.ColorMode.USE,
            "hydrate": constants.CompileVars.HYDRATE,
            "on_load_internal": constants.CompileVars.ON_LOAD_INTERNAL,
            "update_vars_internal": constants.CompileVars.UPDATE_VARS_INTERNAL,
            "frontend_exception_state": constants.CompileVars.FRONTEND_EXCEPTION_STATE_FULL,
            "hook_position": constants.Hooks.HookPosition,
        }

        self.sort_hooks = _sort_hooks


class Template:
    """Template class for f-string based rendering."""

    def __init__(self, template_func: Callable[..., str]):
        """Initialize with a template function.

        Args:
            template_func: Function that takes kwargs and returns rendered string.
        """
        self.template_func = template_func

    def render(self, **kwargs) -> str:
        """Render the template with provided context.

        Args:
            **kwargs: Template context variables.

        Returns:
            Rendered template string.
        """
        renderer = ReflexTemplateRenderer()
        # Merge renderer utilities into context
        context = {
            "const": renderer.const,
            "sort_hooks": renderer.sort_hooks,
            **renderer.filters,
            **kwargs,
        }
        return self.template_func(**context)


# Legacy functions removed - all templates now use f-strings


def _render_component_utils(**kwargs):
    """Utility functions for rendering components."""

    def render(component: Any) -> str:
        if not isinstance(component, dict):
            return str(component)

        if "iterable" in component:
            return render_iterable_tag(component)
        if component.get("name") == "match":
            return render_match_tag(component)
        if "cond" in component:
            return render_condition_tag(component)
        if component.get("children", []):
            return render_tag(component)
        return render_self_close_tag(component)

    def render_self_close_tag(component: Any) -> str:
        if component.get("name"):
            name = component["name"]
            props = render_props(component.get("props", {}))
            contents = component.get("contents", "")
            if contents:
                return f"jsx({name},{props},{contents},)"
            return f"jsx({name},{props},)"
        if component.get("contents"):
            return component["contents"]
        return '""'

    def render_tag(component: Any) -> str:
        name = component.get("name") or "Fragment"
        props = render_props(component.get("props", {}))
        contents = component.get("contents", "")
        rendered_children = [
            render(child) for child in component.get("children", []) if child
        ]

        jsx_content = f"jsx(\n{name},\n{props}"
        if contents:
            jsx_content += f",\n{contents}"

        # Handle children with special logic for the last one
        for i, child in enumerate(rendered_children):
            jsx_content += f",\n{child}"
            # If this is the last child and it ends with ), don't add newline before final comma
            if i == len(rendered_children) - 1 and child.endswith(")"):
                jsx_content += ",)"
                return jsx_content

        jsx_content += "\n,)"
        return jsx_content

    def render_condition_tag(component: Any) -> str:
        return f"({component['cond_state']} ? ({render(component['true_value'])}) : ({render(component['false_value'])}))"

    def render_iterable_tag(component: Any) -> str:
        children_rendered = "".join(
            [render(child) for child in component.get("children", [])]
        )
        return f"{component['iterable_state']}.map(({component['arg_name']},{component['arg_index']})=>({children_rendered}))"

    def render_props(props: Any) -> str:
        if not props:
            return "{}"
        if isinstance(props, list):
            return "{" + ",".join(props) + "}"
        return str(props)

    def render_match_tag(component: Any) -> str:
        cases_code = ""
        for case in component.get("match_cases", []):
            for condition in case[:-1]:
                cases_code += f"    case JSON.stringify({condition._js_expr}):\n"
            cases_code += f"      return {render(case[-1])};\n      break;\n"

        return f"""(() => {{
  switch (JSON.stringify({component["cond"]._js_expr})) {{
{cases_code}    default:
      return {render(component["default"])};\n      break;
  }}
}})()"""

    def get_import(module: Any) -> str:
        if module.get("default") and module.get("rest"):
            rest_imports = ", ".join(sorted(module["rest"]))
            return f'import {module["default"]}, {{ {rest_imports} }} from "{module["lib"]}"'
        if module.get("default"):
            return f'import {module["default"]} from "{module["lib"]}"'
        if module.get("rest"):
            rest_imports = ", ".join(sorted(module["rest"]))
            return f'import {{ {rest_imports} }} from "{module["lib"]}"'
        return f'import "{module["lib"]}"'

    return {
        "render": render,
        "render_self_close_tag": render_self_close_tag,
        "render_tag": render_tag,
        "render_condition_tag": render_condition_tag,
        "render_iterable_tag": render_iterable_tag,
        "render_props": render_props,
        "render_match_tag": render_match_tag,
        "get_import": get_import,
    }


# Template functions using f-strings


def _rxconfig_template(**kwargs):
    """Template for the Reflex config file."""
    app_name = kwargs.get("app_name", "")
    return f"""import reflex as rx

config = rx.Config(
    app_name="{app_name}",
)"""


def _document_root_template(**kwargs):
    """Template for the Document root."""
    imports = kwargs.get("imports", "")
    document = kwargs.get("document", "")
    utils = _render_component_utils(**kwargs)

    return f"""{imports}

export default function Document() {{
  return (
    {utils["render"](document)}
  )
}}"""


def _app_root_template(**kwargs):
    """Template for the App root."""
    imports = kwargs.get("imports", "")
    custom_codes = kwargs.get("custom_codes", [])
    hooks = kwargs.get("hooks", {})
    window_libraries = kwargs.get("window_libraries", [])
    render_content = kwargs.get("render", "")
    dynamic_imports = kwargs.get("dynamic_imports", [])
    sort_hooks = kwargs.get("sort_hooks", _sort_hooks)
    utils = _render_component_utils(**kwargs)

    custom_code_str = "\n".join(custom_codes)
    dynamic_imports_str = "\n".join(dynamic_imports)

    # Render hooks
    sorted_hooks = sort_hooks(hooks)
    hooks_code = ""
    for hook_list in sorted_hooks.values():
        for hook, _ in hook_list:
            hooks_code += f"  {hook}\n"

    # Window libraries
    window_lib_code = ""
    for norm_name, lib_name in window_libraries:
        window_lib_code += f"  {norm_name}: {lib_name},\n"

    # Check if we need to generate AppWrap function (when wrappers exist)
    has_app_wrappers = (
        isinstance(render_content, dict)
        and render_content.get("name") != "Fragment"
        and render_content.get("name") != ""
    )

    if has_app_wrappers:
        # Check if we need to strip StrictMode based on actual config
        from reflex.config import _get_config

        config = _get_config()
        should_include_strict_mode = config.react_strict_mode

        # If render_content starts with StrictMode but config says not to include it,
        # strip the StrictMode wrapper
        actual_render_content = render_content
        if (
            not should_include_strict_mode
            and isinstance(render_content, dict)
            and render_content.get("name") == "StrictMode"
            and render_content.get("children")
            and len(render_content["children"]) > 0
        ):
            actual_render_content = render_content["children"][0]

        # Generate AppWrap function with wrapper logic
        app_wrap_function = f"""
function AppWrap({{children}}) {{
  const [addEvents, connectErrors] = useContext(EventLoopContext);
  return (
    {utils["render"](actual_render_content)}
  )
}}"""

        # Main App function calls AppWrap
        main_app_function = f"""
export default function App({{ Component, pageProps }}) {{
{hooks_code}

  return (
    jsx(AppWrap,{{}},jsx(Component,pageProps,),)
  )
}}"""
    else:
        # Simple case - no AppWrap needed
        app_wrap_function = ""
        main_app_function = f"""
export default function App({{ Component, pageProps }}) {{
{hooks_code}

  return (
    {utils["render"](render_content)}
  )
}}"""

    return f"""{imports}
{dynamic_imports_str}

{custom_code_str}
{app_wrap_function}
{main_app_function}"""


def _theme_template(**kwargs):
    """Template for the theme file."""
    theme = kwargs.get("theme", "")
    return f"""export const theme = {theme}"""


def _context_template(**kwargs):
    """Template for the context file."""
    initial_state = kwargs.get("initial_state", "null")
    state_name = kwargs.get("state_name", "")
    client_storage = kwargs.get("client_storage", "")
    is_dev_mode = kwargs.get("is_dev_mode", False)
    default_color_mode = kwargs.get("default_color_mode", "")

    return f"""import {{ createContext, useContext, useMemo, useReducer, useState }} from "react"

export const StateContexts = {{
  {state_name or ""}: createContext(null),
}}

export const EventContexts = {{
  {state_name or ""}: createContext(null),
}}

export const initialState = {initial_state}
export const clientStorage = {client_storage}
export const isDevMode = {str(is_dev_mode).lower()}
export const colorModeManager = {{
  get: () => {default_color_mode},
  set: () => {{}},
  type: "localStorage"
}}"""


def _component_template(**kwargs):
    """Template to render a component tag."""
    component = kwargs.get("component", {})
    utils = _render_component_utils(**kwargs)
    # If component has a render method, call it, otherwise use it as-is
    rendered_data = component.render() if hasattr(component, "render") else component
    result = utils["render"](rendered_data)

    # Add trailing newline for HTML elements (those with quoted tag names)
    # to match original Jinja behavior
    if isinstance(rendered_data, dict) and rendered_data.get("name", "").startswith(
        '"'
    ):
        result += "\n"

    return result


def _page_template(**kwargs):
    """Template for a single react page."""
    imports = kwargs.get("imports", "")
    dynamic_imports = kwargs.get("dynamic_imports", [])
    custom_codes = kwargs.get("custom_codes", [])
    hooks = kwargs.get("hooks", {})
    render_content = kwargs.get("render", "")
    sort_hooks = kwargs.get("sort_hooks", _sort_hooks)
    utils = _render_component_utils(**kwargs)

    custom_code_str = "\n".join(custom_codes)
    dynamic_imports_str = "\n".join(dynamic_imports)

    # Render hooks
    sorted_hooks = sort_hooks(hooks)
    hooks_code = ""
    for hook_list in sorted_hooks.values():
        for hook, _ in hook_list:
            hooks_code += f"  {hook}\n"

    return f"""{imports}
{dynamic_imports_str}

{custom_code_str}

export default function Component() {{
{hooks_code}

  return (
    {utils["render"](render_content)}
  )
}}"""


def _package_json_template(**kwargs):
    """Template for package.json."""
    return f"""{{
  "name": "frontend",
  "version": "0.1.0",
  "private": true,
  "dependencies": {kwargs.get("dependencies", {})},
  "devDependencies": {kwargs.get("dev_dependencies", {})},
  "scripts": {kwargs.get("scripts", {})}
}}"""


def _vite_config_template(**kwargs):
    """Template for vite.config.js."""
    base = kwargs.get("base", "/")

    # Generate assetsDir from base path
    # Remove trailing slash, add /assets, then .slice(1) to remove leading slash
    assets_path = base.rstrip("/") + "/assets"

    return f"""import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({{
  plugins: [react()],
  base: "{base}",
  assetsDir: "{assets_path}".slice(1),
}})"""


def _stateful_component_template(**kwargs):
    """Template for stateful component."""
    return kwargs.get("code", "")


def _stateful_components_template(**kwargs) -> str:
    """Template for stateful components."""
    return kwargs.get("code", "")


def _custom_component_template(**kwargs) -> str:
    """Template for custom components."""
    custom_codes = kwargs.get("custom_codes", [])
    components = kwargs.get("components", [])
    utils = _render_component_utils(**kwargs)
    sort_hooks = kwargs.get("sort_hooks", _sort_hooks)

    custom_code_str = "\n".join(custom_codes)

    components_code = ""
    for component in components:
        # Render hooks for each component
        hooks = component.get("hooks", {})
        sorted_hooks = sort_hooks(hooks)
        hooks_code = ""
        for hook_list in sorted_hooks.values():
            for hook, _ in hook_list:
                hooks_code += f"    {hook}\n"

        props_str = ", ".join(component.get("props", []))
        components_code += f"""
export const {component["name"]} = memo({{ {props_str} }}) => {{
{hooks_code}
    return(
        {utils["render"](component["render"])}
      )

}}"""

    return f"""{custom_code_str}
{components_code}"""


def _styles_template(**kwargs) -> str:
    """Template for styles.css."""
    stylesheets = kwargs.get("stylesheets", [])
    imports_code = "@layer __reflex_base;\n"
    for sheet_name in stylesheets:
        imports_code += f"@import url('{sheet_name}'); \n"
    return imports_code


def _render_hooks(
    hooks: dict, sort_hooks_func: Callable = _sort_hooks, memo: list | None = None
) -> str:
    """Render hooks for macros."""
    sorted_hooks = sort_hooks_func(hooks)
    hooks_code = ""

    # Internal hooks
    for hook, _ in sorted_hooks.get(constants.Hooks.HookPosition.INTERNAL, []):
        hooks_code += f"  {hook}\n"

    # Pre-trigger hooks
    for hook, _ in sorted_hooks.get(constants.Hooks.HookPosition.PRE_TRIGGER, []):
        hooks_code += f"  {hook}\n"

    # Memo hooks if provided
    if memo:
        for hook in memo:
            hooks_code += f"  {hook}\n"

    # Post-trigger hooks
    for hook, _ in sorted_hooks.get(constants.Hooks.HookPosition.POST_TRIGGER, []):
        hooks_code += f"  {hook}\n"

    return hooks_code


def _custom_components_pyproject_toml_template(**kwargs) -> str:
    """Template for custom components pyproject.toml."""
    package_name = kwargs.get("package_name", "")
    module_name = kwargs.get("module_name", "")
    reflex_version = kwargs.get("reflex_version", "")

    return f"""[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{package_name}"
version = "0.0.1"
description = "Reflex custom component {module_name}"
readme = "README.md"
license = {{ text = "Apache-2.0" }}
requires-python = ">=3.10"
authors = [{{ name = "", email = "YOUREMAIL@domain.com" }}]
keywords = ["reflex","reflex-custom-components"]

dependencies = ["reflex>={reflex_version}"]

classifiers = ["Development Status :: 4 - Beta"]

[project.urls]

[project.optional-dependencies]
dev = ["build", "twine"]

[tool.setuptools.packages.find]
where = ["custom_components"]
"""


def _custom_components_readme_template(**kwargs) -> str:
    """Template for custom components README."""
    module_name = kwargs.get("module_name", "")
    package_name = kwargs.get("package_name", "")

    return f"""# {module_name}

A Reflex custom component {module_name}.

## Installation

```bash
pip install {package_name}
```
"""


def _custom_components_source_template(**kwargs) -> str:
    """Template for custom components source."""
    component_class_name = kwargs.get("component_class_name", "")
    module_name = kwargs.get("module_name", "")

    return f"""\"\"\"Reflex custom component {component_class_name}.\"\"\"\n\n# For wrapping react guide, visit https://reflex.dev/docs/wrapping-react/overview/\n\nimport reflex as rx\n\n# Some libraries you want to wrap may require dynamic imports.\n# This is because they they may not be compatible with Server-Side Rendering (SSR).\n# To handle this in Reflex, all you need to do is subclass `NoSSRComponent` instead.\n# For example:\n# from reflex.components.component import NoSSRComponent\n# class {component_class_name}(NoSSRComponent):\n#     pass\n\n\nclass {component_class_name}(rx.Component):\n    \"\"\"{component_class_name} component.\"\"\"\n\n    # The React library to wrap.\n    library = \"Fill-Me\"\n\n    # The React component tag.\n    tag = \"Fill-Me\"\n\n    # If the tag is the default export from the module, you must set is_default = True.\n    # This is normally used when components don't have curly braces around them when importing.\n    # is_default = True\n\n    # If you are wrapping another components with the same tag as a component in your project\n    # you can use aliases to differentiate between them and avoid naming conflicts.\n    # alias = \"Other{component_class_name}\"\n\n    # The props of the React component.\n    # Note: when Reflex compiles the component to Javascript,\n    # `snake_case` property names are automatically formatted as `camelCase`.\n    # The prop names may be defined in `camelCase` as well.\n    # some_prop: rx.Var[str] = \"some default value\"\n    # some_other_prop: rx.Var[int] = 1\n\n    # By default Reflex will install the library you have specified in the library property.\n    # However, sometimes you may need to install other libraries to use a component.\n    # In this case you can use the lib_dependencies property to specify other libraries to install.\n    # lib_dependencies: list[str] = []\n\n    # Event triggers declaration if any.\n    # Below is equivalent to merging `{{ \"on_change\": lambda e: [e] }}`\n    # onto the default event triggers of parent/base Component.\n    # The function defined for the `on_change` trigger maps event for the javascript\n    # trigger to what will be passed to the backend event handler function.\n    # on_change: rx.EventHandler[lambda e: [e]]\n\n    # To add custom code to your component\n    # def _get_custom_code(self) -> str:\n    #     return \"const customCode = 'customCode';\"\n\n\n{module_name} = {component_class_name}.create\n"""


def _custom_components_init_template(**kwargs) -> str:
    """Template for custom components __init__.py."""
    module_name = kwargs.get("module_name", "")
    return f"from .{module_name} import *"


def _custom_components_demo_app_template(**kwargs) -> str:
    """Template for custom components demo app."""
    custom_component_module_dir = kwargs.get("custom_component_module_dir", "")
    module_name = kwargs.get("module_name", "")

    return f"""\"\"\"Welcome to Reflex! This file showcases the custom component in a basic app.\"\"\"\n\nfrom rxconfig import config\n\nimport reflex as rx\n\nfrom {custom_component_module_dir} import {module_name}\n\nfilename = f\"{{config.app_name}}/{{config.app_name}}.py\"\n\n\nclass State(rx.State):\n    \"\"\"The app state.\"\"\"\n\n    pass\n\n\ndef index() -> rx.Component:\n    return rx.center(\n        rx.theme_panel(),\n        rx.vstack(\n            rx.heading(\"Welcome to Reflex!\", size=\"9\"),\n            rx.text(\n                \"Test your custom component by editing \", \n                rx.code(filename),\n                font_size=\"2em\",\n            ),\n            {module_name}(),\n            align=\"center\",\n            spacing=\"7\",\n        ),\n        height=\"100vh\",\n    )\n\n\n# Add state and page to the app.\napp = rx.App()\napp.add_page(index)\n\n"""


# Template instances
class TemplateFunction:
    """Wrapper for template functions to match Jinja Template interface."""

    def __init__(self, func: Callable[..., str]):
        """Initialize with template function."""
        self.func = func

    def render(self, **kwargs) -> str:
        """Render template with kwargs."""
        return self.func(**kwargs)


# Template for the Reflex config file.
RXCONFIG = TemplateFunction(_rxconfig_template)

# Code to render the Document root.
DOCUMENT_ROOT = TemplateFunction(_document_root_template)

# Code to render App root.
APP_ROOT = TemplateFunction(_app_root_template)

# Template for the theme file.
THEME = TemplateFunction(_theme_template)

# Template for the context file.
CONTEXT = TemplateFunction(_context_template)

# Template to render a component tag.
COMPONENT = TemplateFunction(_component_template)

# Code to render a single react page.
PAGE = TemplateFunction(_page_template)

# Code to render the custom components page.
COMPONENTS = TemplateFunction(_custom_component_template)

# Code to render Component instances as part of StatefulComponent
STATEFUL_COMPONENT = TemplateFunction(_stateful_component_template)

# Code to render StatefulComponent to an external file to be shared
STATEFUL_COMPONENTS = TemplateFunction(_stateful_components_template)

# Sitemap config file.
SITEMAP_CONFIG = "module.exports = {config}".format

# Code to render the root stylesheet.
STYLE = TemplateFunction(_styles_template)

# Code that generate the package json file
PACKAGE_JSON = TemplateFunction(_package_json_template)

# Code that generate the vite.config.js file
VITE_CONFIG = TemplateFunction(_vite_config_template)

# Template containing some macros used in the web pages.
MACROS = TemplateFunction(
    lambda **kwargs: _render_hooks(
        kwargs.get("hooks", {}),
        kwargs.get("sort_hooks", _sort_hooks),
        kwargs.get("memo", None),
    )
)

# Code that generate the pyproject.toml file for custom components.
CUSTOM_COMPONENTS_PYPROJECT_TOML = TemplateFunction(
    _custom_components_pyproject_toml_template
)

# Code that generates the README file for custom components.
CUSTOM_COMPONENTS_README = TemplateFunction(_custom_components_readme_template)

# Code that generates the source file for custom components.
CUSTOM_COMPONENTS_SOURCE = TemplateFunction(_custom_components_source_template)

# Code that generates the init file for custom components.
CUSTOM_COMPONENTS_INIT_FILE = TemplateFunction(_custom_components_init_template)

# Code that generates the demo app main py file for testing custom components.
CUSTOM_COMPONENTS_DEMO_APP = TemplateFunction(_custom_components_demo_app_template)
