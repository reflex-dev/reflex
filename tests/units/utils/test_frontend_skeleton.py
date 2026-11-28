"""Tests for frontend package manifest synchronization."""

import json
from pathlib import Path
from typing import Any

import pytest
from reflex_base import constants
from reflex_base.compiler.templates import vite_config_template
from reflex_base.config import Config
from reflex_base.plugins import Plugin, VitePluginEntry
from reflex_base.utils.exceptions import InvalidVitePluginError

from reflex.utils import frontend_skeleton


@pytest.fixture
def package_json_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create isolated persisted and rendered package manifests.

    Args:
        tmp_path: Temporary app directory.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The rendered package.json path.
    """
    monkeypatch.chdir(tmp_path)
    web_dir = tmp_path / constants.Dirs.WEB
    web_dir.mkdir()
    monkeypatch.setattr(frontend_skeleton, "get_web_dir", lambda: web_dir)
    root_package = frontend_skeleton.get_root_lockfile_path(constants.PackageJson.PATH)
    root_package.parent.mkdir()
    root_package.write_text(
        json.dumps({"dependencies": {"test-pkg": "1.0.0"}, "description": "Test app"})
    )
    package_path = web_dir / constants.PackageJson.PATH
    package_path.write_text(frontend_skeleton._compile_package_json())
    return package_path


@pytest.mark.parametrize(
    ("indent", "sort_keys", "newline"),
    [(None, False, ""), (2, False, "\n"), (None, True, ""), (2, True, "\n")],
)
def test_sync_root_package_json_ignores_formatting(
    package_json_path: Path, indent: int | None, sort_keys: bool, newline: str
):
    """Formatting and key order changes preserve the existing file.

    Args:
        package_json_path: The rendered package.json path.
        indent: JSON indentation used by the package manager.
        sort_keys: Whether to reorder JSON object keys.
        newline: Trailing whitespace added by the package manager.
    """
    formatted = (
        json.dumps(
            json.loads(package_json_path.read_text()),
            indent=indent,
            sort_keys=sort_keys,
        )
        + newline
    )
    package_json_path.write_text(formatted)
    frontend_skeleton.sync_web_lockfiles_to_root()
    original_mtime = package_json_path.stat().st_mtime_ns

    for _ in range(2):
        assert frontend_skeleton.sync_root_package_json_to_web() is False
        assert package_json_path.read_text() == formatted
        assert package_json_path.stat().st_mtime_ns == original_mtime


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dependencies", {"test-pkg": "2.0.0"}),
        ("devDependencies", {"test-dev-pkg": "1.0.0"}),
        ("overrides", {"test-pkg": "2.0.0"}),
        ("scripts", {}),
        ("description", "Changed app"),
    ],
)
def test_sync_root_package_json_restores_content(package_json_path: Path, field, value):
    """Content differences still restore the persisted manifest and required scripts.

    Args:
        package_json_path: The rendered package.json path.
        field: Manifest field to change.
        value: Changed field value.
    """
    original = json.loads(package_json_path.read_text())
    package_json_path.write_text(json.dumps({**original, field: value}, indent=2))

    assert frontend_skeleton.sync_root_package_json_to_web() is True
    assert json.loads(package_json_path.read_text()) == original


@pytest.mark.parametrize("content", [None, "", "{invalid", "[]", "null", b"\xff{}"])
def test_sync_root_package_json_repairs_unusable_file(
    package_json_path: Path, content: str | bytes | None
):
    """Missing or invalid rendered manifests are replaced with the compiled object.

    Args:
        package_json_path: The rendered package.json path.
        content: Invalid file content (bytes that are not UTF-8), or None to
            remove the file.
    """
    original = json.loads(package_json_path.read_text())
    if content is None:
        package_json_path.unlink()
    elif isinstance(content, bytes):
        package_json_path.write_bytes(content)
    else:
        package_json_path.write_text(content)

    assert frontend_skeleton.sync_root_package_json_to_web() is (content is not None)
    assert json.loads(package_json_path.read_text()) == original


def _assert_bun_format(package_json_path: Path):
    """Assert a package.json is laid out the way bun rewrites it: UTF-8, LF only.

    Args:
        package_json_path: The package.json file to check.
    """
    raw = package_json_path.read_bytes()
    assert b"\r" not in raw
    content = raw.decode("utf-8")
    assert (
        content == json.dumps(json.loads(content), indent=2, ensure_ascii=False) + "\n"
    )


@pytest.mark.usefixtures("windows_text_io")
def test_rendered_package_json_matches_bun_format(package_json_path: Path):
    """Reflex renders package.json in bun's format, so bun rewrites leave no diff.

    Args:
        package_json_path: The rendered package.json path.
    """
    root_package = frontend_skeleton.get_root_lockfile_path(constants.PackageJson.PATH)
    root_package.write_text(
        json.dumps({"description": "Café ☃", "files": ["a", "b"]}), encoding="utf-8"
    )
    frontend_skeleton.initialize_package_json()
    _assert_bun_format(package_json_path)
    assert "Café ☃" in package_json_path.read_text(encoding="utf-8")

    package_json_path.write_text("{}")
    assert frontend_skeleton.sync_root_package_json_to_web() is True
    _assert_bun_format(package_json_path)


@pytest.mark.usefixtures("windows_text_io")
def test_update_package_json_overrides_matches_bun_format(
    package_json_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Merging the framework overrides writes package.json in bun's format.

    Args:
        package_json_path: The rendered package.json path.
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setattr(constants.PackageJson, "OVERRIDES", {"test-pkg": "1.0.1"})
    package_json_path.write_text(json.dumps(json.loads(package_json_path.read_text())))

    assert frontend_skeleton.update_package_json_overrides() is True
    _assert_bun_format(package_json_path)


class _VitePlugins(Plugin):
    """A plugin that contributes the Vite plugin entries it was created with."""

    def __init__(self, *entries: Any):
        """Store the entries to contribute.

        Args:
            entries: What ``get_vite_plugins`` returns.
        """
        self.entries = entries

    def get_vite_plugins(self, **context) -> Any:
        """Contribute the stored entries.

        Args:
            context: The context for the plugin.

        Returns:
            The stored entries.
        """
        return self.entries


class _OtherVitePlugins(_VitePlugins):
    """A second plugin type, to tell plugins apart in an error."""


_SHARED_IMPORT = 'import { Features } from "lightningcss"'
_FIRST = VitePluginEntry(
    imports=['import first from "first-plugin"', _SHARED_IMPORT],
    call="first(Features.Nesting)",
)
_SECOND = VitePluginEntry(imports=(_SHARED_IMPORT,), call="[second()]")
_THIRD = VitePluginEntry(call='{ name: "third" }')


def test_get_vite_plugins_follows_plugin_then_entry_order():
    """Entries come in ``rxconfig.py`` plugin order, then each plugin's own order."""
    plugins = [_VitePlugins(_SECOND, _THIRD), Plugin(), _OtherVitePlugins(_FIRST)]

    assert frontend_skeleton._get_vite_plugins(plugins) == [_SECOND, _THIRD, _FIRST]
    assert frontend_skeleton._get_vite_plugins([Plugin()]) == []


def test_compile_vite_config_renders_plugin_entries():
    """The compiled file is the template rendered with every plugin's entries."""
    config = Config(
        app_name="test", plugins=[_VitePlugins(_FIRST), _OtherVitePlugins(_SECOND)]
    )
    template_args = {
        "base": "/",
        "hmr": True,
        "force_full_reload": False,
        "experimental_hmr": False,
        "sourcemap": False,
    }
    without_plugins = vite_config_template(**template_args)
    rendered = frontend_skeleton._compile_vite_config(config)

    assert rendered == vite_config_template(
        **template_args, vite_plugins=[_FIRST, _SECOND]
    )
    assert rendered != without_plugins
    assert (
        frontend_skeleton._compile_vite_config(Config(app_name="test"))
        == without_plugins
    )


@pytest.mark.parametrize(
    ("entry", "problem"),
    [
        (
            ('import a from "a"', "a()"),
            "is a tuple, not a VitePluginEntry",
        ),
        (
            VitePluginEntry(call="  "),
            "has call='  ', which is not a JavaScript expression",
        ),
        (
            VitePluginEntry(call=None),  # pyright: ignore[reportArgumentType]
            "has call=None, which is not a JavaScript expression",
        ),
        (
            VitePluginEntry(call="a();\n"),
            "has call='a();\\n', which must be an expression without a trailing ';'",
        ),
        (
            VitePluginEntry(call="a(),"),
            "has call='a(),', which must be an expression without a trailing ','",
        ),
        (
            VitePluginEntry(imports='import a from "a"', call="a()"),
            (
                "has imports='import a from \"a\"', which must be a sequence of "
                "import statements, not a single string"
            ),
        ),
        (
            VitePluginEntry(imports=None, call="a()"),  # pyright: ignore[reportArgumentType]
            "has imports=None, which must be a sequence of import statements",
        ),
        (
            VitePluginEntry(imports=['import a from "a"', "a"], call="a()"),
            "has 'a' in imports, which is not an import statement",
        ),
        (
            VitePluginEntry(imports=['const a = await import("a")'], call="a()"),
            (
                "has 'const a = await import(\"a\")' in imports, which is not an "
                "import statement"
            ),
        ),
        (
            VitePluginEntry(imports=['import("a")'], call="a()"),
            "has 'import(\"a\")' in imports, which is not an import statement",
        ),
        (
            VitePluginEntry(imports=[b"import a"], call="a()"),  # pyright: ignore[reportArgumentType]
            "has b'import a' in imports, which is not an import statement",
        ),
    ],
)
def test_get_vite_plugins_rejects_malformed_entry(entry: Any, problem: str):
    """A malformed entry fails the compile, naming the plugin and the entry.

    Args:
        entry: The malformed entry.
        problem: What the error says is wrong with it.
    """
    plugins = [_VitePlugins(_FIRST), _OtherVitePlugins(_SECOND, entry)]

    with pytest.raises(InvalidVitePluginError) as err:
        frontend_skeleton._get_vite_plugins(plugins)

    assert str(err.value) == (
        "_OtherVitePlugins.get_vite_plugins() returned an invalid entry: "
        f"entry 1 {problem}."
    )


@pytest.mark.parametrize(
    "statement",
    [
        'import a from "a"',
        "import a, { b } from 'a';",
        'import{ a } from "a"',
        'import * as a from "a"',
        'import "a"',
        "import'a'",
        '\n  import a from "a";\n',
    ],
)
def test_get_vite_plugins_accepts_import_statement_forms(statement: str):
    """Every static import form is accepted.

    Args:
        statement: The import statement.
    """
    entry = VitePluginEntry(imports=[statement], call="a()")

    assert frontend_skeleton._get_vite_plugins([_VitePlugins(entry)]) == [entry]
