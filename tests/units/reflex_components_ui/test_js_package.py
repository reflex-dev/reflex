"""Tests for the manifest of the javascript package reflex-components-ui embeds."""

import json
from pathlib import Path

from reflex_base import constants
from reflex_components_radix.plugin import RADIX_THEMES_PACKAGE

JS_PACKAGE = Path(__file__).parents[3] / "packages/reflex-components-ui/js"

# StyleX is 0.x and has broken its output between patch releases, so every
# package of it moves together and by an exact pin.
STYLEX_VERSION = "0.19.2"


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


def test_radix_themes_is_the_version_reflex_installs():
    """The tokens are generated from the Radix Themes an app gets.

    A page that mixes Radix components with these ones shows one palette only
    while both define the same values, so the generator reads the stylesheet of
    the version the Radix components install, and no other.
    """
    name, _, version = RADIX_THEMES_PACKAGE.rpartition("@")
    manifest = json.loads((JS_PACKAGE / "package.json").read_text())
    lock = json.loads((JS_PACKAGE / "package-lock.json").read_text())
    assert name == "@radix-ui/themes"
    assert manifest["devDependencies"][name] == version
    assert lock["packages"][f"node_modules/{name}"]["version"] == version


def test_vite_is_the_version_reflex_installs():
    """The live tests build their pages with the Vite an app is built with."""
    version = constants.PackageJson.DEV_DEPENDENCIES["vite"]
    manifest = json.loads((JS_PACKAGE / "package.json").read_text())
    lock = json.loads((JS_PACKAGE / "package-lock.json").read_text())
    assert manifest["devDependencies"]["vite"] == version
    assert lock["packages"]["node_modules/vite"]["version"] == version
