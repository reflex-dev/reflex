"""Tests for reflex_components_ui.constants."""

from pathlib import Path

from reflex_components_ui.constants import JS_SRC, _js_src_dir


def test_js_src_dir_prefers_the_embedded_copy(tmp_path: Path):
    """A built distribution carries the javascript inside the package."""
    root_dir = tmp_path / "site-packages" / "reflex_components_ui"
    embedded = root_dir / "js" / "src"
    embedded.mkdir(parents=True)
    assert _js_src_dir(root_dir) == embedded


def test_js_src_dir_falls_back_to_the_checkout(tmp_path: Path):
    """A source checkout reads the javascript package beside the python source."""
    package = tmp_path / "packages" / "reflex-components-ui"
    root_dir = package / "src" / "reflex_components_ui"
    root_dir.mkdir(parents=True)
    assert _js_src_dir(root_dir) == package / "js" / "src"


def test_js_src_holds_the_javascript():
    """Whichever layout is installed, the constant resolves to real files."""
    assert (JS_SRC / "README.md").is_file()
