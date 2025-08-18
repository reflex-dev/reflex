"""Templates to use in the reflex compiler."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING, Any

from reflex import constants
from reflex.constants import Hooks
from reflex.utils.format import format_state_name, json_dumps
from reflex.vars.base import VarData

if TYPE_CHECKING:
    from reflex.compiler.utils import _ImportDict


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
            **renderer.filters,
            **kwargs,
        }
        return self.template_func(**context)


class _RenderUtils:
    """Utility functions for rendering components.

    Returns:
        Dictionary of utility functions for component rendering.
    """

    @staticmethod
    def render(component: Any) -> str:
        if not isinstance(component, Mapping):
            return str(component)

        if "iterable" in component:
            return _RenderUtils.render_iterable_tag(component)
        if component.get("name") == "match":
            return _RenderUtils.render_match_tag(component)
        if "cond" in component:
            return _RenderUtils.render_condition_tag(component)
        if component.get("children", []):
            return _RenderUtils.render_tag(component)
        return _RenderUtils.render_self_close_tag(component)

    @staticmethod
    def render_self_close_tag(component: Mapping[str, Any]) -> str:
        if component.get("name"):
            name = component["name"]
            props = _RenderUtils.render_props(component.get("props", {}))
            contents = component.get("contents", "")
            return f"jsx({name},{props},{contents})"
        if component.get("contents"):
            return component["contents"]
        return '""'

    @staticmethod
    def render_tag(component: Mapping[str, Any]) -> str:
        name = component.get("name") or "Fragment"
        props = _RenderUtils.render_props(component.get("props", {}))
        contents = component.get("contents", "")
        rendered_children = [
            _RenderUtils.render(child)
            for child in component.get("children", [])
            if child
        ]

        return f"jsx(\n{name},\n{props},\n{contents + ',' if contents else ''}\n{''.join([_RenderUtils.render(child) + ',' for child in rendered_children])}\n)"

    @staticmethod
    def render_condition_tag(component: Any) -> str:
        return f"({component['cond_state']} ? ({_RenderUtils.render(component['true_value'])}) : ({_RenderUtils.render(component['false_value'])}))"

    @staticmethod
    def render_iterable_tag(component: Any) -> str:
        children_rendered = "".join(
            [_RenderUtils.render(child) for child in component.get("children", [])]
        )
        return f"{component['iterable_state']}.map(({component['arg_name']},{component['arg_index']})=>({children_rendered}))"

    @staticmethod
    def render_props(props: list[str]) -> str:
        return "{" + ",".join(props) + "}"

    @staticmethod
    def render_match_tag(component: Any) -> str:
        cases_code = ""
        for case in component.get("match_cases", []):
            for condition in case[:-1]:
                cases_code += f"    case JSON.stringify({condition._js_expr}):\n"
            cases_code += f"""      return {_RenderUtils.render(case[-1])};
      break;
"""

        return f"""(() => {{
  switch (JSON.stringify({component["cond"]._js_expr})) {{
{cases_code}    default:
      return {_RenderUtils.render(component["default"])};
      break;
  }}
}})()"""

    @staticmethod
    def get_import(module: _ImportDict) -> str:
        if module.get("default") and module.get("rest"):
            rest_imports = ", ".join(sorted(module["rest"]))
            return f'import {module["default"]}, {{ {rest_imports} }} from "{module["lib"]}"'
        if module.get("default"):
            return f'import {module["default"]} from "{module["lib"]}"'
        if module.get("rest"):
            rest_imports = ", ".join(sorted(module["rest"]))
            return f'import {{ {rest_imports} }} from "{module["lib"]}"'
        return f'import "{module["lib"]}"'


def rxconfig_template(app_name: str):
    """Template for the Reflex config file.

    Args:
        app_name: The name of the application.

    Returns:
        Rendered Reflex config file content as string.
    """
    return f"""import reflex as rx

config = rx.Config(
    app_name="{app_name}",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)"""


def document_root_template(*, imports: list[_ImportDict], document: dict[str, Any]):
    """Template for the document root.

    Args:
        imports: List of import statements.
        document: Document root component.

    Returns:
        Rendered document root code as string.
    """
    imports_rendered = "\n".join([_RenderUtils.get_import(mod) for mod in imports])
    return f"""{imports_rendered}

export default function Layout() {{
  return (
    {_RenderUtils.render(document)}
  )
}}"""


def app_root_template(
    *,
    imports: list[_ImportDict],
    custom_codes: set[str],
    hooks: dict[str, VarData | None],
    window_libraries: list[tuple[str, str]],
    render: dict[str, Any],
    dynamic_imports: set[str],
):
    """Template for the App root.

    Args:
        imports: The list of import statements.
        custom_codes: The set of custom code snippets.
        hooks: The dictionary of hooks.
        window_libraries: The list of window libraries.
        render: The dictionary of render functions.
        dynamic_imports: The set of dynamic imports.

    Returns:
        Rendered App root component as string.
    """
    imports_str = "\n".join([_RenderUtils.get_import(mod) for mod in imports])
    dynamic_imports_str = "\n".join(dynamic_imports)

    custom_code_str = "\n".join(custom_codes)

    import_window_libraries = "\n".join(
        [
            f'import * as {lib_alias} from "{lib_path}";'
            for lib_alias, lib_path in window_libraries
        ]
    )

    window_imports_str = "\n".join(
        [f'    "{lib_path}": {lib_alias},' for lib_alias, lib_path in window_libraries]
    )

    return f"""
import reflexGlobalStyles from '$/styles/__reflex_global_styles.css?url';
{imports_str}
{dynamic_imports_str}
import {{ EventLoopProvider, StateProvider, defaultColorMode }} from "$/utils/context";
import {{ ThemeProvider }} from '$/utils/react-theme';
import {{ Layout as AppLayout }} from './_document';
import {{ Outlet }} from 'react-router';
{import_window_libraries}

{custom_code_str}

export const links = () => [
  {{ rel: 'stylesheet', href: reflexGlobalStyles, type: 'text/css' }}
];

function AppWrap({{children}}) {{
  {_render_hooks(hooks)}

  return (
    {_RenderUtils.render(render)}
  )
}}


export function Layout({{children}}) {{
  useEffect(() => {{
    // Make contexts and state objects available globally for dynamic eval'd components
    let windowImports = {{
      {window_imports_str}
    }};
    window["__reflex"] = windowImports;
  }}, []);

  return jsx(AppLayout, {{}},
    jsx(ThemeProvider, {{defaultTheme: defaultColorMode, attribute: "class"}},
      jsx(StateProvider, {{}},
        jsx(EventLoopProvider, {{}},
          jsx(AppWrap, {{}}, children)
        )
      )
    )
  );
}}

export default function App() {{
  return jsx(Outlet, {{}});
}}

"""


def theme_template(theme: str):
    """Template for the theme file.

    Args:
        theme: The theme to render.

    Returns:
        Rendered theme file content as string.
    """
    return f"""export default {theme}"""


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
    # If component has a render method, call it, otherwise use it as-is
    rendered_data = component.render() if hasattr(component, "render") else component
    result = _RenderUtils.render(rendered_data)

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

    custom_code_str = "\n".join(custom_codes)
    dynamic_imports_str = "\n".join(dynamic_imports)

    # Render hooks
    sorted_hooks = _sort_hooks(hooks)
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
    {_RenderUtils.render(render_content)}
  )
}}"""


def package_json_template(
    scripts: dict[str, str],
    dependencies: dict[str, str],
    dev_dependencies: dict[str, str],
    overrides: dict[str, str],
):
    """Template for package.json.

    Args:
        scripts: The scripts to include in the package.json file.
        dependencies: The dependencies to include in the package.json file.
        dev_dependencies: The devDependencies to include in the package.json file.
        overrides: The overrides to include in the package.json file.

    Returns:
        Rendered package.json content as string.
    """
    return json.dumps(
        {
            "name": "reflex",
            "type": "module",
            "scripts": scripts,
            "dependencies": dependencies,
            "devDependencies": dev_dependencies,
            "overrides": overrides,
        }
    )


def vite_config_template(base: str):
    """Template for vite.config.js.

    Args:
        base: The base path for the Vite config.

    Returns:
        Rendered vite.config.js content as string.
    """
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


def custom_component_template(
    imports: list[_ImportDict],
    components: list[dict[str, Any]],
    dynamic_imports: Iterable[str],
    custom_codes: Iterable[str],
) -> str:
    """Template for custom component.

    Args:
        imports: List of import statements.
        components: List of component definitions.
        dynamic_imports: List of dynamic import statements.
        custom_codes: List of custom code snippets.

    Returns:
        Rendered custom component code as string.
    """
    imports_str = "\n".join([_RenderUtils.get_import(imp) for imp in imports])
    dynamic_imports_str = "\n".join(dynamic_imports)
    custom_code_str = "\n".join(custom_codes)

    components_code = ""
    for component in components:
        components_code += f"""
export const {component["name"]} = memo({{ {", ".join(component.get("props", []))} }}) => {{
    {_render_hooks(component.get("hooks", {}))}
    return(
        {_RenderUtils.render(component["render"])}
    )
}}
"""

    return f"""
{imports_str}

{dynamic_imports_str}

{custom_code_str}

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


def _render_hooks(hooks: dict, memo: list | None = None) -> str:
    """Render hooks for macros.

    Args:
        hooks: Dictionary of hooks to render.
        memo: Optional list of memo hooks.

    Returns:
        Rendered hooks code as string.
    """
    sorted_hooks = _sort_hooks(hooks)
    hooks_code = ""

    for hook, _ in sorted_hooks.get(constants.Hooks.HookPosition.INTERNAL, []):
        hooks_code += f"  {hook}\n"

    for hook, _ in sorted_hooks.get(constants.Hooks.HookPosition.PRE_TRIGGER, []):
        hooks_code += f"  {hook}\n"

    if memo:
        for hook in memo:
            hooks_code += f"  {hook}\n"

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


# Template for the context file.
CONTEXT = TemplateFunction(_context_template)

# Template to render a component tag.
COMPONENT = TemplateFunction(_component_template)

# Code to render a single react page.
PAGE = TemplateFunction(_page_template)

# Code to render Component instances as part of StatefulComponent
STATEFUL_COMPONENT = TemplateFunction(_stateful_component_template)

# Code to render StatefulComponent to an external file to be shared
STATEFUL_COMPONENTS = TemplateFunction(_stateful_components_template)

# Sitemap config file.
SITEMAP_CONFIG = "module.exports = {config}".format

# Code to render the root stylesheet.
STYLE = TemplateFunction(_styles_template)

# Template containing some macros used in the web pages.
MACROS = TemplateFunction(
    lambda **kwargs: _render_hooks(
        kwargs.get("hooks", {}),
        kwargs.get("memo", None),
    )
)
