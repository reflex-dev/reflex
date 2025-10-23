"""Templates to use in the reflex compiler."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, Literal

from reflex import constants
from reflex.constants import Hooks
from reflex.constants.state import CAMEL_CASE_MEMO_MARKER
from reflex.utils.format import format_state_name, json_dumps
from reflex.vars.base import VarData

if TYPE_CHECKING:
    from reflex.compiler.utils import _ImportDict
    from reflex.components.component import Component, StatefulComponent


def _sort_hooks(
    hooks: dict[str, VarData | None],
) -> tuple[list[str], list[str], list[str]]:
    """Sort the hooks by their position.

    Args:
        hooks: The hooks to sort.

    Returns:
        The sorted hooks.
    """
    internal_hooks = []
    pre_trigger_hooks = []
    post_trigger_hooks = []

    for hook, data in hooks.items():
        if data and data.position and data.position == Hooks.HookPosition.INTERNAL:
            internal_hooks.append(hook)
        elif not data or (
            not data.position
            or data.position == constants.Hooks.HookPosition.PRE_TRIGGER
        ):
            pre_trigger_hooks.append(hook)
        elif (
            data
            and data.position
            and data.position == constants.Hooks.HookPosition.POST_TRIGGER
        ):
            post_trigger_hooks.append(hook)

    return internal_hooks, pre_trigger_hooks, post_trigger_hooks


class _RenderUtils:
    @staticmethod
    def render(component: Mapping[str, Any] | str) -> str:
        if isinstance(component, str):
            return component or "null"
        if "iterable" in component:
            return _RenderUtils.render_iterable_tag(component)
        if "match_cases" in component:
            return _RenderUtils.render_match_tag(component)
        if "cond_state" in component:
            return _RenderUtils.render_condition_tag(component)
        if (contents := component.get("contents")) is not None:
            return contents or "null"
        return _RenderUtils.render_tag(component)

    @staticmethod
    def render_tag(component: Mapping[str, Any]) -> str:
        name = component.get("name") or "Fragment"
        props = f"{{{','.join(component['props'])}}}"
        rendered_children = [
            _RenderUtils.render(child)
            for child in component.get("children", [])
            if child
        ]

        return f"jsx({name},{props},{','.join(rendered_children)})"

    @staticmethod
    def render_condition_tag(component: Any) -> str:
        return f"({component['cond_state']}?({_RenderUtils.render(component['true_value'])}):({_RenderUtils.render(component['false_value'])}))"

    @staticmethod
    def render_iterable_tag(component: Any) -> str:
        children_rendered = "".join([
            _RenderUtils.render(child) for child in component.get("children", [])
        ])
        return f"Array.prototype.map.call({component['iterable_state']} ?? [],(({component['arg_name']},{component['arg_index']})=>({children_rendered})))"

    @staticmethod
    def render_match_tag(component: Any) -> str:
        cases_code = ""
        for conditions, return_value in component["match_cases"]:
            for condition in conditions:
                cases_code += f"    case JSON.stringify({condition}):\n"
            cases_code += f"""      return {_RenderUtils.render(return_value)};
      break;
"""

        return f"""(() => {{
  switch (JSON.stringify({component["cond"]})) {{
{cases_code}    default:
      return {_RenderUtils.render(component["default"])};
      break;
  }}
}})()"""

    @staticmethod
    def get_import(module: _ImportDict) -> str:
        default_import = module["default"]
        rest_imports = module["rest"]

        if default_import and rest_imports:
            rest_imports_str = ",".join(sorted(rest_imports))
            return f'import {default_import}, {{{rest_imports_str}}} from "{module["lib"]}"'
        if default_import:
            return f'import {default_import} from "{module["lib"]}"'
        if rest_imports:
            rest_imports_str = ",".join(sorted(rest_imports))
            return f'import {{{rest_imports_str}}} from "{module["lib"]}"'
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

export function Layout({{children}}) {{
  return (
    {_RenderUtils.render(document)}
  )
}}"""


def app_root_template(
    *,
    imports: list[_ImportDict],
    custom_codes: Iterable[str],
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

    import_window_libraries = "\n".join([
        f'import * as {lib_alias} from "{lib_path}";'
        for lib_alias, lib_path in window_libraries
    ])

    window_imports_str = "\n".join([
        f'    "{lib_path}": {lib_alias},' for lib_alias, lib_path in window_libraries
    ])

    return f"""
{imports_str}
{dynamic_imports_str}
import {{ EventLoopProvider, StateProvider, defaultColorMode }} from "$/utils/context";
import {{ ThemeProvider }} from '$/utils/react-theme';
import {{ Layout as AppLayout }} from './_document';
import {{ Outlet }} from 'react-router';
{import_window_libraries}

{custom_code_str}

function AppWrap({{children}}) {{
{_render_hooks(hooks)}
return ({_RenderUtils.render(render)})
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


def context_template(
    *,
    is_dev_mode: bool,
    default_color_mode: str,
    initial_state: dict[str, Any] | None = None,
    state_name: str | None = None,
    client_storage: dict[str, dict[str, dict[str, Any]]] | None = None,
):
    """Template for the context file.

    Args:
        initial_state: The initial state for the context.
        state_name: The name of the state.
        client_storage: The client storage for the context.
        is_dev_mode: Whether the app is in development mode.
        default_color_mode: The default color mode for the context.

    Returns:
        Rendered context file content as string.
    """
    initial_state = initial_state or {}
    state_contexts_str = "".join([
        f"{format_state_name(state_name)}: createContext(null),"
        for state_name in initial_state
    ])

    state_str = (
        rf"""
export const state_name = "{state_name}"

export const exception_state_name = "{constants.CompileVars.FRONTEND_EXCEPTION_STATE_FULL}"

// These events are triggered on initial load and each page navigation.
export const onLoadInternalEvent = () => {{
    const internal_events = [];

    // Get tracked cookie and local storage vars to send to the backend.
    const client_storage_vars = hydrateClientStorage(clientStorage);
    // But only send the vars if any are actually set in the browser.
    if (client_storage_vars && Object.keys(client_storage_vars).length !== 0) {{
        internal_events.push(
            ReflexEvent(
                '{state_name}.{constants.CompileVars.UPDATE_VARS_INTERNAL}',
                {{vars: client_storage_vars}},
            ),
        );
    }}

    // `on_load_internal` triggers the correct on_load event(s) for the current page.
    // If the page does not define any on_load event, this will just set `is_hydrated = true`.
    internal_events.push(ReflexEvent('{state_name}.{constants.CompileVars.ON_LOAD_INTERNAL}'));

    return internal_events;
}}

// The following events are sent when the websocket connects or reconnects.
export const initialEvents = () => [
    ReflexEvent('{state_name}.{constants.CompileVars.HYDRATE}'),
    ...onLoadInternalEvent()
]
    """
        if state_name
        else """
export const state_name = undefined

export const exception_state_name = undefined

export const onLoadInternalEvent = () => []

export const initialEvents = () => []
"""
    )

    state_reducer_str = "\n".join(
        rf'const [{format_state_name(state_name)}, dispatch_{format_state_name(state_name)}] = useReducer(applyDelta, initialState["{state_name}"])'
        for state_name in initial_state
    )

    create_state_contexts_str = "\n".join(
        rf"createElement(StateContexts.{format_state_name(state_name)},{{value: {format_state_name(state_name)}}},"
        for state_name in initial_state
    )

    dispatchers_str = "\n".join(
        f'"{state_name}": dispatch_{format_state_name(state_name)},'
        for state_name in initial_state
    )

    return rf"""import {{ createContext, useContext, useMemo, useReducer, useState, createElement, useEffect }} from "react"
import {{ applyDelta, ReflexEvent, hydrateClientStorage, useEventLoop, refs }} from "$/utils/state"
import {{ jsx }} from "@emotion/react";

export const initialState = {"{}" if not initial_state else json_dumps(initial_state)}

export const defaultColorMode = {default_color_mode}
export const ColorModeContext = createContext(null);
export const UploadFilesContext = createContext(null);
export const DispatchContext = createContext(null);
export const StateContexts = {{{state_contexts_str}}};
export const EventLoopContext = createContext(null);
export const clientStorage = {"{}" if client_storage is None else json.dumps(client_storage)}

{state_str}

export const isDevMode = {json.dumps(is_dev_mode)};

export function UploadFilesProvider({{ children }}) {{
  const [filesById, setFilesById] = useState({{}})
  refs["__clear_selected_files"] = (id) => setFilesById(filesById => {{
    const newFilesById = {{...filesById}}
    delete newFilesById[id]
    return newFilesById
  }})
  return createElement(
    UploadFilesContext.Provider,
    {{ value: [filesById, setFilesById] }},
    children
  );
}}

export function ClientSide(component) {{
  return ({{ children, ...props }}) => {{
    const [Component, setComponent] = useState(null);
    useEffect(() => {{
      setComponent(component);
    }}, []);
    return Component ? jsx(Component, props, children) : null;
  }};
}}

export function EventLoopProvider({{ children }}) {{
  const dispatch = useContext(DispatchContext)
  const [addEvents, connectErrors] = useEventLoop(
    dispatch,
    initialEvents,
    clientStorage,
  )
  return createElement(
    EventLoopContext.Provider,
    {{ value: [addEvents, connectErrors] }},
    children
  );
}}

export function StateProvider({{ children }}) {{
  {state_reducer_str}
  const dispatchers = useMemo(() => {{
    return {{
      {dispatchers_str}
    }}
  }}, [])

  return (
    {create_state_contexts_str}
    createElement(DispatchContext, {{value: dispatchers}}, children)
    {")" * len(initial_state)}
  )
}}"""


def component_template(component: Component | StatefulComponent):
    """Template to render a component tag.

    Args:
        component: The component to render.

    Returns:
        Rendered component as string.
    """
    return _RenderUtils.render(component.render())


def page_template(
    imports: Iterable[_ImportDict],
    dynamic_imports: Iterable[str],
    custom_codes: Iterable[str],
    hooks: dict[str, VarData | None],
    render: dict[str, Any],
):
    """Template for a single react page.

    Args:
        imports: List of import statements.
        dynamic_imports: List of dynamic import statements.
        custom_codes: List of custom code snippets.
        hooks: Dictionary of hooks.
        render: Render function for the component.

    Returns:
        Rendered React page component as string.
    """
    imports_str = "\n".join([_RenderUtils.get_import(imp) for imp in imports])
    custom_code_str = "\n".join(custom_codes)
    dynamic_imports_str = "\n".join(dynamic_imports)

    hooks_str = _render_hooks(hooks)
    return f"""{imports_str}

{dynamic_imports_str}

{custom_code_str}

export default function Component() {{
{hooks_str}

  return (
    {_RenderUtils.render(render)}
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
    return json.dumps({
        "name": "reflex",
        "type": "module",
        "scripts": scripts,
        "dependencies": dependencies,
        "devDependencies": dev_dependencies,
        "overrides": overrides,
    })


def vite_config_template(
    base: str,
    hmr: bool,
    force_full_reload: bool,
    experimental_hmr: bool,
    sourcemap: bool | Literal["inline", "hidden"],
):
    """Template for vite.config.js.

    Args:
        base: The base path for the Vite config.
        hmr: Whether to enable hot module replacement.
        force_full_reload: Whether to force a full reload on changes.
        experimental_hmr: Whether to enable experimental HMR features.
        sourcemap: The sourcemap configuration.

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

function fullReload() {{
  return {{
    name: "full-reload",
    enforce: "pre",
    handleHotUpdate({{ server }}) {{
      server.ws.send({{
        type: "full-reload",
      }});
      return [];
    }}
  }};
}}

export default defineConfig((config) => ({{
  plugins: [
    alwaysUseReactDomServerNode(),
    reactRouter(),
    safariCacheBustPlugin(),
  ].concat({"[fullReload()]" if force_full_reload else "[]"}),
  build: {{
    assetsDir: "{base}assets".slice(1),
    sourcemap: {"true" if sourcemap is True else "false" if sourcemap is False else repr(sourcemap)},
    rollupOptions: {{
      onwarn(warning, warn) {{
        if (warning.code === "EVAL" && warning.id && warning.id.endsWith("state.js")) return;
        warn(warning);
      }},
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
    hmr: {"true" if experimental_hmr else "false"},
  }},
  server: {{
    port: process.env.PORT,
    hmr: {"true" if hmr else "false"},
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


def stateful_component_template(
    tag_name: str, memo_trigger_hooks: list[str], component: Component, export: bool
):
    """Template for stateful component.

    Args:
        tag_name: The tag name for the component.
        memo_trigger_hooks: The memo trigger hooks for the component.
        component: The component to render.
        export: Whether to export the component.

    Returns:
        Rendered stateful component code as string.
    """
    all_hooks = component._get_all_hooks()
    return f"""
{"export " if export else ""}function {tag_name} () {{
  {_render_hooks(all_hooks, memo_trigger_hooks)}
  return (
    {_RenderUtils.render(component.render())}
  )
}}
"""


def stateful_components_template(imports: list[_ImportDict], memoized_code: str) -> str:
    """Template for stateful components.

    Args:
        imports: List of import statements.
        memoized_code: Memoized code for stateful components.

    Returns:
        Rendered stateful components code as string.
    """
    imports_str = "\n".join([_RenderUtils.get_import(imp) for imp in imports])
    return f"{imports_str}\n{memoized_code}"


def memo_components_template(
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
export const {component["name"]} = memo(({{ {",".join([f"{prop}:{prop}{CAMEL_CASE_MEMO_MARKER}" for prop in component.get("props", [])])} }}) => {{
    {_render_hooks(component.get("hooks", {}))}
    return(
        {_RenderUtils.render(component["render"])}
    )
}});
"""

    return f"""
{imports_str}

{dynamic_imports_str}

{custom_code_str}

{components_code}"""


def styles_template(stylesheets: list[str]) -> str:
    """Template for styles.css.

    Args:
        stylesheets: List of stylesheets to include.

    Returns:
        Rendered styles.css content as string.
    """
    return "@layer __reflex_base;\n" + "\n".join([
        f"@import url('{sheet_name}');" for sheet_name in stylesheets
    ])


def _render_hooks(hooks: dict[str, VarData | None], memo: list | None = None) -> str:
    """Render hooks for macros.

    Args:
        hooks: Dictionary of hooks to render.
        memo: Optional list of memo hooks.

    Returns:
        Rendered hooks code as string.
    """
    internal, pre_trigger, post_trigger = _sort_hooks(hooks)
    internal_str = "\n".join(internal)
    pre_trigger_str = "\n".join(pre_trigger)
    post_trigger_str = "\n".join(post_trigger)
    memo_str = "\n".join(memo) if memo is not None else ""
    return f"{internal_str}\n{pre_trigger_str}\n{memo_str}\n{post_trigger_str}"
