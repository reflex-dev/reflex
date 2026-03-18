import os
import shutil
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from reflex.config import Config
from reflex.constants.installer import PackageJson
from reflex.reflex import cli
from reflex.testing import chdir
from reflex.utils.decorator import cached_procedure
from reflex.utils.frontend_skeleton import (
    _compile_package_json,
    _compile_vite_config,
    _update_react_router_config,
    sync_web_runtime_templates,
)
from reflex.utils.rename import rename_imports_and_app_name
from reflex.utils.telemetry import CpuInfo, get_cpu_info

runner = CliRunner()


@pytest.mark.parametrize(
    ("config", "export", "expected_output"),
    [
        (
            Config(
                app_name="test",
            ),
            False,
            'export default {"basename": "/", "future": {"unstable_optimizeDeps": true}, "ssr": false};',
        ),
        (
            Config(
                app_name="test",
                static_page_generation_timeout=30,
            ),
            False,
            'export default {"basename": "/", "future": {"unstable_optimizeDeps": true}, "ssr": false};',
        ),
        (
            Config(
                app_name="test",
                frontend_path="/test",
            ),
            False,
            'export default {"basename": "/test/", "future": {"unstable_optimizeDeps": true}, "ssr": false};',
        ),
        (
            Config(
                app_name="test",
            ),
            True,
            'export default {"basename": "/", "future": {"unstable_optimizeDeps": true}, "ssr": false, "prerender": true, "build": "build"};',
        ),
    ],
)
def test_update_react_router_config(config, export, expected_output):
    output = _update_react_router_config(config, prerender_routes=export)
    assert output == expected_output


@pytest.mark.parametrize(
    ("config", "expected_output"),
    [
        (
            Config(
                app_name="test",
                frontend_path="",
            ),
            'assetsDir: "/assets".slice(1),',
        ),
        (
            Config(
                app_name="test",
                frontend_path="/test",
            ),
            'assetsDir: "/test/assets".slice(1),',
        ),
        (
            Config(
                app_name="test",
                frontend_path="/test/",
            ),
            'assetsDir: "/test/assets".slice(1),',
        ),
    ],
)
def test_initialise_vite_config(config, expected_output):
    output = _compile_vite_config(config)
    assert expected_output in output


def test_sync_web_runtime_templates_preserves_generated_routes(
    temp_directory, monkeypatch
):
    template_dir = temp_directory / "template_web"
    web_dir = temp_directory / ".web"

    template_files = {
        "utils/state.js": "new state helper",
        "utils/helpers/upload.js": "new upload helper",
        "components/reflex/radix_themes_color_mode_provider.js": "new component",
        "app/entry.client.js": "new entry client",
        "app/routes.js": "new routes file",
        "styles/__reflex_style_reset.css": "new reset",
        "jsconfig.json": '{"compilerOptions": {}}',
        "postcss.config.js": "module.exports = {};",
        "vite-plugin-safari-cachebust.js": "export default function plugin() {}",
    }

    for relative_path, content in template_files.items():
        file_path = template_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    stale_files = {
        "utils/state.js": "old state helper",
        "utils/helpers/upload.js": "old upload helper",
        "components/reflex/radix_themes_color_mode_provider.js": "old component",
        "app/entry.client.js": "old entry client",
        "app/routes.js": "old routes file",
    }
    for relative_path, content in stale_files.items():
        file_path = web_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    generated_route = web_dir / "app" / "routes" / "compare._index.jsx"
    generated_route.parent.mkdir(parents=True, exist_ok=True)
    generated_route.write_text("generated route module")
    generated_context = web_dir / "utils" / "context.js"
    generated_context.parent.mkdir(parents=True, exist_ok=True)
    generated_context.write_text("generated context module")
    generated_component = web_dir / "components" / "utils.js"
    generated_component.parent.mkdir(parents=True, exist_ok=True)
    generated_component.write_text("generated component module")

    monkeypatch.setattr("reflex.utils.frontend_skeleton.get_web_dir", lambda: web_dir)
    monkeypatch.setattr(
        "reflex.utils.frontend_skeleton.constants.Templates.Dirs.WEB_TEMPLATE",
        os.fspath(template_dir),
    )

    sync_web_runtime_templates()

    assert (web_dir / "utils" / "state.js").read_text() == "new state helper"
    assert (web_dir / "utils" / "helpers" / "upload.js").read_text() == (
        "new upload helper"
    )
    assert (
        web_dir / "components" / "reflex" / "radix_themes_color_mode_provider.js"
    ).read_text() == "new component"
    assert (web_dir / "app" / "entry.client.js").read_text() == "new entry client"
    assert (web_dir / "app" / "routes.js").read_text() == "new routes file"
    assert generated_route.exists()
    assert generated_route.read_text() == "generated route module"
    assert generated_context.exists()
    assert generated_context.read_text() == "generated context module"
    assert generated_component.exists()
    assert generated_component.read_text() == "generated component module"


@pytest.mark.parametrize(
    ("frontend_path", "expected_command"),
    [
        ("", "sirv ./build/client --single 404.html --host"),
        ("/", "sirv ./build/client --single 404.html --host"),
        ("/app", "sirv ./build/client --single app/404.html --host"),
        ("/app/", "sirv ./build/client --single app/404.html --host"),
        ("app", "sirv ./build/client --single app/404.html --host"),
        (
            "/deep/nested/path",
            "sirv ./build/client --single deep/nested/path/404.html --host",
        ),
    ],
)
def test_get_prod_command(frontend_path, expected_command):
    assert PackageJson.Commands.get_prod_command(frontend_path) == expected_command


@pytest.mark.parametrize(
    ("config", "expected_prod_script"),
    [
        (
            Config(app_name="test"),
            "sirv ./build/client --single 404.html --host",
        ),
        (
            Config(app_name="test", frontend_path="/app"),
            "sirv ./build/client --single app/404.html --host",
        ),
        (
            Config(app_name="test", frontend_path="/deep/nested"),
            "sirv ./build/client --single deep/nested/404.html --host",
        ),
    ],
)
def test_compile_package_json_prod_command(config, expected_prod_script, monkeypatch):
    monkeypatch.setattr("reflex.utils.frontend_skeleton.get_config", lambda: config)
    output = _compile_package_json()
    assert f'"prod": "{expected_prod_script}"' in output


def test_cached_procedure():
    call_count = 0

    temp_file = tempfile.mktemp()

    @cached_procedure(
        cache_file_path=lambda: Path(temp_file), payload_fn=lambda: "constant"
    )
    def _function_with_no_args():
        nonlocal call_count
        call_count += 1

    _function_with_no_args()
    assert call_count == 1
    _function_with_no_args()
    assert call_count == 1

    call_count = 0

    another_temp_file = tempfile.mktemp()

    @cached_procedure(
        cache_file_path=lambda: Path(another_temp_file),
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
        cache_file_path=lambda: Path(tempfile.mktemp()), payload_fn=lambda: "constant"
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
    ("config_code", "expected"),
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

    assert result.exit_code == 0, result.output
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
