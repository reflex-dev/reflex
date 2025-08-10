"""Templates to use in the reflex compiler."""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader, Template

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


class ReflexJinjaEnvironment(Environment):
    """The template class for jinja environment."""

    def __init__(self) -> None:
        """Set default environment."""
        super().__init__(
            trim_blocks=True,
            lstrip_blocks=True,
            auto_reload=False,
        )
        self.filters["json_dumps"] = json_dumps
        self.filters["react_setter"] = lambda state: f"set{state.capitalize()}"
        self.filters["var_name"] = format_state_name
        self.loader = FileSystemLoader(constants.Templates.Dirs.JINJA_TEMPLATE)
        self.globals["const"] = {
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
        self.globals["sort_hooks"] = _sort_hooks


def get_template(name: str) -> Template:
    """Get render function that work with a template.

    Args:
        name: The template name. "/" is used as the path separator.

    Returns:
        A render function.
    """
    return ReflexJinjaEnvironment().get_template(name=name)


def from_string(source: str) -> Template:
    """Get render function that work with a template.

    Args:
        source: The template source.

    Returns:
        A render function.
    """
    return ReflexJinjaEnvironment().from_string(source=source)


# Template for the Reflex config file.
RXCONFIG = get_template("app/rxconfig.py.jinja2")

# Code to render the Document root.
DOCUMENT_ROOT = get_template("web/pages/_document.js.jinja2")

# Code to render App root.
APP_ROOT = get_template("web/pages/_app.js.jinja2")

# Template for the theme file.
THEME = get_template("web/utils/theme.js.jinja2")

# Template for the context file.
CONTEXT = get_template("web/utils/context.js.jinja2")

# Template to render a component tag.
COMPONENT = get_template("web/pages/component.js.jinja2")

# Code to render a single react page.
PAGE = get_template("web/pages/index.js.jinja2")

# Code to render the custom components page.
COMPONENTS = get_template("web/pages/custom_component.js.jinja2")

# Code to render Component instances as part of StatefulComponent
STATEFUL_COMPONENT = get_template("web/pages/stateful_component.js.jinja2")

# Code to render StatefulComponent to an external file to be shared
STATEFUL_COMPONENTS = get_template("web/pages/stateful_components.js.jinja2")

# Sitemap config file.
SITEMAP_CONFIG = "module.exports = {config}".format

# Code to render the root stylesheet.
STYLE = get_template("web/styles/styles.css.jinja2")

# Code that generate the package json file
PACKAGE_JSON = get_template("web/package.json.jinja2")

# Code that generate the vite.config.js file
VITE_CONFIG = get_template("web/vite.config.js.jinja2")

# Template containing some macros used in the web pages.
MACROS = get_template("web/pages/macros.js.jinja2")

# Code that generate the pyproject.toml file for custom components.
CUSTOM_COMPONENTS_PYPROJECT_TOML = get_template(
    "custom_components/pyproject.toml.jinja2"
)

# Code that generates the README file for custom components.
CUSTOM_COMPONENTS_README = get_template("custom_components/README.md.jinja2")

# Code that generates the source file for custom components.
CUSTOM_COMPONENTS_SOURCE = get_template("custom_components/src.py.jinja2")

# Code that generates the init file for custom components.
CUSTOM_COMPONENTS_INIT_FILE = get_template("custom_components/__init__.py.jinja2")

# Code that generates the demo app main py file for testing custom components.
CUSTOM_COMPONENTS_DEMO_APP = get_template("custom_components/demo_app.py.jinja2")
