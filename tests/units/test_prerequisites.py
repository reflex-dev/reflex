import json
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

    # Forward the initial-install helper through the same stub so tests can
    # inspect the install args without mocking subprocess primitives.
    def _stub_initial_install(primary_pm, env):
        args = [primary_pm, "install", "--legacy-peer-deps"]
        if js_runtimes._is_bun_package_manager(primary_pm):
            args.append("--frozen-lockfile")
        run_package_manager(
            args,
            show_status_message="Installing base frontend packages",
        )

    monkeypatch.setattr(js_runtimes, "_run_initial_install", _stub_initial_install)


class _InstallFn(Protocol):
    def __call__(self, packages: set[str] | None = ...) -> None: ...


@dataclass
class InstallPackagesEnv:
    """Test environment for install_frontend_packages tests."""

    tmp_path: Path
    web_dir: Path
    root_lock: Path
    web_lock: Path
    root_package_json: Path
    web_package_json: Path
    config: Config
    patch_pm: Callable[[list[str], Callable], None]
    install: _InstallFn


def _stub_framework_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty out framework deps so install call counts are predictable."""
    monkeypatch.setattr(constants.PackageJson, "DEPENDENCIES", {})
    monkeypatch.setattr(constants.PackageJson, "DEV_DEPENDENCIES", {})


@pytest.fixture
def install_packages_env(
    tmp_path, monkeypatch
) -> Generator[InstallPackagesEnv, None, None]:
    """Isolated environment for install_frontend_packages tests.

    Creates the web dir, patches get_web_dir, chdirs into tmp_path, and
    exposes the bun lock and package.json paths, a Config, a
    package-manager patch helper, and a runner that invokes
    install_frontend_packages. Framework dep constants are emptied so
    tests can reason about exactly the calls they trigger.

    Yields:
        An InstallPackagesEnv with paths, config, and patch_pm/install helpers.
    """
    web_dir = tmp_path / constants.Dirs.WEB
    web_dir.mkdir()
    _patch_web_dir(monkeypatch, web_dir)
    _stub_framework_packages(monkeypatch)
    config = Config(app_name="test")

    def patch_pm(package_managers: list[str], run_package_manager: Callable) -> None:
        _patch_frontend_package_manager(
            monkeypatch, package_managers, run_package_manager
        )

    def install(packages: set[str] | None = None) -> None:
        js_runtimes.install_frontend_packages(packages or set(), config)

    root_lock_dir = tmp_path / constants.Bun.ROOT_LOCKFILE_DIR
    root_lock_dir.mkdir(parents=True, exist_ok=True)
    env = InstallPackagesEnv(
        tmp_path=tmp_path,
        web_dir=web_dir,
        root_lock=root_lock_dir / constants.Bun.LOCKFILE_PATH,
        web_lock=web_dir / constants.Bun.LOCKFILE_PATH,
        root_package_json=root_lock_dir / constants.PackageJson.PATH,
        web_package_json=web_dir / constants.PackageJson.PATH,
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
    root_lock = tmp_path / constants.Bun.ROOT_LOCKFILE_DIR / constants.Bun.LOCKFILE_PATH
    root_lock.parent.mkdir(parents=True, exist_ok=True)
    root_lock.write_text("root-lock")
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
    env.install({"some-pkg@1.0.0"})

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
    install_runs = 0

    def run_package_manager(args, **kwargs):
        nonlocal install_runs
        # Count distinct cached-procedure invocations by detecting `install`.
        if "install" in args and "add" not in args and "remove" not in args:
            install_runs += 1
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

    # 4 install() calls minus one cache hit = 3 actual runs. The final run
    # sees no root lock so the web copy is removed before the run; the
    # initial `bun install` is then skipped, leaving 2 install invocations.
    assert install_runs == 2


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
    env.install({"some-pkg@1.0.0"})

    assert call_count >= 1
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


def _record_calls(env: InstallPackagesEnv) -> list[list[str]]:
    """Record `bun add`/`bun install` invocations into a list.

    Args:
        env: The install_packages_env fixture instance.

    Returns:
        A list that is appended to (in-place) on each package manager call.
    """
    calls: list[list[str]] = []

    def run_package_manager(args, **kwargs):
        calls.append(list(args))

    env.patch_pm(["bun"], run_package_manager)
    return calls


def test_install_frontend_packages_pinned_packages_single_call(
    install_packages_env: InstallPackagesEnv,
):
    """All-pinned packages produce a single add call without ``--only-missing``."""
    env = install_packages_env
    calls = _record_calls(env)

    env.install({"some-pkg@1.2.3", "@scope/pkg@4.5.6"})

    add_calls = [c for c in calls if "add" in c]
    assert len(add_calls) == 1
    pinned_call = add_calls[0]
    assert "--only-missing" not in pinned_call
    assert "some-pkg@1.2.3" in pinned_call
    assert "@scope/pkg@4.5.6" in pinned_call


def test_install_frontend_packages_unpinned_packages_single_call(
    install_packages_env: InstallPackagesEnv,
):
    """Unpinned packages are added without ``--only-missing`` when not present."""
    env = install_packages_env
    calls = _record_calls(env)

    env.install({"some-pkg", "@scope/pkg"})

    add_calls = [c for c in calls if "add" in c]
    assert len(add_calls) == 1
    unpinned_call = add_calls[0]
    assert "--only-missing" not in unpinned_call
    assert "some-pkg" in unpinned_call
    assert "@scope/pkg" in unpinned_call


def test_install_frontend_packages_combines_pinned_and_unpinned(
    install_packages_env: InstallPackagesEnv,
):
    """Pinned and unpinned packages are batched into one add call."""
    env = install_packages_env
    calls = _record_calls(env)

    env.install({"pinned@1.0.0", "unpinned"})

    add_calls = [c for c in calls if "add" in c]
    assert len(add_calls) == 1
    add_call = add_calls[0]
    assert "--only-missing" not in add_call
    assert "pinned@1.0.0" in add_call
    assert "unpinned" in add_call


def test_install_frontend_packages_skips_unpinned_already_in_package_json(
    install_packages_env: InstallPackagesEnv,
):
    """An unpinned package already in package.json is not re-added."""
    env = install_packages_env
    env.web_package_json.write_text(
        json.dumps({"dependencies": {"already-installed": "2.3.4"}})
    )
    calls = _record_calls(env)

    env.install({"already-installed", "fresh-pkg"})

    add_calls = [c for c in calls if "add" in c]
    assert len(add_calls) == 1
    add_call = add_calls[0]
    assert "fresh-pkg" in add_call
    assert "already-installed" not in add_call


def test_install_frontend_packages_skips_unpinned_dev_dep_already_in_package_json(
    install_packages_env: InstallPackagesEnv,
    monkeypatch,
):
    """An unpinned dev dep already in package.json is not re-added."""
    env = install_packages_env
    env.web_package_json.write_text(
        json.dumps({
            "devDependencies": {
                "already-dev": "1.2.3",
            }
        })
    )

    class FakePlugin:
        def get_frontend_dependencies(self):
            return set()

        def get_frontend_development_dependencies(self):
            return {"already-dev", "fresh-dev"}

    monkeypatch.setattr(env.config, "plugins", [FakePlugin()])
    calls = _record_calls(env)

    env.install()

    dev_add_calls = [c for c in calls if "add" in c and "-d" in c]
    assert len(dev_add_calls) == 1
    dev_call = dev_add_calls[0]
    assert "fresh-dev" in dev_call
    assert "already-dev" not in dev_call


def test_install_frontend_packages_unpinned_already_present_makes_no_add_call(
    install_packages_env: InstallPackagesEnv,
):
    """If every requested unpinned package is already present, no add call runs."""
    env = install_packages_env
    env.web_package_json.write_text(
        json.dumps({"dependencies": {"some-pkg": "1.0.0", "@scope/pkg": "2.0.0"}})
    )
    calls = _record_calls(env)

    env.install({"some-pkg", "@scope/pkg"})

    add_calls = [c for c in calls if "add" in c]
    assert add_calls == []


def test_install_frontend_packages_moves_misplaced_unpinned_dep_to_deps(
    install_packages_env: InstallPackagesEnv,
):
    """A regular dep currently sitting under devDependencies gets relocated."""
    env = install_packages_env
    env.web_package_json.write_text(
        json.dumps({"devDependencies": {"some-pkg": "1.2.3"}})
    )
    calls = _record_calls(env)

    env.install({"some-pkg"})

    remove_calls = [c for c in calls if "remove" in c]
    assert len(remove_calls) == 1
    assert "some-pkg" in remove_calls[0]

    add_calls = [c for c in calls if "add" in c]
    assert len(add_calls) == 1
    add_call = add_calls[0]
    assert "some-pkg" in add_call
    assert "-d" not in add_call


def test_install_frontend_packages_moves_misplaced_unpinned_dev_dep_to_dev(
    install_packages_env: InstallPackagesEnv,
    monkeypatch,
):
    """A dev dep currently sitting under dependencies gets relocated."""
    env = install_packages_env
    env.web_package_json.write_text(json.dumps({"dependencies": {"some-dev": "1.2.3"}}))

    class FakePlugin:
        def get_frontend_dependencies(self):
            return set()

        def get_frontend_development_dependencies(self):
            return {"some-dev"}

    monkeypatch.setattr(env.config, "plugins", [FakePlugin()])
    calls = _record_calls(env)

    env.install()

    remove_calls = [c for c in calls if "remove" in c]
    assert len(remove_calls) == 1
    assert "some-dev" in remove_calls[0]

    dev_add_calls = [c for c in calls if "add" in c and "-d" in c]
    assert len(dev_add_calls) == 1
    assert "some-dev" in dev_add_calls[0]

    deps_add_calls = [c for c in calls if "add" in c and "-d" not in c]
    assert deps_add_calls == []


def test_install_frontend_packages_moves_misplaced_pinned_framework_dep(
    install_packages_env: InstallPackagesEnv,
    monkeypatch,
):
    """A framework dep listed in the wrong section gets relocated and re-pinned."""
    env = install_packages_env
    monkeypatch.setattr(constants.PackageJson, "DEPENDENCIES", {"react": "19.2.5"})
    env.web_package_json.write_text(
        json.dumps({"devDependencies": {"react": "18.0.0"}})
    )
    calls = _record_calls(env)

    env.install()

    remove_calls = [c for c in calls if "remove" in c]
    assert len(remove_calls) == 1
    assert "react" in remove_calls[0]

    add_calls = [c for c in calls if "add" in c]
    assert len(add_calls) == 1
    add_call = add_calls[0]
    assert "react@19.2.5" in add_call
    assert "-d" not in add_call


def test_install_frontend_packages_conflict_prefers_regular_section(
    install_packages_env: InstallPackagesEnv,
    monkeypatch,
):
    """A package wanted by both deps and dev-deps lands in deps only."""
    env = install_packages_env

    class FakePlugin:
        def get_frontend_dependencies(self):
            return {"shared-pkg"}

        def get_frontend_development_dependencies(self):
            return {"shared-pkg"}

    monkeypatch.setattr(env.config, "plugins", [FakePlugin()])
    calls = _record_calls(env)

    env.install()

    add_calls = [c for c in calls if "add" in c]
    assert len(add_calls) == 1
    add_call = add_calls[0]
    assert "shared-pkg" in add_call
    assert "-d" not in add_call


def test_install_frontend_packages_dev_deps_added_before_regular_deps(
    install_packages_env: InstallPackagesEnv,
    monkeypatch,
):
    """When both sections have additions, the dev-deps add runs first."""
    env = install_packages_env

    class FakePlugin:
        def get_frontend_dependencies(self):
            return set()

        def get_frontend_development_dependencies(self):
            return {"some-dev"}

    monkeypatch.setattr(env.config, "plugins", [FakePlugin()])
    calls = _record_calls(env)

    env.install({"some-pkg"})

    add_calls = [c for c in calls if "add" in c]
    assert len(add_calls) == 2
    assert "-d" in add_calls[0]
    assert "some-dev" in add_calls[0]
    assert "-d" not in add_calls[1]
    assert "some-pkg" in add_calls[1]


def test_install_frontend_packages_conflict_with_misplaced_existing_entry(
    install_packages_env: InstallPackagesEnv,
    monkeypatch,
):
    """A conflicting name currently in devDeps is removed and re-added to deps."""
    env = install_packages_env
    env.web_package_json.write_text(
        json.dumps({"devDependencies": {"shared-pkg": "1.0.0"}})
    )

    class FakePlugin:
        def get_frontend_dependencies(self):
            return {"shared-pkg"}

        def get_frontend_development_dependencies(self):
            return {"shared-pkg"}

    monkeypatch.setattr(env.config, "plugins", [FakePlugin()])
    calls = _record_calls(env)

    env.install()

    remove_calls = [c for c in calls if "remove" in c]
    assert len(remove_calls) == 1
    assert "shared-pkg" in remove_calls[0]

    add_calls = [c for c in calls if "add" in c]
    assert len(add_calls) == 1
    assert "shared-pkg" in add_calls[0]
    assert "-d" not in add_calls[0]


def test_install_frontend_packages_does_not_move_correctly_placed_packages(
    install_packages_env: InstallPackagesEnv,
    monkeypatch,
):
    """Packages already in the right section trigger no remove/add."""
    env = install_packages_env
    env.web_package_json.write_text(
        json.dumps({
            "dependencies": {"regular": "1.0.0"},
            "devDependencies": {"dev-only": "2.0.0"},
        })
    )

    class FakePlugin:
        def get_frontend_dependencies(self):
            return set()

        def get_frontend_development_dependencies(self):
            return {"dev-only"}

    monkeypatch.setattr(env.config, "plugins", [FakePlugin()])
    calls = _record_calls(env)

    env.install({"regular"})

    assert [c for c in calls if "remove" in c] == []
    assert [c for c in calls if "add" in c] == []


def test_install_frontend_packages_pins_framework_dependencies(
    install_packages_env: InstallPackagesEnv,
    monkeypatch,
):
    """Framework dep constants are emitted as pinned ``name@version`` specs."""
    env = install_packages_env
    monkeypatch.setattr(
        constants.PackageJson, "DEPENDENCIES", {"react": "19.2.5", "isbot": "5.1.39"}
    )
    monkeypatch.setattr(constants.PackageJson, "DEV_DEPENDENCIES", {"vite": "8.0.9"})
    calls = _record_calls(env)

    env.install()

    add_calls = [c for c in calls if "add" in c]
    pin_deps_call = next(c for c in add_calls if "react@19.2.5" in c)
    assert "isbot@5.1.39" in pin_deps_call
    assert "-d" not in pin_deps_call
    assert "--only-missing" not in pin_deps_call

    pin_dev_deps_call = next(c for c in add_calls if "vite@8.0.9" in c)
    assert "-d" in pin_dev_deps_call
    assert "--only-missing" not in pin_dev_deps_call


def _record_calls_with_pm(
    env: InstallPackagesEnv, package_manager: str
) -> list[list[str]]:
    """Record package-manager invocations for an arbitrary primary PM.

    Args:
        env: The install_packages_env fixture instance.
        package_manager: The primary package manager path to patch in.

    Returns:
        A list that is appended to (in-place) on each package manager call.
    """
    calls: list[list[str]] = []

    def run_package_manager(args, **kwargs):
        calls.append(list(args))

    env.patch_pm([package_manager], run_package_manager)
    return calls


def test_install_frontend_packages_npm_skips_frozen_lockfile(
    install_packages_env: InstallPackagesEnv,
):
    """``--frozen-lockfile`` is bun-only and must not be passed to npm."""
    env = install_packages_env
    env.root_lock.write_text("npm-lock")
    calls = _record_calls_with_pm(env, "npm")

    env.install({"some-pkg@1.0.0"})

    install_calls = [c for c in calls if "install" in c]
    assert install_calls, "expected an initial `npm install` call"
    for call in install_calls:
        assert "--frozen-lockfile" not in call


def test_install_frontend_packages_bun_keeps_frozen_lockfile(
    install_packages_env: InstallPackagesEnv,
):
    """Bun still receives ``--frozen-lockfile`` on the initial install."""
    env = install_packages_env
    env.root_lock.write_text("bun-lock")
    calls = _record_calls_with_pm(env, "bun")

    env.install({"some-pkg"})

    install_calls = [c for c in calls if "install" in c]
    assert any("--frozen-lockfile" in c for c in install_calls)


def test_install_frontend_packages_persists_package_json_to_root(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env

    def run_package_manager(args, **kwargs):
        env.web_package_json.write_text('{"name": "reflex", "dependencies": {}}')

    env.patch_pm(["bun"], run_package_manager)
    env.install({"some-pkg@1.0.0"})

    assert env.root_package_json.read_text() == (
        '{"name": "reflex", "dependencies": {}}'
    )


def test_compile_package_json_recovers_dependencies(tmp_path, monkeypatch):
    """_compile_package_json should restore deps/devDeps from reflex.lock."""
    root_pkg = tmp_path / constants.Bun.ROOT_LOCKFILE_DIR / constants.PackageJson.PATH
    root_pkg.parent.mkdir(parents=True, exist_ok=True)
    root_pkg.write_text(
        '{"name": "reflex", "type": "module", "scripts": {"old": "x"}, '
        '"dependencies": {"react": "19.2.5"}, '
        '"devDependencies": {"vite": "8.0.9"}, '
        '"overrides": {"old-override": "1.0"}}'
    )
    monkeypatch.setattr(
        constants.PackageJson,
        "OVERRIDES",
        {"cookie": "1.1.1"},
    )

    with chdir(tmp_path):
        rendered = json.loads(frontend_skeleton._compile_package_json())

    assert rendered["dependencies"] == {"react": "19.2.5"}
    assert rendered["devDependencies"] == {"vite": "8.0.9"}
    assert rendered["overrides"] == {"cookie": "1.1.1"}
    assert rendered["scripts"]["dev"] == constants.PackageJson.Commands.DEV
    assert rendered["scripts"]["export"] == constants.PackageJson.Commands.EXPORT
    assert rendered["scripts"]["old"] == "x"


def test_compile_package_json_no_persisted_starts_empty(tmp_path, monkeypatch):
    """Without a persisted file, deps/devDeps are empty."""
    monkeypatch.setattr(
        constants.PackageJson,
        "OVERRIDES",
        {"cookie": "1.1.1"},
    )

    with chdir(tmp_path):
        rendered = json.loads(frontend_skeleton._compile_package_json())

    assert rendered["dependencies"] == {}
    assert rendered["devDependencies"] == {}
    assert rendered["overrides"] == {"cookie": "1.1.1"}


def test_compile_package_json_preserves_user_scripts(tmp_path):
    """User-added scripts are preserved; only dev/export are refreshed."""
    root_pkg = tmp_path / constants.Bun.ROOT_LOCKFILE_DIR / constants.PackageJson.PATH
    root_pkg.parent.mkdir(parents=True, exist_ok=True)
    root_pkg.write_text(
        json.dumps({
            "scripts": {
                "dev": "stale-dev",
                "export": "stale-export",
                "lint": "eslint .",
                "custom": "echo hi",
            },
            "dependencies": {},
            "devDependencies": {},
        })
    )

    with chdir(tmp_path):
        rendered = json.loads(frontend_skeleton._compile_package_json())

    assert rendered["scripts"]["lint"] == "eslint ."
    assert rendered["scripts"]["custom"] == "echo hi"
    assert rendered["scripts"]["dev"] == constants.PackageJson.Commands.DEV
    assert rendered["scripts"]["export"] == constants.PackageJson.Commands.EXPORT


def test_install_frontend_packages_removes_stale_dependencies(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env
    env.web_package_json.write_text(
        json.dumps({
            "dependencies": {
                "still-needed": "1.0.0",
                "stale-dep": "2.0.0",
            },
            "devDependencies": {
                "stale-dev-dep": "3.0.0",
            },
        })
    )
    calls = _record_calls(env)

    env.install({"still-needed"})

    remove_calls = [c for c in calls if "remove" in c]
    assert len(remove_calls) == 1
    remove_call = remove_calls[0]
    assert "stale-dep" in remove_call
    assert "stale-dev-dep" in remove_call
    assert "still-needed" not in remove_call


def test_install_frontend_packages_no_remove_when_all_needed(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env
    env.web_package_json.write_text(
        json.dumps({"dependencies": {"keep-me": "1.0.0"}, "devDependencies": {}})
    )
    calls = _record_calls(env)

    env.install({"keep-me"})

    remove_calls = [c for c in calls if "remove" in c]
    assert remove_calls == []


def test_install_frontend_packages_keeps_framework_deps_during_remove(
    install_packages_env: InstallPackagesEnv,
    monkeypatch,
):
    env = install_packages_env
    monkeypatch.setattr(constants.PackageJson, "DEPENDENCIES", {"react": "19.2.5"})
    monkeypatch.setattr(constants.PackageJson, "DEV_DEPENDENCIES", {"vite": "8.0.9"})
    env.web_package_json.write_text(
        json.dumps({
            "dependencies": {"react": "19.2.5", "stale-dep": "1.0.0"},
            "devDependencies": {"vite": "8.0.9"},
        })
    )
    calls = _record_calls(env)

    env.install()

    remove_calls = [c for c in calls if "remove" in c]
    assert len(remove_calls) == 1
    remove_call = remove_calls[0]
    assert "stale-dep" in remove_call
    assert "react" not in remove_call
    assert "vite" not in remove_call


def test_install_frontend_packages_skips_initial_install_on_fresh_project(
    install_packages_env: InstallPackagesEnv,
):
    """No lockfile yet → skip ``bun install`` (would fail under frozenLockfile)."""
    env = install_packages_env
    calls = _record_calls(env)

    env.install({"some-pkg@1.0.0"})

    install_calls = [c for c in calls if "install" in c and "add" not in c]
    assert install_calls == []
    add_calls = [c for c in calls if "add" in c]
    assert len(add_calls) == 1


def test_install_frontend_packages_runs_initial_install_when_lockfile_present(
    install_packages_env: InstallPackagesEnv,
):
    """Lockfile recovered → initial ``bun install`` runs to honor pins."""
    env = install_packages_env
    env.root_lock.write_text("persisted-lock")
    calls = _record_calls(env)

    env.install({"some-pkg@1.0.0"})

    install_calls = [c for c in calls if "install" in c and "add" not in c]
    assert len(install_calls) == 1


def test_install_frontend_packages_persists_npm_lock(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env
    web_npm_lock = env.web_dir / constants.Node.LOCKFILE_PATH
    root_npm_lock = (
        env.tmp_path / constants.Bun.ROOT_LOCKFILE_DIR / constants.Node.LOCKFILE_PATH
    )

    def run_package_manager(args, **kwargs):
        web_npm_lock.write_text("npm-lock-content")

    env.patch_pm(["npm"], run_package_manager)
    env.install({"some-pkg@1.0.0"})

    assert root_npm_lock.read_text() == "npm-lock-content"


def test_install_frontend_packages_restores_npm_lock(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env
    root_npm_lock = (
        env.tmp_path / constants.Bun.ROOT_LOCKFILE_DIR / constants.Node.LOCKFILE_PATH
    )
    root_npm_lock.write_text("persisted-npm-lock")
    web_npm_lock = env.web_dir / constants.Node.LOCKFILE_PATH
    seen_contents: list[str] = []

    def run_package_manager(args, **kwargs):
        seen_contents.append(web_npm_lock.read_text())

    env.patch_pm(["npm"], run_package_manager)
    env.install()

    assert seen_contents
    assert seen_contents[0] == "persisted-npm-lock"


def test_install_frontend_packages_npm_lock_change_invalidates_cache(
    install_packages_env: InstallPackagesEnv,
):
    env = install_packages_env
    root_npm_lock = (
        env.tmp_path / constants.Bun.ROOT_LOCKFILE_DIR / constants.Node.LOCKFILE_PATH
    )
    root_npm_lock.write_text("npm-lock-v1")
    web_npm_lock = env.web_dir / constants.Node.LOCKFILE_PATH
    call_count = 0

    def run_package_manager(args, **kwargs):
        nonlocal call_count
        call_count += 1
        if root_npm_lock.exists():
            web_npm_lock.write_text(root_npm_lock.read_text())

    env.patch_pm(["npm"], run_package_manager)

    env.install()
    first_run_calls = call_count
    env.install()
    assert call_count == first_run_calls  # cache hit, no extra calls

    root_npm_lock.write_text("npm-lock-v2")
    env.install()
    assert call_count > first_run_calls  # cache invalidated, install ran again


def test_prefer_npm_over_bun_implicit_from_npm_lock(tmp_path, monkeypatch):
    """A persisted package-lock.json with no bun.lock implies npm preference."""
    monkeypatch.delenv("REFLEX_USE_NPM", raising=False)
    monkeypatch.setattr(js_runtimes.constants, "IS_WINDOWS", False)
    root_dir = tmp_path / constants.Bun.ROOT_LOCKFILE_DIR
    root_dir.mkdir(parents=True)
    (root_dir / constants.Node.LOCKFILE_PATH).write_text("{}")

    with chdir(tmp_path):
        assert js_runtimes.prefer_npm_over_bun() is True


def test_prefer_npm_over_bun_implicit_disabled_when_bun_lock_present(
    tmp_path, monkeypatch
):
    """If both lockfiles are persisted, no implicit npm preference."""
    monkeypatch.delenv("REFLEX_USE_NPM", raising=False)
    monkeypatch.setattr(js_runtimes.constants, "IS_WINDOWS", False)
    root_dir = tmp_path / constants.Bun.ROOT_LOCKFILE_DIR
    root_dir.mkdir(parents=True)
    (root_dir / constants.Node.LOCKFILE_PATH).write_text("{}")
    (root_dir / constants.Bun.LOCKFILE_PATH).write_text("")

    with chdir(tmp_path):
        assert js_runtimes.prefer_npm_over_bun() is False


def test_prefer_npm_over_bun_explicit_false_overrides_implicit(tmp_path, monkeypatch):
    """REFLEX_USE_NPM=0 overrides the implicit npm-lock-only detection."""
    monkeypatch.setenv("REFLEX_USE_NPM", "0")
    monkeypatch.setattr(js_runtimes.constants, "IS_WINDOWS", False)
    root_dir = tmp_path / constants.Bun.ROOT_LOCKFILE_DIR
    root_dir.mkdir(parents=True)
    (root_dir / constants.Node.LOCKFILE_PATH).write_text("{}")

    with chdir(tmp_path):
        assert js_runtimes.prefer_npm_over_bun() is False


def test_prefer_npm_over_bun_explicit_true_wins(tmp_path, monkeypatch):
    """REFLEX_USE_NPM=1 forces npm regardless of persisted state."""
    monkeypatch.setenv("REFLEX_USE_NPM", "1")
    monkeypatch.setattr(js_runtimes.constants, "IS_WINDOWS", False)

    with chdir(tmp_path):
        assert js_runtimes.prefer_npm_over_bun() is True


def test_install_frontend_packages_does_not_fall_back(
    install_packages_env: InstallPackagesEnv,
):
    """A failing primary package manager surfaces the error, no fallback."""
    env = install_packages_env
    env.root_lock.write_text("persisted-lock")
    error_message = "primary failed"

    def run_package_manager(args, **kwargs):
        # If a fallback ever ran the test would not raise.
        assert kwargs.get("fallbacks") is None
        raise RuntimeError(error_message)

    env.patch_pm(["bun"], run_package_manager)

    with pytest.raises(RuntimeError, match=error_message):
        env.install({"some-pkg@1.0.0"})


@pytest.mark.usefixtures("install_packages_env")
def test_run_initial_install_frozen_lockfile_error_helpful_message(monkeypatch, capsys):
    """A frozen-lockfile mismatch surfaces a 'delete reflex.lock/package.json' hint."""

    class _FakeProcess:
        returncode = 1

    monkeypatch.setattr(
        js_runtimes.processes,
        "new_process",
        lambda *args, **kwargs: _FakeProcess(),
    )
    monkeypatch.setattr(
        js_runtimes.processes,
        "show_status",
        lambda message, process, suppress_errors=False: [
            "error: lockfile had changes, but lockfile is frozen\n",
        ],
    )

    with pytest.raises(SystemExit):
        js_runtimes._run_initial_install("bun", env={})

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "out of sync" in output
    assert constants.Bun.ROOT_LOCKFILE_DIR in output


@pytest.mark.usefixtures("install_packages_env")
def test_run_initial_install_other_error_replays_logs(monkeypatch, capsys):
    """Non-frozen-lockfile failures replay the captured logs."""

    class _FakeProcess:
        returncode = 1

    monkeypatch.setattr(
        js_runtimes.processes,
        "new_process",
        lambda *args, **kwargs: _FakeProcess(),
    )
    monkeypatch.setattr(
        js_runtimes.processes,
        "show_status",
        lambda message, process, suppress_errors=False: [
            "error: network unreachable\n",
        ],
    )

    with pytest.raises(SystemExit):
        js_runtimes._run_initial_install("bun", env={})

    captured = capsys.readouterr()
    assert "network unreachable" in captured.out + captured.err


def test_extract_package_name():
    assert js_runtimes._extract_package_name("react") == "react"
    assert js_runtimes._extract_package_name("react@1.2.3") == "react"
    assert js_runtimes._extract_package_name("@scope/pkg") == "@scope/pkg"
    assert js_runtimes._extract_package_name("@scope/pkg@1.2.3") == "@scope/pkg"


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
