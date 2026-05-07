import shutil
import tempfile
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pytest
from click.testing import CliRunner
from reflex_base import constants
from reflex_base.config import Config
from reflex_base.utils.decorator import cached_procedure

from reflex.reflex import cli
from reflex.testing import chdir
from reflex.utils import frontend_skeleton, js_runtimes
from reflex.utils.frontend_skeleton import (
    _compile_vite_config,
    _update_react_router_config,
)
from reflex.utils.rename import rename_imports_and_app_name
from reflex.utils.telemetry import CpuInfo, get_cpu_info

runner = CliRunner()


def _patch_web_dir(monkeypatch: pytest.MonkeyPatch, web_dir: Path):
    monkeypatch.setattr(frontend_skeleton, "get_web_dir", lambda: web_dir)
    monkeypatch.setattr(js_runtimes, "get_web_dir", lambda: web_dir)


def _patch_frontend_package_manager(
    monkeypatch: pytest.MonkeyPatch,
    package_managers: list[str],
    run_package_manager,
):
    monkeypatch.setattr(
        js_runtimes,
        "get_nodejs_compatible_package_managers",
        lambda raise_on_none=True: package_managers,
    )
    monkeypatch.setattr(
        js_runtimes.processes,
        "run_process_with_fallbacks",
        run_package_manager,
    )


class _InstallFn(Protocol):
    def __call__(self, packages: set[str] | None = ...) -> None: ...


@dataclass
class InstallPackagesEnv:
    """Test environment for install_frontend_packages tests."""

    tmp_path: Path
    web_dir: Path
    root_lock: Path
    web_lock: Path
    config: Config
    patch_pm: Callable[[list[str], Callable], None]
    install: _InstallFn


@pytest.fixture
def install_packages_env(
    tmp_path, monkeypatch
) -> Generator[InstallPackagesEnv, None, None]:
    """Isolated environment for install_frontend_packages tests.

    Creates the web dir, patches get_web_dir, chdirs into tmp_path, and
    exposes the bun lock paths, a Config, a package-manager patch helper,
    and a runner that invokes install_frontend_packages.

    Yields:
        An InstallPackagesEnv with paths, config, and patch_pm/install helpers.
    """
    web_dir = tmp_path / constants.Dirs.WEB
    web_dir.mkdir()
    _patch_web_dir(monkeypatch, web_dir)
    config = Config(app_name="test")

    def patch_pm(package_managers: list[str], run_package_manager: Callable) -> None:
        _patch_frontend_package_manager(
            monkeypatch, package_managers, run_package_manager
        )

    def install(packages: set[str] | None = None) -> None:
        js_runtimes.install_frontend_packages(packages or set(), config)

    env = InstallPackagesEnv(
        tmp_path=tmp_path,
        web_dir=web_dir,
        root_lock=tmp_path / constants.Bun.LOCKFILE_PATH,
        web_lock=web_dir / constants.Bun.LOCKFILE_PATH,
        config=config,
        patch_pm=patch_pm,
        install=install,
    )
    with chdir(tmp_path):
        yield env


@pytest.fixture
def _stub_skeleton_initializers(monkeypatch):
    """Stub the frontend_skeleton initialize_* helpers to no-ops."""
    for name in (
        "initialize_package_json",
        "initialize_bun_config",
        "initialize_npmrc",
        "update_react_router_config",
        "initialize_vite_config",
    ):
        monkeypatch.setattr(frontend_skeleton, name, lambda: None)
    monkeypatch.setattr(frontend_skeleton, "get_project_hash", lambda: None)
    monkeypatch.setattr(
        frontend_skeleton, "init_reflex_json", lambda project_hash: None
    )


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
            'base: "/",',
        ),
        (
            Config(
                app_name="test",
                frontend_path="/test",
            ),
            'base: "/test/",',
        ),
        (
            Config(
                app_name="test",
                frontend_path="/test/",
            ),
            'base: "/test/",',
        ),
    ],
)
def test_initialise_vite_config(config, expected_output):
    output = _compile_vite_config(config)
    assert expected_output in output


@pytest.mark.usefixtures("_stub_skeleton_initializers")
def test_initialize_web_directory_restores_root_bun_lock(tmp_path, monkeypatch):
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / ".gitignore").write_text(".web\n")
    monkeypatch.setattr(
        frontend_skeleton.constants.Templates.Dirs, "WEB_TEMPLATE", template_dir
    )

    web_dir = tmp_path / constants.Dirs.WEB
    (tmp_path / constants.Bun.LOCKFILE_PATH).write_text("root-lock")
    _patch_web_dir(monkeypatch, web_dir)

    with chdir(tmp_path):
        frontend_skeleton.initialize_web_directory()

    assert (web_dir / constants.Bun.LOCKFILE_PATH).read_text() == "root-lock"


def test_install_frontend_packages_syncs_root_bun_lock(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env
    env.root_lock.write_text("root-lock")
    seen_web_lock_contents: list[str] = []

    def run_package_manager(args, **kwargs):
        seen_web_lock_contents.append(env.web_lock.read_text())
        env.web_lock.write_text("updated-lock")

    env.patch_pm(["bun"], run_package_manager)
    env.install()

    assert seen_web_lock_contents == ["root-lock"]
    assert env.root_lock.read_text() == "updated-lock"


def test_install_frontend_packages_creates_root_bun_lock(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env

    def run_package_manager(args, **kwargs):
        env.web_lock.write_text("generated-lock")

    env.patch_pm(["bun"], run_package_manager)
    env.install()

    assert env.root_lock.read_text() == "generated-lock"


def test_install_frontend_packages_does_not_persist_partial_bun_lock(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env
    env.root_lock.write_text("root-lock")
    call_count = 0
    error_message = "package installation failed"

    def run_package_manager(args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            assert env.web_lock.read_text() == "root-lock"
            env.web_lock.write_text("partial-lock")
            return
        raise RuntimeError(error_message)

    env.patch_pm(["bun"], run_package_manager)

    with pytest.raises(RuntimeError, match=error_message):
        env.install({"custom-package"})

    assert env.root_lock.read_text() == "root-lock"


def test_install_frontend_packages_cache_respects_root_bun_lock(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env
    env.root_lock.write_text("lock-v1")
    call_count = 0

    def run_package_manager(args, **kwargs):
        nonlocal call_count
        call_count += 1
        if env.root_lock.exists():
            env.web_lock.write_text(env.root_lock.read_text())
        else:
            env.web_lock.write_text("lock-regenerated")

    env.patch_pm(["bun"], run_package_manager)

    env.install()
    env.install()
    env.root_lock.write_text("lock-v2")
    env.install()
    env.root_lock.unlink()
    env.install()

    assert call_count == 3


def test_install_frontend_packages_npm_does_not_create_bogus_bun_lock(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env
    env.web_lock.write_text("stale-lock")
    call_count = 0

    def run_package_manager(args, **kwargs):
        nonlocal call_count
        call_count += 1
        assert not env.web_lock.exists()

    env.patch_pm(["npm"], run_package_manager)
    env.install()

    assert call_count == 1
    assert not env.root_lock.exists()
    assert not env.web_lock.exists()


def test_install_frontend_packages_cache_hit_refreshes_web_bun_lock(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env
    env.root_lock.write_text("root-lock")
    call_count = 0

    def run_package_manager(args, **kwargs):
        nonlocal call_count
        call_count += 1
        env.web_lock.write_text("root-lock")

    env.patch_pm(["bun"], run_package_manager)

    env.install()
    env.web_lock.unlink()
    env.install()

    assert call_count == 1
    assert env.web_lock.read_text() == "root-lock"


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
