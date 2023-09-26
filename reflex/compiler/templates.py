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
        self.loader = FileSystemLoader(constants.TEMPLATE.DIR.JINJA_TEMPLATE)
        self.globals["const"] = {
            "socket": constants.VAR_NAMES.SOCKET,
            "result": constants.VAR_NAMES.RESULT,
            "router": constants.VAR_NAMES.ROUTER,
            "event_endpoint": constants.ENDPOINT.EVENT.name,
            "events": constants.VAR_NAMES.EVENTS,
            "state": constants.VAR_NAMES.STATE,
            "final": constants.VAR_NAMES.FINAL,
            "processing": constants.VAR_NAMES.PROCESSING,
            "initial_result": {
                constants.VAR_NAMES.STATE: None,
                constants.VAR_NAMES.EVENTS: [],
                constants.VAR_NAMES.FINAL: True,
                constants.VAR_NAMES.PROCESSING: False,
            },
            "color_mode": constants.COLOR_MODE.NAME,
            "toggle_color_mode": constants.COLOR_MODE.TOGGLE,
            "use_color_mode": constants.COLOR_MODE.USE,
            "hydrate": constants.VAR_NAMES.HYDRATE,
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
