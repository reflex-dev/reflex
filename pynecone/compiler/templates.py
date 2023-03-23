"""Templates to use in the pynecone compiler."""

from typing import Optional, Set
from jinja2 import Environment, FileSystemLoader, Template

from pynecone import constants
from pynecone.utils import path_ops, format


class PyneconeJinjaEnvironment(Environment):
    def __init__(self) -> None:
        extensions=[
            'jinja2.ext.debug'
        ]
        super().__init__(
            extensions=extensions,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.filters["json_dumps"] = format.json_dumps
        self.filters["react_setter"] = lambda state: f"set{state.capitalize()}"
        self.loader=FileSystemLoader(constants.JINJA_TEMPLATE_DIR)


def get_template(name: str) -> Template:
    """Get render function that work with a template.

    Args:
        name: The template name. "/" is used as the path separator.

    Returns:
        A render function.
    """
    return PyneconeJinjaEnvironment().get_template(name=name)


# Template for the Pynecone config file.
PCCONFIG = get_template('app/pcconfig.py')

# Javascript formatting.
CONST = get_template('web/pages/parts/const.js.jinja2')
IMPORT_LIB = get_template('web/pages/parts/import_lib.js.jinja2')
IMPORT_FIELDS = get_template('web/pages/parts/import_fields.js.jinja2')


def format_import(lib: str, default: str = "", rest: Optional[Set[str]] = None) -> str:
    """Format an import statement.

    Args:
        lib: The library to import from.
        default: The default field to import.
        rest: The set of fields to import from the library.

    Returns:
        The compiled import statement.
    """
    # Handle the case of direct imports with no libraries.
    if not lib:
        assert not default, "No default field allowed for empty library."
        assert rest is not None and len(rest) > 0, "No fields to import."
        return path_ops.join([IMPORT_LIB.render(lib=lib) for lib in sorted(rest)])

    # Handle importing from a library.
    rest = rest or set()
    return IMPORT_FIELDS.render(default=default, rest=rest, lib=lib)


# Code to render a NextJS Document root.
DOCUMENT_ROOT = get_template('web/pages/_document.js.jinja2')

# Template for the theme file.
THEME = get_template('web/utils/theme.js')

# Code to render a single NextJS page.
PAGE = get_template('web/pages/index.js.jinja2')


# Code to render a single exported custom component.
COMPONENT = path_ops.join(
    [
        "export const {name} = memo(({{{props}}}) => (",
        "{render}",
        "))",
    ]
).format

# Code to render the custom components page.
COMPONENTS = path_ops.join(
    [
        "{imports}",
        "{components}",
    ]
).format


# React state declarations.
USE_STATE = get_template('web/pages/parts/use_state.js.jinja2')

# Effects.
USE_EFFECT = get_template('web/pages/parts/use_effect.js.jinja2')

# Sitemap config file.
SITEMAP_CONFIG = "module.exports = {config}".format

# state of app
STATE = get_template('web/pages/parts/state.js.jinja2')
