"""Templates to use in the pynecone compiler."""

from jinja2 import Environment, FileSystemLoader, Template

from pynecone import constants
from pynecone.utils import path_ops
from pynecone.utils.format import json_dumps


class PyneconeJinjaEnvironment(Environment):
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
        self.loader = FileSystemLoader(constants.JINJA_TEMPLATE_DIR)
        self.globals["const"] = {
            "socket": constants.SOCKET,
            "result": constants.RESULT,
            "router": constants.ROUTER,
            "event_endpoint": constants.Endpoint.EVENT.name,
            "events": constants.EVENTS,
            "state": constants.STATE,
            "processing": constants.PROCESSING,
            "initial_result": {
                constants.STATE: None,
                constants.EVENTS: [],
                constants.PROCESSING: False,
            },
            "color_mode": constants.COLOR_MODE,
            "toggle_color_mode": constants.TOGGLE_COLOR_MODE,
            "use_color_mode": constants.USE_COLOR_MODE,
            "hydrate": constants.HYDRATE,
            "db_url": constants.DB_URL,
        }


def get_template(name: str) -> Template:
    """Get render function that work with a template.

    Args:
        name: The template name. "/" is used as the path separator.

    Returns:
        A render function.
    """
    return PyneconeJinjaEnvironment().get_template(name=name)


# Template for the Pynecone config file.
PCCONFIG = get_template("app/pcconfig.py.jinja2")

# Code to render a NextJS Document root.
DOCUMENT_ROOT = get_template("web/pages/_document.js.jinja2")

# Template for the theme file.
THEME = get_template("web/utils/theme.js.jinja2")

# Code to render a single NextJS page.
PAGE = get_template("web/pages/index.js.jinja2")

# Code to render the custom components page.
COMPONENTS = get_template("web/pages/custom_component.js.jinja2")

# Sitemap config file.
SITEMAP_CONFIG = "module.exports = {config}".format

FULL_CONTROL = path_ops.join(
    [
        "{{setState(prev => ({{",
        "...prev,{state_name}: {arg}",
        "}}), ",
        "()=>Event([{chain}])",
        ")}}",
    ]
).format
