"""Tests for the document components."""

from reflex_base import constants
from reflex_base.utils.imports import ImportVar
from reflex_components_core.base.document import Scripts


def test_scripts_come_from_the_reflex_frontend():
    """The document's scripts are Reflex's wrapper, which the web template ships."""
    scripts = Scripts.create()
    assert scripts.render() == {"name": "Scripts", "props": [], "children": []}
    assert scripts._get_all_imports() == {"$/utils/scripts": [ImportVar(tag="Scripts")]}
    assert (constants.Templates.Dirs.WEB_TEMPLATE / "utils" / "scripts.js").is_file()
