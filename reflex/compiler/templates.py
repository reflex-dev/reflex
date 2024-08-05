"""Templates to use in the reflex compiler."""

from jinja2 import Environment, FileSystemLoader, Template

from reflex import constants
from reflex.utils.format import format_state_name, json_dumps


class ReflexJinjaEnvironment(Environment):
    """The template class for jinja environment."""

    def __init__(self) -> None:
        """Set default environment."""
        from reflex.state import (
            FrontendEventExceptionState,
            OnLoadInternalState,
            State,
            UpdateVarsInternalState,
        )

        extensions = ["jinja2.ext.debug"]
        super().__init__(
            extensions=extensions,
            trim_blocks=True,
            lstrip_blocks=True,
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
            "main_state_name": State.get_name(),
            "on_load_internal": f"{OnLoadInternalState.get_name()}.on_load_internal",
            "update_vars_internal": f"{UpdateVarsInternalState.get_name()}.update_vars_internal",
            "frontend_exception_state": FrontendEventExceptionState.get_full_name(),
        }


def get_template(name: str) -> Template:
    """Get render function that work with a template.

    Args:
        name: The template name. "/" is used as the path separator.

    Returns:
        A render function.
    """
    return ReflexJinjaEnvironment().get_template(name=name)


def rxconfig():
    """Template for the Reflex config file.

    Returns:
        Template: The template for the Reflex config file.
    """
    return get_template("app/rxconfig.py.jinja2")


def document_root():
    """Code to render a NextJS Document root.

    Returns:
        Template: The template for the NextJS Document root.
    """
    return get_template("web/pages/_document.js.jinja2")


def app_root():
    """Code to render NextJS App root.

    Returns:
        Template: The template for the NextJS App root.
    """
    return get_template("web/pages/_app.js.jinja2")


def theme():
    """Template for the theme file.

    Returns:
        Template: The template for the theme file.
    """
    return get_template("web/utils/theme.js.jinja2")


def context():
    """Template for the context file.

    Returns:
        Template: The template for the context file.
    """
    return get_template("web/utils/context.js.jinja2")


def tailwind_config():
    """Template for Tailwind config.

    Returns:
        Template: The template for the Tailwind config
    """
    return get_template("web/tailwind.config.js.jinja2")


def component():
    """Template to render a component tag.

    Returns:
        Template: The template for the component tag.
    """
    return get_template("web/pages/component.js.jinja2")


def page():
    """Code to render a single NextJS page.

    Returns:
        Template: The template for the NextJS page.
    """
    return get_template("web/pages/index.js.jinja2")


def components():
    """Code to render the custom components page.

    Returns:
        Template: The template for the custom components page.
    """
    return get_template("web/pages/custom_component.js.jinja2")


def stateful_component():
    """Code to render Component instances as part of StatefulComponent.

    Returns:
        Template: The template for the StatefulComponent.
    """
    return get_template("web/pages/stateful_component.js.jinja2")


def stateful_components():
    """Code to render StatefulComponent to an external file to be shared.

    Returns:
        Template: The template for the StatefulComponent.
    """
    return get_template("web/pages/stateful_components.js.jinja2")


def sitemap_config():
    """Sitemap config file.

    Returns:
        Template: The template for the sitemap config file.
    """
    return "module.exports = {config}".format


def style():
    """Code to render the root stylesheet.

    Returns:
        Template: The template for the root stylesheet
    """
    return get_template("web/styles/styles.css.jinja2")


def package_json():
    """Code that generate the package json file.

    Returns:
        Template: The template for the package json file
    """
    return get_template("web/package.json.jinja2")


def custom_components_pyproject_toml():
    """Code that generate the pyproject.toml file for custom components.

    Returns:
        Template: The template for the pyproject.toml file
    """
    return get_template("custom_components/pyproject.toml.jinja2")


def custom_components_readme():
    """Code that generates the README file for custom components.

    Returns:
        Template: The template for the README file
    """
    return get_template("custom_components/README.md.jinja2")


def custom_components_source():
    """Code that generates the source file for custom components.

    Returns:
        Template: The template for the source file
    """
    return get_template("custom_components/src.py.jinja2")


def custom_components_init():
    """Code that generates the init file for custom components.

    Returns:
        Template: The template for the init file
    """
    return get_template("custom_components/__init__.py.jinja2")


def custom_components_demo_app():
    """Code that generates the demo app main py file for testing custom components.

    Returns:
        Template: The template for the demo app main py file
    """
    return get_template("custom_components/demo_app.py.jinja2")
