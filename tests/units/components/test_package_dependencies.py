from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[3]


def _package_dependencies(package: str) -> list[str]:
    pyproject = REPO_ROOT / "packages" / package / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())

    dependencies = list(data["project"].get("dependencies", []))
    dependencies.extend(
        data
        .get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("hooks", {})
        .get("reflex-pyi", {})
        .get("dependencies", [])
    )
    return dependencies


def _dependency_names(package: str) -> set[str]:
    return {dependency.split()[0] for dependency in _package_dependencies(package)}


def _source_imports(package: str, import_name: str) -> bool:
    source_root = REPO_ROOT / "packages" / package / "src"
    return any(
        import_name in source.read_text() for source in source_root.rglob("*.py")
    )


def test_core_does_not_depend_on_lucide_or_sonner():
    dependency_names = _dependency_names("reflex-components-core")

    assert "reflex-components-lucide" not in dependency_names
    assert "reflex-components-sonner" not in dependency_names
    assert not _source_imports("reflex-components-core", "reflex_components_lucide")
    assert not _source_imports("reflex-components-core", "reflex_components_sonner")


def test_sonner_does_not_depend_on_lucide():
    dependency_names = _dependency_names("reflex-components-sonner")

    assert "reflex-components-lucide" not in dependency_names
    assert not _source_imports("reflex-components-sonner", "reflex_components_lucide")
