import json
import re
import shutil
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from reflex.config import Config
from reflex.reflex import cli
from reflex.testing import chdir
from reflex.utils.prerequisites import (
    CpuInfo,
    _update_next_config,
    cached_procedure,
    get_cpu_info,
    rename_imports_and_app_name,
)

runner = CliRunner()


@pytest.mark.parametrize(
    "config, export, expected_output",
    [
        (
            Config(
                app_name="test",
            ),
            False,
            'module.exports = {basePath: "", compress: true, trailingSlash: true, staticPageGenerationTimeout: 60, devIndicators: false};',
        ),
        (
            Config(
                app_name="test",
                static_page_generation_timeout=30,
            ),
            False,
            'module.exports = {basePath: "", compress: true, trailingSlash: true, staticPageGenerationTimeout: 30, devIndicators: false};',
        ),
        (
            Config(
                app_name="test",
                next_compression=False,
            ),
            False,
            'module.exports = {basePath: "", compress: false, trailingSlash: true, staticPageGenerationTimeout: 60, devIndicators: false};',
        ),
        (
            Config(
                app_name="test",
                frontend_path="/test",
            ),
            False,
            'module.exports = {basePath: "/test", compress: true, trailingSlash: true, staticPageGenerationTimeout: 60, devIndicators: false};',
        ),
        (
            Config(
                app_name="test",
                frontend_path="/test",
                next_compression=False,
            ),
            False,
            'module.exports = {basePath: "/test", compress: false, trailingSlash: true, staticPageGenerationTimeout: 60, devIndicators: false};',
        ),
        (
            Config(
                app_name="test",
            ),
            True,
            'module.exports = {basePath: "", compress: true, trailingSlash: true, staticPageGenerationTimeout: 60, devIndicators: false, output: "export", distDir: "_static"};',
        ),
        (
            Config(
                app_name="test",
                next_dev_indicators=True,
            ),
            True,
            'module.exports = {basePath: "", compress: true, trailingSlash: true, staticPageGenerationTimeout: 60, output: "export", distDir: "_static"};',
        ),
    ],
)
def test_update_next_config(config, export, expected_output):
    output = _update_next_config(config, export=export)
    assert output == expected_output


@pytest.mark.parametrize(
    ("transpile_packages", "expected_transpile_packages"),
    (
        (
            ["foo", "@bar/baz"],
            ["@bar/baz", "foo"],
        ),
        (
            ["foo", "@bar/baz", "foo", "@bar/baz@3.2.1"],
            ["@bar/baz", "foo"],
        ),
        (["@bar/baz", {"name": "foo"}], ["@bar/baz", "foo"]),
        (["@bar/baz", {"name": "@foo/baz"}], ["@bar/baz", "@foo/baz"]),
    ),
)
def test_transpile_packages(transpile_packages, expected_transpile_packages):
    output = _update_next_config(
        Config(app_name="test"),
        transpile_packages=transpile_packages,
    )
    transpile_packages_match = re.search(r"transpilePackages: (\[.*?\])", output)
    transpile_packages_json = transpile_packages_match.group(1)  # pyright: ignore [reportOptionalMemberAccess]
    actual_transpile_packages = sorted(json.loads(transpile_packages_json))
    assert actual_transpile_packages == expected_transpile_packages


def test_cached_procedure():
    call_count = 0

    @cached_procedure(tempfile.mktemp(), payload_fn=lambda: "constant")
    def _function_with_no_args():
        nonlocal call_count
        call_count += 1

    _function_with_no_args()
    assert call_count == 1
    _function_with_no_args()
    assert call_count == 1

    call_count = 0

    @cached_procedure(
        cache_file=tempfile.mktemp(),
        payload_fn=lambda *args, **kwargs: f"{repr(args), repr(kwargs)}",
    )
    def _function_with_some_args(*args, **kwargs):
        nonlocal call_count
        call_count += 1

    _function_with_some_args(1, y=2)
    assert call_count == 1
    _function_with_some_args(1, y=2)
    assert call_count == 1
    _function_with_some_args(100, y=300)
    assert call_count == 2
    _function_with_some_args(100, y=300)
    assert call_count == 2

    call_count = 0

    @cached_procedure(
        cache_file=None, cache_file_fn=tempfile.mktemp, payload_fn=lambda: "constant"
    )
    def _function_with_no_args_fn():
        nonlocal call_count
        call_count += 1

    _function_with_no_args_fn()
    assert call_count == 1
    _function_with_no_args_fn()
    assert call_count == 2


def test_get_cpu_info():
    cpu_info = get_cpu_info()
    assert cpu_info is not None
    assert isinstance(cpu_info, CpuInfo)
    assert cpu_info.model_name is not None

    for attr in ("manufacturer_id", "model_name", "address_width"):
        value = getattr(cpu_info, attr)
        assert value.strip() if attr != "address_width" else value


@pytest.fixture
def temp_directory():
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.mark.parametrize(
    "config_code,expected",
    [
        ("rx.Config(app_name='old_name')", 'rx.Config(app_name="new_name")'),
        ('rx.Config(app_name="old_name")', 'rx.Config(app_name="new_name")'),
        ("rx.Config('old_name')", 'rx.Config("new_name")'),
        ('rx.Config("old_name")', 'rx.Config("new_name")'),
    ],
)
def test_rename_imports_and_app_name(temp_directory, config_code, expected):
    file_path = temp_directory / "rxconfig.py"
    content = f"""
config = {config_code}
"""
    file_path.write_text(content)

    rename_imports_and_app_name(file_path, "old_name", "new_name")

    updated_content = file_path.read_text()
    expected_content = f"""
config = {expected}
"""
    assert updated_content == expected_content


def test_regex_edge_cases(temp_directory):
    file_path = temp_directory / "example.py"
    content = """
from old_name.module import something
import old_name
from old_name import something_else as alias
from old_name
"""
    file_path.write_text(content)

    rename_imports_and_app_name(file_path, "old_name", "new_name")

    updated_content = file_path.read_text()
    expected_content = """
from new_name.module import something
import new_name
from new_name import something_else as alias
from new_name
"""
    assert updated_content == expected_content


def test_cli_rename_command(temp_directory):
    foo_dir = temp_directory / "foo"
    foo_dir.mkdir()
    (foo_dir / "__init__").touch()
    (foo_dir / ".web").mkdir()
    (foo_dir / "assets").mkdir()
    (foo_dir / "foo").mkdir()
    (foo_dir / "foo" / "__init__.py").touch()
    (foo_dir / "rxconfig.py").touch()
    (foo_dir / "rxconfig.py").write_text(
        """
import reflex as rx

config = rx.Config(
    app_name="foo",
)
"""
    )
    (foo_dir / "foo" / "components").mkdir()
    (foo_dir / "foo" / "components" / "__init__.py").touch()
    (foo_dir / "foo" / "components" / "base.py").touch()
    (foo_dir / "foo" / "components" / "views.py").touch()
    (foo_dir / "foo" / "components" / "base.py").write_text(
        """
import reflex as rx
from foo.components import views
from foo.components.views import *
from .base import *

def random_component():
    return rx.fragment()
"""
    )
    (foo_dir / "foo" / "foo.py").touch()
    (foo_dir / "foo" / "foo.py").write_text(
        """
import reflex as rx
import foo.components.base
from foo.components.base import random_component

class State(rx.State):
  pass


def index():
   return rx.text("Hello, World!")

app = rx.App()
app.add_page(index)
"""
    )

    with chdir(temp_directory / "foo"):
        result = runner.invoke(cli, ["rename", "bar"])

    assert result.exit_code == 0
    assert (foo_dir / "rxconfig.py").read_text() == (
        """
import reflex as rx

config = rx.Config(
    app_name="bar",
)
"""
    )
    assert (foo_dir / "bar").exists()
    assert not (foo_dir / "foo").exists()
    assert (foo_dir / "bar" / "components" / "base.py").read_text() == (
        """
import reflex as rx
from bar.components import views
from bar.components.views import *
from .base import *

def random_component():
    return rx.fragment()
"""
    )
    assert (foo_dir / "bar" / "bar.py").exists()
    assert not (foo_dir / "bar" / "foo.py").exists()
    assert (foo_dir / "bar" / "bar.py").read_text() == (
        """
import reflex as rx
import bar.components.base
from bar.components.base import random_component

class State(rx.State):
  pass


def index():
   return rx.text("Hello, World!")

app = rx.App()
app.add_page(index)
"""
    )
