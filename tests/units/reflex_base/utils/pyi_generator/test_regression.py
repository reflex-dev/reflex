"""Regression tests for pyi_generator.

Runs pyi_generator against a directory of curated Python files and compares
the generated .pyi stubs against a set of golden reference files.

Usage as CLI to regenerate golden files:
    python -m tests.units.reflex_base.utils.pyi_generator --update

Usage as pytest:
    pytest tests/units/reflex_base/utils/pyi_generator/test_regression.py
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

import pytest

from reflex_base.utils.pyi_generator import _scan_file

_HERE = Path(__file__).resolve().parent
DATASET_DIR = _HERE / "dataset"
GOLDEN_DIR = _HERE / "golden"

_UPDATE_CMD = "python -m tests.units.reflex_base.utils.pyi_generator --update"

DATASET_MODULES = sorted(
    p
    for p in DATASET_DIR.rglob("*.py")
    if p.name != "__init__.py" and not p.name.startswith("_")
)

DATASET_INIT_MODULES = sorted(
    p for p in DATASET_DIR.rglob("__init__.py") if p != DATASET_DIR / "__init__.py"
)

ALL_DATASET_FILES = DATASET_MODULES + DATASET_INIT_MODULES


def _golden_path_for(module_path: Path) -> Path:
    """Map a dataset .py file to its golden .pyi counterpart."""
    relative = module_path.relative_to(DATASET_DIR)
    return GOLDEN_DIR / relative.with_suffix(".pyi")


def _generate_stub(module_path: Path) -> str | None:
    """Generate a .pyi stub for a single dataset module and return its content.

    Returns None if the generator decides no stub is needed.
    """
    result = _scan_file(module_path)
    if result is None:
        return None
    pyi_path = Path(result[0])
    content = pyi_path.read_text()
    pyi_path.unlink(missing_ok=True)
    return content


def _normalize_stub(content: str) -> str:
    """Strip the file-specific header (path line) so golden files are portable."""
    lines = content.splitlines(keepends=True)
    normalized: list[str] = []
    for line in lines:
        if line.startswith('"""Stub file for '):
            normalized.append('"""Stub file for <dataset>"""\n')
        else:
            normalized.append(line)
    return "".join(normalized)


def update_golden_files() -> list[str]:
    """Regenerate all golden .pyi files from the dataset.

    Returns a list of updated file names.
    """
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for subdir in DATASET_DIR.rglob("*"):
        if subdir.is_dir() and subdir != DATASET_DIR:
            (GOLDEN_DIR / subdir.relative_to(DATASET_DIR)).mkdir(
                parents=True, exist_ok=True
            )

    updated: list[str] = []
    for module_path in ALL_DATASET_FILES:
        content = _generate_stub(module_path)
        if content is None:
            continue
        golden = _golden_path_for(module_path)
        normalized = _normalize_stub(content)
        golden.write_text(normalized)
        updated.append(str(golden.relative_to(_HERE)))
        print(f"  updated: {golden.relative_to(_HERE)}")

    expected_goldens = {_golden_path_for(p) for p in ALL_DATASET_FILES}
    for existing in GOLDEN_DIR.rglob("*.pyi"):
        if existing not in expected_goldens:
            existing.unlink()
            print(f"  removed stale: {existing.relative_to(_HERE)}")

    return updated


def _get_test_cases() -> list[tuple[str, Path]]:
    """Build parameterized test cases: (test_id, module_path)."""
    cases = []
    for module_path in ALL_DATASET_FILES:
        golden = _golden_path_for(module_path)
        if golden.exists():
            test_id = str(module_path.relative_to(DATASET_DIR)).replace("/", ".")
            cases.append((test_id, module_path))
    return cases


@pytest.fixture(autouse=True, scope="module")
def _ensure_dataset_importable():
    """Ensure the dataset directory is on sys.path so modules can be imported."""
    repo_root = _HERE.parent.parent.parent.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


@pytest.mark.parametrize(
    "module_path",
    [p for _, p in _get_test_cases()],
    ids=[tid for tid, _ in _get_test_cases()],
)
def test_pyi_golden(module_path: Path):
    """Compare generated .pyi output against golden reference."""
    golden_path = _golden_path_for(module_path)
    if not golden_path.exists():
        pytest.skip(f"No golden file for {module_path.name}. Run `{_UPDATE_CMD}` to generate.")

    generated = _generate_stub(module_path)
    if generated is None:
        pytest.fail(
            f"pyi_generator produced no output for {module_path.name}, "
            f"but a golden file exists at {golden_path}"
        )

    normalized = _normalize_stub(generated)
    expected = golden_path.read_text()

    if normalized != expected:
        diff = difflib.unified_diff(
            expected.splitlines(keepends=True),
            normalized.splitlines(keepends=True),
            fromfile=f"golden/{golden_path.name}",
            tofile=f"generated/{golden_path.name}",
        )
        diff_text = "".join(diff)
        pytest.fail(
            f"Generated stub differs from golden reference for {module_path.name}.\n"
            f"Run `{_UPDATE_CMD}` to regenerate.\n\n{diff_text}"
        )


def test_no_extra_golden_files():
    """Ensure no golden files exist without corresponding dataset sources."""
    expected_goldens = {_golden_path_for(p) for p in ALL_DATASET_FILES}
    for existing in GOLDEN_DIR.rglob("*.pyi"):
        assert existing in expected_goldens, (
            f"Stale golden file {existing.relative_to(_HERE)} has no dataset source. "
            f"Run `{_UPDATE_CMD}` to clean up."
        )


def main():
    parser = argparse.ArgumentParser(description="pyi_generator regression test suite")
    parser.add_argument("--update", action="store_true", help="Regenerate golden .pyi files from the dataset.")
    parser.add_argument("--check", action="store_true", help="Check that generated stubs match golden files (CI mode).")
    args = parser.parse_args()

    if args.update:
        print(f"Regenerating golden files from {DATASET_DIR} ...")
        updated = update_golden_files()
        print(f"\nDone. {len(updated)} file(s) updated in {GOLDEN_DIR.relative_to(_HERE)}/")
        print("Review the changes and commit them with your PR.")
    elif args.check:
        print("Checking generated stubs against golden files...")
        failures = []
        for module_path in ALL_DATASET_FILES:
            golden_path = _golden_path_for(module_path)
            if not golden_path.exists():
                continue
            generated = _generate_stub(module_path)
            if generated is None:
                failures.append(f"  {module_path.name}: no output generated")
                continue
            normalized = _normalize_stub(generated)
            if normalized != golden_path.read_text():
                failures.append(f"  {module_path.name}: differs from golden")
        if failures:
            print("FAILED:")
            print("\n".join(failures))
            print(f"\nRun `{_UPDATE_CMD}` to regenerate.")
            sys.exit(1)
        print("All stubs match golden files.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
