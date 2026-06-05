"""Unit tests for scripts/check_min_deps.py (the minimum-dependency-version checker)."""

import sys
from pathlib import Path

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
    ("raw", "expected"),
    [
        ("reflex-base", "reflex-base"),
        ("python_multipart", "python-multipart"),
        ("Typing_Extensions", "typing-extensions"),
        ("ruamel.yaml", "ruamel-yaml"),
        ("Foo__Bar.Baz", "foo-bar-baz"),
    ],
)
def test_normalize_name(raw: str, expected: str):
    assert check_min_deps._normalize_name(raw) == expected


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
        ("python_multipart >= 0.0.21", "python-multipart", False),
        ("foo ==1.0dev", "foo", True),
        ("foo ==1.0-dev2", "foo", True),
        # A ".dev" URL host is a direct reference, not a development-release version pin.
        ("foo @ https://example.dev/foo.whl", "foo", False),
        ("bar", "bar", False),
        ("pkg ~=1.2.3.dev4", "pkg", True),
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


def test_local_dev_sources_selects_only_dev_pinned_workspace_members():
    dirs = check_min_deps._workspace_package_dirs()
    project = {
        "dependencies": [
            "reflex-base >= 0.9.5.dev1",  # workspace + dev -> included
            "pydantic >= 2.12.0",  # external -> excluded
            "reflex-components-lucide >= 0.9.0",  # workspace, non-dev -> excluded
            "reflex-base >= 0.9.5.dev1",  # duplicate -> deduped
        ],
        "optional-dependencies": {
            "x": ["reflex-components-radix >= 0.9.2.dev1"],  # dev pin in optional group
        },
    }
    assert check_min_deps._local_dev_sources(project, dirs) == (
        dirs["reflex-base"],
        dirs["reflex-components-radix"],
    )


def test_local_dev_sources_ignores_dev_pinned_non_workspace_dep():
    dirs = check_min_deps._workspace_package_dirs()
    # An external package's dev pin cannot be served locally, so it is not selected.
    project = {"dependencies": ["somethirdparty >= 1.0.dev1"]}
    assert check_min_deps._local_dev_sources(project, dirs) == ()


def test_discover_packages_records_local_dev_sources():
    for package in check_min_deps.discover_packages():
        assert isinstance(package.local_dev_sources, tuple)
        for source in package.local_dev_sources:
            assert (source / "pyproject.toml").is_file()


def test_resolve_and_check_appends_local_dev_sources_as_editables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    captured: list[list[str]] = []

    class _Done:
        returncode = 0
        stdout = '{"generalDiagnostics": []}'

    def fake_run(cmd: list[str], **kwargs: object) -> _Done:
        captured.append([str(c) for c in cmd])
        return _Done()

    monkeypatch.setattr(check_min_deps, "_run", fake_run)
    dev_source = check_min_deps.REPO_ROOT / "packages" / "reflex-base"
    package = check_min_deps.Package(
        name="reflex",
        project_dir=check_min_deps.REPO_ROOT,
        source_dir=check_min_deps.REPO_ROOT / "reflex",
        extras=(),
        local_dev_sources=(dev_source,),
    )

    errors, _ = check_min_deps._resolve_and_check(
        package, "3.12", tmp_path / "venv", tmp_path / "cfg.json", lowest=True
    )

    assert errors == {}
    install = next(c for c in captured if c[:3] == ["uv", "pip", "install"])
    # PyPI is still forced for every non-dev dependency...
    assert "--no-sources" in install
    assert install[install.index("--resolution") + 1] == "lowest-direct"
    # ...but the dev-pinned sibling is provided editable from its local checkout.
    assert install.count("-e") == 2
    assert str(dev_source) in install


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
