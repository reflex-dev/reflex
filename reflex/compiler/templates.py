"""Templates to use in the reflex compiler."""

from jinja2 import Environment, FileSystemLoader, Template

from reflex import constants
from reflex.utils.format import json_dumps


class ReflexJinjaEnvironment(Environment):
    """The template class for jinja environment."""

    def __init__(self) -> None:
        """Set default environment."""
        extensions = ["jinja2.ext.debug"]
        super().__init__(
            extensions=extensions,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.filters["json_dumps"] = json_dumps
        self.filters["react_setter"] = lambda state: f"set{state.capitalize()}"
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
            "toggle_color_mode": constants.ColorMode.TOGGLE,
            "use_color_mode": constants.ColorMode.USE,
            "hydrate": constants.CompileVars.HYDRATE,
        }


def get_template(name: str) -> Template:
    """Get render function that work with a template.

    Args:
        name: The template name. "/" is used as the path separator.

    Returns:
        A render function.
    """
    return ReflexJinjaEnvironment().get_template(name=name)


# Template for the Reflex config file.
RXCONFIG = get_template("app/rxconfig.py.jinja2")

# Code to render a NextJS Document root.
DOCUMENT_ROOT = get_template("web/pages/_document.js.jinja2")

# Template for the theme file.
THEME = get_template("web/utils/theme.js.jinja2")

# Template for the context file.
CONTEXT = get_template("web/utils/context.js.jinja2")

# Template for Tailwind config.
TAILWIND_CONFIG = get_template("web/tailwind.config.js.jinja2")

# Template to render a component tag.
COMPONENT = get_template("web/pages/component.js.jinja2")

# Code to render a single NextJS page.
PAGE = get_template("web/pages/index.js.jinja2")

# Code to render the custom components page.
COMPONENTS = get_template("web/pages/custom_component.js.jinja2")

# Sitemap config file.
SITEMAP_CONFIG = "module.exports = {config}".format

# Code to render the root stylesheet.
STYLE = get_template("web/styles/styles.css.jinja2")

# Code that generate the package json file
PACKAGE_JSON = get_template("web/package.json.jinja2")
