"""Tests for the manifest of the javascript package reflex-components-ui embeds."""

import json
from pathlib import Path

from reflex_components_ui.constants import STYLEX_VERSION

JS_PACKAGE = Path(__file__).parents[3] / "packages/reflex-components-ui/js"

# StyleX is 0.x and has broken its output between patch releases, so every
# package of it moves together and by an exact pin: the version an app
# installs is the version the javascript package is developed against.


def test_stylex_packages_are_pinned_to_one_exact_version():
    """The manifest names no StyleX package at a range or a second version."""
    manifest = json.loads((JS_PACKAGE / "package.json").read_text())
    pins = {
        name: pin
        for group in ("dependencies", "devDependencies")
        for name, pin in manifest[group].items()
        if name.startswith("@stylexjs/")
    }
    assert pins == {
        "@stylexjs/stylex": STYLEX_VERSION,
        "@stylexjs/unplugin": STYLEX_VERSION,
        "@stylexjs/eslint-plugin": STYLEX_VERSION,
    }


def test_lockfile_installs_stylex_at_the_pinned_version():
    """What `npm ci` installs, the compiler behind the plugin included."""
    lock = json.loads((JS_PACKAGE / "package-lock.json").read_text())
    installed = {
        path.removeprefix("node_modules/"): package["version"]
        for path, package in lock["packages"].items()
        if path.startswith("node_modules/@stylexjs/")
    }
    assert installed == {
        "@stylexjs/babel-plugin": STYLEX_VERSION,
        "@stylexjs/eslint-plugin": STYLEX_VERSION,
        "@stylexjs/shared": STYLEX_VERSION,
        "@stylexjs/stylex": STYLEX_VERSION,
        "@stylexjs/unplugin": STYLEX_VERSION,
    }
