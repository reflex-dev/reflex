"""Unit tests for scripts/check_min_deps.py (the minimum-dependency-version checker)."""

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import Mock

import pytest

# The script relies on ``tomllib`` (stdlib only on 3.11+); on 3.10 it falls back to the
# ``tomli`` backport. Skip the whole module when neither is available, so the tests still
# run on 3.10 whenever ``tomli`` happens to be installed.
if sys.version_info < (3, 11):
    pytest.importorskip(
        "tomli", reason="check_min_deps requires tomli on Python < 3.11"
    )

from scripts import check_min_deps


def test_install_target_without_extras(tmp_path: Path):
    package = check_min_deps.Package(
        name="pkg", project_dir=tmp_path, source_dir=tmp_path, extras=()
    )
    assert package.install_target() == str(tmp_path)


def test_install_target_with_extras(tmp_path: Path):
    package = check_min_deps.Package(
        name="pkg", project_dir=tmp_path, source_dir=tmp_path, extras=("db", "extra")
    )
    assert package.install_target() == f"{tmp_path}[db,extra]"


def test_single_source_dir(tmp_path: Path):
    module = tmp_path / "the_module"
    module.mkdir()
    (tmp_path / "not_a_dir.txt").write_text("")
    assert check_min_deps._single_source_dir(tmp_path) == module


def test_single_source_dir_requires_exactly_one(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    with pytest.raises(ValueError, match="exactly one module directory"):
        check_min_deps._single_source_dir(tmp_path)


def test_discover_packages_includes_root_first_and_skips_excluded():
    packages = check_min_deps.discover_packages()
    names = [p.name for p in packages]

    assert names[0] == "reflex", "root reflex package should be checked first"
    assert "reflex-base" in names
    assert not check_min_deps.SKIP_PACKAGES.intersection(names)

    for package in packages:
        assert package.source_dir.is_dir(), f"{package.name} source dir must exist"
        assert (package.project_dir / "pyproject.toml").is_file()


def test_discover_packages_records_optional_extras():
    by_name = {p.name: p for p in check_min_deps.discover_packages()}
    # The root package declares a `db` optional-dependency group.
    assert "db" in by_name["reflex"].extras


def test_pyright_errors_keys_and_filters_severity():
    report = {
        "generalDiagnostics": [
            {
                "file": "/abs/foo.py",
                "severity": "error",
                "message": "boom",
                "range": {"start": {"line": 9, "character": 4}},
            },
            {
                "file": "/abs/foo.py",
                "severity": "warning",
                "message": "ignore me",
                "range": {"start": {"line": 1, "character": 0}},
            },
        ]
    }
    errors = check_min_deps._pyright_errors(report)

    assert list(errors) == [("/abs/foo.py", 9, 4, "boom")]
    # Line/character are converted to 1-based in the display string.
    assert errors["/abs/foo.py", 9, 4, "boom"] == "/abs/foo.py:10:5 - error: boom"


def test_pyright_errors_delta_cancels_shared_noise():
    def report(messages: list[tuple[str, int]]) -> dict:
        return {
            "generalDiagnostics": [
                {
                    "file": "/abs/foo.py",
                    "severity": "error",
                    "message": msg,
                    "range": {"start": {"line": line, "character": 0}},
                }
                for msg, line in messages
            ]
        }

    # A shared, undeclared-import error appears in both resolutions; only the
    # minimum-version-specific error should remain in the delta.
    baseline = check_min_deps._pyright_errors(report([("missing optional import", 1)]))
    minimum = check_min_deps._pyright_errors(
        report([("missing optional import", 1), ("model_dump is unknown", 50)])
    )

    new = minimum.keys() - baseline.keys()
    assert new == {("/abs/foo.py", 50, 0, "model_dump is unknown")}


@pytest.mark.parametrize(
    ("requirement", "name", "is_dev"),
    [
        ("reflex-base >= 0.9.4", "reflex-base", False),
        ("reflex-base >= 0.9.5.dev1", "reflex-base", True),
        ("reflex-base>=0.9.5.dev1,<0.10", "reflex-base", True),
        ("pydantic >=2.12.0,<3.0", "pydantic", False),
        ("psutil >=7.0.0,<8.0; sys_platform == 'win32'", "psutil", False),
        ("granian[reload] >=2.5.5", "granian", False),
        ("granian[reload] >=2.5.5.dev0", "granian", True),
        # Name canonicalization (PEP 503) is handled by packaging.
        ("python_multipart >= 0.0.21", "python-multipart", False),
        ("ruamel.yaml >=0.18", "ruamel-yaml", False),
        ("foo ==1.0dev", "foo", True),
        ("foo ==1.0-dev2", "foo", True),
        ("foo ===1.0.dev1", "foo", True),
        ("foo >1.0.dev1", "foo", True),
        # A dev release only counts as a lower bound; upper-bound and exclusion clauses are
        # still resolvable from PyPI and must not be flagged.
        ("reflex-base >=1.0,!=2.0.dev1", "reflex-base", False),
        ("foo >=1.0,<2.0.dev3", "foo", False),
        ("foo <2.0.dev3", "foo", False),
        ("foo <=1.0.dev1", "foo", False),
        ("foo !=1.2.dev3", "foo", False),
        # A prefix match (``==1.2.*``) has no concrete version and is not a dev pin.
        ("foo ==1.2.*", "foo", False),
        # A direct URL reference carries no version specifier.
        ("foo @ https://example.dev/foo.whl", "foo", False),
        ("bar", "bar", False),
        ("pkg ~=1.2.3.dev4", "pkg", True),
        # An unparsable requirement yields an empty name and is not a dev pin.
        ("not a requirement!!", "", False),
    ],
)
def test_parse_requirement(requirement: str, name: str, is_dev: bool):
    assert check_min_deps._parse_requirement(requirement) == (name, is_dev)


def test_published_dependencies_includes_core_and_optional_groups():
    project = {
        "dependencies": ["a >= 1", "b >= 2"],
        "optional-dependencies": {"x": ["c >= 3"], "y": ["d >= 4"]},
    }
    assert check_min_deps._published_dependencies(project) == [
        "a >= 1",
        "b >= 2",
        "c >= 3",
        "d >= 4",
    ]


def test_published_dependencies_empty_project():
    assert check_min_deps._published_dependencies({}) == []


def test_workspace_package_dirs_maps_dist_names_to_dirs():
    dirs = check_min_deps._workspace_package_dirs()
    assert dirs["reflex"] == check_min_deps.REPO_ROOT
    assert dirs["reflex-base"] == check_min_deps.REPO_ROOT / "packages" / "reflex-base"
    # External (non-workspace) dependencies are not present.
    assert "pydantic" not in dirs


def test_local_sources_selects_every_workspace_member():
    dirs = check_min_deps._workspace_package_dirs()
    project = {
        "dependencies": [
            "reflex-base >= 0.9.5.dev1",  # workspace + dev pin -> included
            "pydantic >= 2.12.0",  # external -> excluded
            "reflex-components-lucide >= 0.9.0",  # workspace, plain floor -> included
            "reflex-base >= 0.9.5.dev1",  # duplicate -> deduped
        ],
        "optional-dependencies": {
            "x": [
                "reflex-components-radix >= 0.9.2.dev1"
            ],  # optional group -> included
        },
    }
    sources = check_min_deps._local_sources(project, dirs)

    assert dirs["reflex-base"] in sources
    assert dirs["reflex-components-lucide"] in sources
    assert dirs["reflex-components-radix"] in sources
    assert "pydantic" not in dirs
    assert len(sources) == len(set(sources)), "deduplicated"
    # Radix is reached directly, its own workspace requirements only through it, and they
    # have to be built first.
    assert sources.index(dirs["reflex-components-core"]) < sources.index(
        dirs["reflex-components-radix"]
    )


def test_local_sources_returns_the_closure_dependencies_first():
    """A sibling's own workspace requirements must be built before the sibling itself.

    `reflex-docgen` declares only `reflex`, but the root's build backend sets
    `require-runtime-dependencies`, so building it resolves the root's own `reflex-base`
    floor -- which is unpublished for the length of a release train.
    """
    sources = {p.name: p for p in check_min_deps.discover_packages()}[
        "reflex-docgen"
    ].local_sources
    root = check_min_deps.REPO_ROOT
    base = root / "packages" / "reflex-base"

    assert root in sources, "the directly declared sibling"
    assert base in sources, "reached only through the root's own dependencies"
    assert sources.index(base) < sources.index(root)


def test_local_sources_ignores_non_workspace_deps():
    dirs = check_min_deps._workspace_package_dirs()
    # Nothing outside the workspace can be served locally, dev-pinned or not.
    project = {"dependencies": ["somethirdparty >= 1.0.dev1", "pydantic >= 2.12.0"]}
    assert check_min_deps._local_sources(project, dirs) == ()


def test_discover_packages_records_local_sources():
    by_name = {p.name: p for p in check_min_deps.discover_packages()}
    for package in by_name.values():
        assert isinstance(package.local_sources, tuple)
        for source in package.local_sources:
            assert (source / "pyproject.toml").is_file()

    # A plain (non-dev) sibling floor must be served from the workspace too. A package is
    # written against the sibling's HEAD, so while the API it uses is unpublished, resolving
    # `latest` from PyPI reports the same error as the minimum resolution does, the delta
    # cancels it out, and the too-low floor ships.
    assert (
        check_min_deps.REPO_ROOT / "packages" / "reflex-base"
        in by_name["reflex-components-core"].local_sources
    )


class _FakeRun:
    """Records the commands ``_run`` is called with and replays canned results."""

    def __init__(
        self,
        returncode: int = 0,
        stdout: str = '{"generalDiagnostics": []}',
        built: dict[str, str] | None = None,
    ):
        """Record calls, and write the wheels a ``uv build`` would have produced.

        Args:
            returncode: The exit status every replayed call reports.
            stdout: The output every replayed call carries.
            built: Version to "build" each source directory at, keyed by directory name.
                A ``uv build`` for a listed directory drops a wheel in its ``--out-dir``,
                as the real command would, honouring a ``UV_DYNAMIC_VERSIONING_BYPASS``
                override the same way.
        """
        self.commands: list[list[str]] = []
        self.returncode = returncode
        self.stdout = stdout
        self.built = built or {}

    def __call__(self, cmd: list[str], **kwargs) -> "_FakeRun":
        command = [str(c) for c in cmd]
        self.commands.append(command)
        if command[:2] == ["uv", "build"] and self.returncode == 0:
            env = kwargs.get("env") or {}
            version = env.get("UV_DYNAMIC_VERSIONING_BYPASS") or self.built.get(
                Path(command[-1]).name
            )
            if version is not None:
                out_dir = Path(command[command.index("--out-dir") + 1])
                name = Path(command[-1]).name.replace("-", "_")
                (out_dir / f"{name}-{version}-py3-none-any.whl").touch()
        return self

    def command_starting_with(self, prefix: list[str]) -> list[str]:
        return next(c for c in self.commands if c[: len(prefix)] == prefix)


def _fake_package(local_sources: tuple[Path, ...] = ()) -> check_min_deps.Package:
    return check_min_deps.Package(
        name="reflex",
        project_dir=check_min_deps.REPO_ROOT,
        source_dir=check_min_deps.REPO_ROOT / "reflex",
        extras=(),
        local_sources=local_sources,
    )


def test_resolve_and_check_offers_the_wheelhouse_at_the_minimum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    fake_run = _FakeRun()
    monkeypatch.setattr(check_min_deps, "_run", fake_run)
    wheelhouse = tmp_path / "wheelhouse"

    errors, _ = check_min_deps._resolve_and_check(
        _fake_package((check_min_deps.REPO_ROOT / "packages" / "reflex-base",)),
        "3.12",
        tmp_path / "venv",
        tmp_path / "cfg.json",
        wheelhouse,
        (),
        lowest=True,
    )

    assert errors == {}
    install = fake_run.command_starting_with(["uv", "pip", "install"])
    # PyPI is still forced for every third-party dependency...
    assert "--no-sources" in install
    assert install[install.index("--resolution") + 1] == "lowest-direct"
    # ...but the workspace wheels stay resolvable, which is what makes an unpublished `*.dev`
    # floor installable at all. An index (not a second editable target) is required, so build
    # environments can see them too.
    assert install[install.index("--find-links") + 1] == str(wheelhouse)
    assert install.count("-e") == 1
    assert install[-1] == str(check_min_deps.REPO_ROOT)


def test_resolve_and_check_checks_modules_not_the_source_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Only real source is checked; generated `.pyi` stubs in the tree must not be.

    Stubs are absent from a fresh checkout and regenerated whenever the pyi build hook runs,
    including when another package's check builds this one as a sibling, so naming the
    directory would make the result depend on what else the run happened to build.

    Args:
        monkeypatch: Subprocess patching fixture.
        tmp_path: Temporary venv and config directory.
    """
    fake_run = _FakeRun()
    monkeypatch.setattr(check_min_deps, "_run", fake_run)

    check_min_deps._resolve_and_check(
        _fake_package(),
        "3.12",
        tmp_path / "venv",
        tmp_path / "cfg.json",
        None,
        (),
        lowest=False,
    )

    pyright = fake_run.command_starting_with(["pyright"])
    checked = pyright[pyright.index("--project") + 2 :]
    assert str(check_min_deps.REPO_ROOT / "reflex") not in pyright
    assert checked, "the package's modules are passed individually"
    assert all(module.endswith(".py") for module in checked)
    assert str(check_min_deps.REPO_ROOT / "reflex" / "app.py") in checked


def test_resolve_and_check_offers_the_wheelhouse_at_the_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """The `latest` resolution must see the workspace, or the delta has nothing to compare.

    Args:
        monkeypatch: Subprocess patching fixture.
        tmp_path: Temporary venv, config and wheelhouse directory.
    """
    fake_run = _FakeRun()
    monkeypatch.setattr(check_min_deps, "_run", fake_run)
    wheelhouse = tmp_path / "wheelhouse"

    check_min_deps._resolve_and_check(
        _fake_package((check_min_deps.REPO_ROOT / "packages" / "reflex-base",)),
        "3.12",
        tmp_path / "venv",
        tmp_path / "cfg.json",
        wheelhouse,
        ("reflex-base==0.9.12.post1.dev0+abc1234",),
        lowest=False,
    )

    install = fake_run.command_starting_with(["uv", "pip", "install"])
    assert install[install.index("--find-links") + 1] == str(wheelhouse)
    assert "--resolution" not in install
    # A plain floor would otherwise skip the workspace build for the published release,
    # because a resolver only considers pre-releases for a requirement that names one.
    assert install[-1] == "reflex-base==0.9.12.post1.dev0+abc1234"
    assert install[-3:-1] == ["-e", str(check_min_deps.REPO_ROOT)]


def test_resolve_and_check_without_local_sources_uses_no_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    fake_run = _FakeRun()
    monkeypatch.setattr(check_min_deps, "_run", fake_run)

    check_min_deps._resolve_and_check(
        _fake_package(),
        "3.12",
        tmp_path / "venv",
        tmp_path / "cfg.json",
        None,
        (),
        lowest=False,
    )

    install = fake_run.command_starting_with(["uv", "pip", "install"])
    assert "--find-links" not in install
    assert "--resolution" not in install
    assert install.count("-e") == 1


def test_build_local_wheelhouse_builds_every_source_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Each sibling is built once, at the version its own checkout derives.

    Args:
        monkeypatch: Subprocess patching fixture.
        tmp_path: Temporary wheelhouse directory.
    """
    fake_run = _FakeRun(
        built={
            # Both satisfy what the root package declares, so neither is rebuilt.
            "reflex-base": "0.9.12.post1.dev0+abc1234",
            "reflex-hosting-cli": "0.1.71.post1.dev0+abc1234",
        }
    )
    monkeypatch.setattr(check_min_deps, "_run", fake_run)
    sources = (
        check_min_deps.REPO_ROOT / "packages" / "reflex-base",
        check_min_deps.REPO_ROOT / "packages" / "reflex-hosting-cli",
    )
    wheelhouse = tmp_path / "nested" / "wheelhouse"

    pins, detail = check_min_deps._build_local_wheelhouse(
        _fake_package(sources), wheelhouse
    )
    assert detail is None
    assert pins == [
        "reflex-base==0.9.12.post1.dev0+abc1234",
        "reflex-hosting-cli==0.1.71.post1.dev0+abc1234",
    ]

    # ``uv build`` refuses to run against a missing ``--find-links`` directory.
    assert wheelhouse.is_dir()
    assert len(fake_run.commands) == len(sources)
    for source, build in zip(sources, fake_run.commands, strict=True):
        assert build[:4] == ["uv", "build", "--no-sources", "--wheel"]
        assert build[build.index("--out-dir") + 1] == str(wheelhouse)
        assert build[build.index("--find-links") + 1] == str(wheelhouse)
        assert build[-1] == str(source)


def test_build_local_wheelhouse_reports_build_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    fake_run = _FakeRun(returncode=1, stdout="boom")
    monkeypatch.setattr(check_min_deps, "_run", fake_run)
    sources = (
        check_min_deps.REPO_ROOT / "packages" / "reflex-base",
        check_min_deps.REPO_ROOT / "packages" / "reflex-hosting-cli",
    )

    pins, detail = check_min_deps._build_local_wheelhouse(
        _fake_package(sources), tmp_path / "wheelhouse"
    )

    assert pins is None
    assert detail == "boom"
    assert len(fake_run.commands) == 1, "the first failure should stop the build"


def _consumer(tmp_path: Path, requirement: str) -> check_min_deps.Package:
    """Build a package declaring one workspace sibling, with that sibling beside it.

    Args:
        tmp_path: Directory to create both packages in.
        requirement: The consumer's declared dependency on ``reflex-base``.

    Returns:
        A package whose sole local source is the sibling's project directory.
    """
    consumer = tmp_path / "consumer"
    sibling = tmp_path / "reflex-base"
    consumer.mkdir()
    sibling.mkdir()
    (consumer / "pyproject.toml").write_text(
        f'[project]\nname = "consumer"\ndependencies = ["{requirement}"]\n'
    )
    (sibling / "pyproject.toml").write_text('[project]\nname = "reflex-base"\n')
    return check_min_deps.Package(
        name="consumer",
        project_dir=consumer,
        source_dir=consumer,
        extras=(),
        local_sources=(sibling,),
    )


@pytest.mark.parametrize(
    ("requirement", "version"),
    [
        ("reflex-base>=0.9.12.dev0", "0.9.12.dev0"),
        ("reflex-base>=0.9.12.dev0,>=0.9.12.dev2", "0.9.12.dev2"),
        ("reflex-base==0.9.12.dev3", "0.9.12.dev3"),
        ("reflex-base>0.9.12.dev0", None),
    ],
)
def test_dev_wheel_version_satisfies_declared_floor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    requirement: str,
    version: str | None,
):
    """Development wheels honor usable declared floors without changing the parent env.

    Args:
        monkeypatch: Environment and build-process patching fixture.
        tmp_path: Temporary consumer and sibling package directory.
        requirement: The consumer's unpublished dependency requirement.
        version: The declared version to use, or None to retain normal versioning.
    """
    package = _consumer(tmp_path, requirement)
    monkeypatch.delenv("UV_DYNAMIC_VERSIONING_BYPASS", raising=False)
    build = Mock(return_value=subprocess.CompletedProcess([], 0, stdout=""))
    monkeypatch.setattr(check_min_deps, "_run", build)

    # Nothing is written to the wheelhouse, so every build reads as falling short.
    assert (
        check_min_deps._build_local_wheelhouse(package, tmp_path / "wheels")[1] is None
    )

    env = build.call_args.kwargs.get("env")
    if version is None:
        assert env is None
    else:
        assert env is not None
        assert env["UV_DYNAMIC_VERSIONING_BYPASS"] == version
        assert env["PATH"] == os.environ["PATH"]
    assert "UV_DYNAMIC_VERSIONING_BYPASS" not in os.environ


@pytest.mark.parametrize(
    "requirement",
    ["reflex-base >= 0.9.12", "reflex-base >= 0.9.12.dev0", "reflex-base"],
)
def test_build_local_wheelhouse_pins_the_exact_workspace_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, requirement: str
):
    """A satisfied workspace build is pinned, whatever shape the declared floor takes.

    Args:
        monkeypatch: Subprocess patching fixture.
        tmp_path: Temporary package and wheelhouse directory.
        requirement: The consumer's declared dependency on the sibling.
    """
    fake_run = _FakeRun(built={"reflex-base": "0.9.12.post1.dev0+abc1234"})
    monkeypatch.setattr(check_min_deps, "_run", fake_run)

    pins, detail = check_min_deps._build_local_wheelhouse(
        _consumer(tmp_path, requirement), tmp_path / "wheelhouse"
    )

    assert detail is None
    assert pins == ["reflex-base==0.9.12.post1.dev0+abc1234"]
    assert len(fake_run.commands) == 1, "a satisfying build is not redone"


def test_build_local_wheelhouse_skips_a_pin_the_declared_floor_excludes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A checkout whose tags predate the floor falls back to PyPI instead of failing.

    Args:
        monkeypatch: Subprocess patching fixture.
        tmp_path: Temporary package and wheelhouse directory.
    """
    # 0.9.11 does not reach the floor, and no development floor is declared to rebuild at.
    fake_run = _FakeRun(built={"reflex-base": "0.9.11.post1.dev0+abc1234"})
    monkeypatch.setattr(check_min_deps, "_run", fake_run)

    pins, detail = check_min_deps._build_local_wheelhouse(
        _consumer(tmp_path, "reflex-base >= 0.9.12"), tmp_path / "wheelhouse"
    )

    assert detail is None
    assert pins == []


def test_build_local_wheelhouse_redoes_a_build_below_a_development_floor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A build under a `*.dev` pin is redone at the floor, and that build is what gets pinned.

    Args:
        monkeypatch: Subprocess patching fixture.
        tmp_path: Temporary package and wheelhouse directory.
    """
    fake_run = _FakeRun(built={"reflex-base": "0.9.11.post1.dev0+abc1234"})
    monkeypatch.setattr(check_min_deps, "_run", fake_run)

    pins, detail = check_min_deps._build_local_wheelhouse(
        _consumer(tmp_path, "reflex-base >= 0.9.12.dev0"), tmp_path / "wheelhouse"
    )

    assert detail is None
    assert len(fake_run.commands) == 2, "the first build is redone at the floor"
    assert pins == ["reflex-base==0.9.12.dev0"]


def test_check_package_pins_the_workspace_only_at_the_baseline(
    monkeypatch: pytest.MonkeyPatch,
):
    """The minimum resolution must see the declared floors, not the workspace builds."""
    monkeypatch.setattr(
        check_min_deps,
        "_build_local_wheelhouse",
        lambda package, wheelhouse: (["pinned==1.0"], None),
    )
    seen: list[tuple[Sequence[str], bool]] = []

    def fake_resolve(package, python_version, venv, config, wheelhouse, pins, lowest):
        seen.append((pins, lowest))
        return {}, ""

    monkeypatch.setattr(check_min_deps, "_resolve_and_check", fake_resolve)

    result = check_min_deps.check_package(
        _fake_package((check_min_deps.REPO_ROOT / "packages" / "reflex-base",)), "3.12"
    )

    assert result.ok
    assert seen == [(["pinned==1.0"], False), ((), True)]


def test_check_package_reports_failed_wheelhouse_build(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        check_min_deps,
        "_build_local_wheelhouse",
        lambda package, wheelhouse: (None, "boom"),
    )
    monkeypatch.setattr(
        check_min_deps,
        "_resolve_and_check",
        lambda *args, **kwargs: pytest.fail("must not resolve without the dev wheels"),
    )

    result = check_min_deps.check_package(
        _fake_package((check_min_deps.REPO_ROOT / "packages" / "reflex-base",)), "3.12"
    )

    assert not result.ok
    assert result.stage == "resolution"
    assert "boom" in result.detail


def _write_pyproject(path: Path, dependencies: list[str], optional: str = "") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    pyproject = path / "pyproject.toml"
    deps = ", ".join(f'"{dep}"' for dep in dependencies)
    pyproject.write_text(
        f'[project]\nname = "demo"\ndependencies = [{deps}]\n{optional}'
    )
    return pyproject


def test_check_dev_pins_passes_when_no_dev_pins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    pyproject = _write_pyproject(tmp_path, ["reflex-base >= 0.9.4", "pydantic >= 2.12"])
    monkeypatch.setattr(
        check_min_deps, "_workspace_pyprojects", lambda: iter([("demo", pyproject)])
    )
    assert check_min_deps.check_dev_pins([]) == 0


def test_check_dev_pins_fails_and_reports_only_dev_pins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    pyproject = _write_pyproject(
        tmp_path, ["reflex-base >= 0.9.5.dev1", "pydantic >= 2.12.0"]
    )
    monkeypatch.setattr(
        check_min_deps, "_workspace_pyprojects", lambda: iter([("demo", pyproject)])
    )

    assert check_min_deps.check_dev_pins([]) == 1
    out = capsys.readouterr().out
    assert "reflex-base >= 0.9.5.dev1" in out
    assert "pydantic" not in out  # the non-dev pin is not flagged


def test_check_dev_pins_detects_dev_pin_in_optional_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    pyproject = _write_pyproject(
        tmp_path,
        [],
        optional='[project.optional-dependencies]\nextra = ["sibling >= 1.0.dev3"]\n',
    )
    monkeypatch.setattr(
        check_min_deps, "_workspace_pyprojects", lambda: iter([("demo", pyproject)])
    )
    assert check_min_deps.check_dev_pins([]) == 1


def test_check_dev_pins_unknown_package_returns_error(
    capsys: pytest.CaptureFixture[str],
):
    assert check_min_deps.check_dev_pins(["does-not-exist"]) == 1
    assert "unknown package" in capsys.readouterr().out


def test_check_dev_pins_scopes_to_named_package(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    clean = _write_pyproject(tmp_path / "clean", ["reflex-base >= 0.9.4"])
    dirty = _write_pyproject(tmp_path / "dirty", ["reflex-base >= 0.9.5.dev1"])
    monkeypatch.setattr(
        check_min_deps,
        "_workspace_pyprojects",
        lambda: iter([("clean", clean), ("dirty", dirty)]),
    )
    # Scoped to the clean package, the dirty package's dev pin is not consulted.
    assert check_min_deps.check_dev_pins(["clean"]) == 0
    assert check_min_deps.check_dev_pins(["dirty"]) == 1
