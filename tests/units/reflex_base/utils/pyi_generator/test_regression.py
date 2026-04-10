"""Regression tests for pyi_generator.

Runs PyiGenerator.scan_all against a directory of curated Python files and
compares the generated .pyi stubs against a set of golden reference files.

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
from reflex_base.utils.pyi_generator import PyiGenerator

_HERE = Path(__file__).resolve().parent
DATASET_DIR = _HERE / "dataset"
GOLDEN_DIR = _HERE / "golden"

_UPDATE_CMD = "python -m tests.units.reflex_base.utils.pyi_generator --update"


def _golden_path_for(source_path: Path) -> Path:
    """Map a dataset .py file to its golden .pyi counterpart.

    Args:
        source_path: The path to the dataset .py file.

    Returns:
        The corresponding path to the golden .pyi file.
    """
    relative = source_path.relative_to(DATASET_DIR)
    return GOLDEN_DIR / relative.with_suffix(".pyi")


def _normalize_stub(content: str) -> str:
    """Replace the absolute-path docstring header so golden files are portable.

    Args:
        content: The raw content of the generated .pyi file.

    Returns:
        The normalized content with the dataset path replaced by a placeholder.
    """
    lines = content.splitlines(keepends=True)
    normalized: list[str] = []
    for line in lines:
        if line.startswith('"""Stub file for '):
            normalized.append('"""Stub file for <dataset>"""\n')
        else:
            normalized.append(line)
    return "".join(normalized)


def _run_generator() -> dict[Path, str]:
    """Run PyiGenerator.scan_all on the dataset dir and collect results.

    Generated .pyi files are read back and then removed from the dataset
    tree so the working copy stays clean.  A ``try/finally`` block ensures
    generated files are always cleaned up, even if reading one of them fails.

    Returns:
        A mapping from dataset source .py files to their generated .pyi content.
    """
    gen = PyiGenerator()
    gen.scan_all([str(DATASET_DIR)])

    pyi_paths = [Path(pyi_str) for pyi_str, _hash in gen.written_files]
    try:
        results: dict[Path, str] = {}
        for pyi_path in pyi_paths:
            source_path = pyi_path.with_suffix(".py")
            results[source_path] = pyi_path.read_text()
    finally:
        for pyi_path in pyi_paths:
            pyi_path.unlink(missing_ok=True)
    return results


def update_golden_files() -> list[str]:
    """Regenerate all golden .pyi files from the dataset.

    Returns:
        A list of relative paths to the golden files that were updated.
    """
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for subdir in DATASET_DIR.rglob("*"):
        if subdir.is_dir() and subdir != DATASET_DIR:
            (GOLDEN_DIR / subdir.relative_to(DATASET_DIR)).mkdir(
                parents=True, exist_ok=True
            )

    generated = _run_generator()
    updated: list[str] = []
    for source_path, content in sorted(generated.items()):
        golden = _golden_path_for(source_path)
        golden.write_text(_normalize_stub(content))
        rel = golden.relative_to(_HERE)
        updated.append(str(rel))
        print(f"  updated: {rel}")

    expected_goldens = {_golden_path_for(s) for s in generated}
    for existing in GOLDEN_DIR.rglob("*.pyi"):
        if existing not in expected_goldens:
            existing.unlink()
            print(f"  removed stale: {existing.relative_to(_HERE)}")

    return updated


@pytest.fixture(scope="module")
def generated_stubs():
    """Run the generator once for the whole test module.

    Returns:
        A mapping from dataset source .py files to their generated .pyi content.
    """
    return _run_generator()


def _existing_golden_cases() -> list[tuple[str, Path]]:
    """Build test IDs from existing golden files (no generator run needed).

    Returns:
        A list of tuples containing test IDs and corresponding dataset source paths.
    """
    cases = []
    for golden in sorted(GOLDEN_DIR.rglob("*.pyi")):
        relative = golden.relative_to(GOLDEN_DIR)
        source = DATASET_DIR / relative.with_suffix(".py")
        tid = str(relative.with_suffix(".py")).replace("/", ".")
        cases.append((tid, source))
    return cases


@pytest.mark.parametrize(
    "source_path",
    [p for _, p in _existing_golden_cases()],
    ids=[tid for tid, _ in _existing_golden_cases()],
)
def test_pyi_golden(generated_stubs: dict[Path, str], source_path: Path):
    """Compare generated .pyi output against golden reference.

    Args:
        generated_stubs: The mapping of dataset source paths to generated .pyi content.
        source_path: The path to the dataset .py file for this test case.
    """
    golden_path = _golden_path_for(source_path)

    content = generated_stubs.get(source_path)
    if content is None:
        pytest.fail(
            f"pyi_generator produced no output for {source_path.name}, "
            f"but a golden file exists at {golden_path}"
        )

    normalized = _normalize_stub(content)
    expected = golden_path.read_text()

    if normalized != expected:
        diff = difflib.unified_diff(
            expected.splitlines(keepends=True),
            normalized.splitlines(keepends=True),
            fromfile=f"golden/{golden_path.name}",
            tofile=f"generated/{golden_path.name}",
        )
        pytest.fail(
            f"Generated stub differs from golden reference for {source_path.name}.\n"
            f"Run `{_UPDATE_CMD}` to regenerate.\n\n{''.join(diff)}"
        )


def test_no_extra_golden_files(generated_stubs: dict[Path, str]):
    """Ensure no golden files exist without corresponding dataset sources.

    Args:
        generated_stubs: The mapping of dataset source paths to generated .pyi content.
    """
    expected_goldens = {_golden_path_for(s) for s in generated_stubs}
    for existing in GOLDEN_DIR.rglob("*.pyi"):
        assert existing in expected_goldens, (
            f"Stale golden file {existing.relative_to(_HERE)} has no dataset source. "
            f"Run `{_UPDATE_CMD}` to clean up."
        )


def test_no_missing_golden_files(generated_stubs: dict[Path, str]):
    """Ensure every generated stub has a corresponding golden file.

    Catches the case where a new dataset file is added but ``--update`` is
    not run, so no golden reference exists and the new scenario silently
    goes untested.

    Args:
        generated_stubs: The mapping of dataset source paths to generated .pyi content.
    """
    existing_goldens = set(GOLDEN_DIR.rglob("*.pyi"))
    missing = []
    for source_path in sorted(generated_stubs):
        golden = _golden_path_for(source_path)
        if golden not in existing_goldens:
            missing.append(str(golden.relative_to(_HERE)))
    assert not missing, (
        f"Generated stubs have no golden files: {', '.join(missing)}. "
        f"Run `{_UPDATE_CMD}` to create them."
    )


def main():
    parser = argparse.ArgumentParser(description="pyi_generator regression test suite")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Regenerate golden .pyi files from the dataset.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that generated stubs match golden files (CI mode).",
    )
    args = parser.parse_args()

    if args.update:
        print(f"Regenerating golden files from {DATASET_DIR} ...")
        updated = update_golden_files()
        print(
            f"\nDone. {len(updated)} file(s) updated in {GOLDEN_DIR.relative_to(_HERE)}/"
        )
        print("Review the changes and commit them with your PR.")
    elif args.check:
        print("Checking generated stubs against golden files...")
        generated = _run_generator()
        failures = []
        for source_path, content in sorted(generated.items()):
            golden_path = _golden_path_for(source_path)
            if not golden_path.exists():
                failures.append(f"  {source_path.name}: missing golden file")
                continue
            if _normalize_stub(content) != golden_path.read_text():
                failures.append(f"  {source_path.name}: differs from golden")
        expected_goldens = {_golden_path_for(s) for s in generated}
        for existing in sorted(GOLDEN_DIR.rglob("*.pyi")):
            if existing not in expected_goldens:
                failures.append(
                    f"  {existing.relative_to(_HERE)}: stale golden (no dataset source)"
                )
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
