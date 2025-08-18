"""Templates to use in the reflex compiler."""

from __future__ import annotations

import json
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
    """Utility functions for rendering components.

    Args:
        **kwargs: Template context variables for rendering.

    Returns:
        Dictionary of utility functions for component rendering.
    """

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
            cases_code += f"""      return {render(case[-1])};
      break;
"""

        return f"""(() => {{
  switch (JSON.stringify({component["cond"]._js_expr})) {{
{cases_code}    default:
      return {render(component["default"])};
      break;
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
    """Template for the Reflex config file.

    Args:
        **kwargs: Template context variables including app_name.

    Returns:
        Rendered Reflex config file content as string.
    """
    app_name = kwargs.get("app_name", "")
    return f"""import reflex as rx

config = rx.Config(
    app_name="{app_name}",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)"""


def _document_root_template(**kwargs):
    """Template for the Document root.

    Args:
        **kwargs: Template context variables including imports and document.

    Returns:
        Rendered Document root component as string.
    """
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
    """Template for the App root.

    Args:
        **kwargs: Template context variables including imports, hooks, render content, etc.

    Returns:
        Rendered App root component as string.
    """
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
    """Template for the theme file.

    Args:
        **kwargs: Template context variables including theme.

    Returns:
        Rendered theme export as string.
    """
    theme = kwargs.get("theme", "")
    return f"""export const theme = {theme}"""


def _context_template(**kwargs):
    """Template for the context file.

    Args:
        **kwargs: Template context variables including initial_state, state_name, etc.

    Returns:
        Rendered context file content as string.
    """
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
    """Template to render a component tag.

    Args:
        **kwargs: Template context variables including component.

    Returns:
        Rendered component as string.
    """
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
    """Template for a single react page.

    Args:
        **kwargs: Template context variables including imports, hooks, render content, etc.

    Returns:
        Rendered React page component as string.
    """
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
    """Template for package.json.

    Args:
        **kwargs: Template context variables including dependencies, dev_dependencies, scripts.

    Returns:
        Rendered package.json content as string.
    """
    return json.dumps(
        {
            "name": "reflex",
            "type": "module",
            "scripts": kwargs.get("scripts", {}),
            "dependencies": kwargs.get("dependencies", {}),
            "devDependencies": kwargs.get("dev_dependencies", {}),
            "overrides": kwargs.get("overrides", {}),
        }
    )


def _vite_config_template(**kwargs):
    """Template for vite.config.js.

    Args:
        **kwargs: Template context variables including base path.

    Returns:
        Rendered vite.config.js content as string.
    """
    base = kwargs.get("base", "/")

    return rf"""import {{ fileURLToPath, URL }} from "url";
import {{ reactRouter }} from "@react-router/dev/vite";
import {{ defineConfig }} from "vite";
import safariCacheBustPlugin from "./vite-plugin-safari-cachebust";

// Ensure that bun always uses the react-dom/server.node functions.
function alwaysUseReactDomServerNode() {{
  return {{
    name: "vite-plugin-always-use-react-dom-server-node",
    enforce: "pre",

    resolveId(source, importer) {{
      if (
        typeof importer === "string" &&
        importer.endsWith("/entry.server.node.tsx") &&
        source.includes("react-dom/server")
      ) {{
        return this.resolve("react-dom/server.node", importer, {{
          skipSelf: true,
        }});
      }}
      return null;
    }},
  }};
}}

export default defineConfig((config) => ({{
  plugins: [
    alwaysUseReactDomServerNode(),
    reactRouter(),
    safariCacheBustPlugin(),
  ],
  build: {{
    assetsDir: "{base}assets".slice(1),
    rollupOptions: {{
      jsx: {{}},
      output: {{
        advancedChunks: {{
          groups: [
            {{
              test: /env.json/,
              name: "reflex-env",
            }},
          ],
        }},
      }},
    }},
  }},
  experimental: {{
    enableNativePlugin: false,
  }},
  server: {{
    port: process.env.PORT,
    watch: {{
      ignored: [
        "**/.web/backend/**",
        "**/.web/reflex.install_frontend_packages.cached",
      ],
    }},
  }},
  resolve: {{
    mainFields: ["browser", "module", "jsnext"],
    alias: [
      {{
        find: "$",
        replacement: fileURLToPath(new URL("./", import.meta.url)),
      }},
      {{
        find: "@",
        replacement: fileURLToPath(new URL("./public", import.meta.url)),
      }},
    ],
  }},
}}));"""


def _stateful_component_template(**kwargs):
    """Template for stateful component.

    Args:
        **kwargs: Template context variables including code.

    Returns:
        Rendered stateful component code as string.
    """
    return kwargs.get("code", "")


def _stateful_components_template(**kwargs) -> str:
    """Template for stateful components.

    Args:
        **kwargs: Template context variables including code.

    Returns:
        Rendered stateful components code as string.
    """
    return kwargs.get("code", "")


def _custom_component_template(**kwargs) -> str:
    """Template for custom components.

    Args:
        **kwargs: Template context variables including custom_codes, components, etc.

    Returns:
        Rendered custom components code as string.
    """
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
    """Template for styles.css.

    Args:
        **kwargs: Template context variables including stylesheets.

    Returns:
        Rendered styles.css content as string.
    """
    stylesheets = kwargs.get("stylesheets", [])
    imports_code = "@layer __reflex_base;\n"
    for sheet_name in stylesheets:
        imports_code += f"@import url('{sheet_name}');\n"
    return imports_code


def _render_hooks(
    hooks: dict, sort_hooks_func: Callable = _sort_hooks, memo: list | None = None
) -> str:
    """Render hooks for macros.

    Args:
        hooks: Dictionary of hooks to render.
        sort_hooks_func: Function to sort hooks by position.
        memo: Optional list of memo hooks.

    Returns:
        Rendered hooks code as string.
    """
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


# Template instances
class TemplateFunction:
    """Wrapper for template functions to match Jinja Template interface."""

    def __init__(self, func: Callable[..., str]):
        """Initialize with template function.

        Args:
            func: Template function to wrap.
        """
        self.func = func

    def render(self, **kwargs) -> str:
        """Render template with kwargs.

        Args:
            **kwargs: Template context variables.

        Returns:
            Rendered template as string.
        """
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
