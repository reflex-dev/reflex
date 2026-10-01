"""Unit tests for reflex/custom_components/custom_components.py."""

from __future__ import annotations

from pathlib import Path

from reflex.custom_components import custom_components


def test_make_pyi_files_delegates_recursive_scan_without_path_walk(
    monkeypatch, tmp_path: Path
):
    """``_make_pyi_files`` delegates recursive scanning without ``Path.walk``.

    ``pathlib.Path.walk`` only exists on Python 3.12+, but Reflex supports 3.10
    and 3.11 too, so the build must not depend on it. ``Path.walk`` is removed
    here to reproduce the 3.10/3.11 environment on any interpreter.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path: A temporary directory used as the project root.
    """
    package = tmp_path / "my_component"
    nested = package / "sub"
    nested.mkdir(parents=True)
    (package / "__pycache__").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / ".hidden").mkdir()

    scans: list[list[Path]] = []

    class _RecordingGenerator:
        def scan_all(self, targets, *_args, **_kwargs):
            scans.append([Path(target) for target in targets])

    monkeypatch.setattr(
        "reflex_base.utils.pyi_generator.PyiGenerator", _RecordingGenerator
    )
    monkeypatch.delattr(Path, "walk", raising=False)
    monkeypatch.chdir(tmp_path)

    custom_components._make_pyi_files()

    assert scans == [[package]]


def test_share_reports_the_retired_gallery_without_contacting_it(monkeypatch):
    """``reflex component share`` deprecates itself and sends nothing anywhere.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    import httpx
    from click.testing import CliRunner

    deprecations: list[dict] = []
    monkeypatch.setattr(
        custom_components.console, "deprecate", lambda **kw: deprecations.append(kw)
    )

    def _refuse(*_args, **_kwargs):
        msg = "share must not make a request"
        raise AssertionError(msg)

    monkeypatch.setattr(httpx, "post", _refuse)

    result = CliRunner().invoke(custom_components.custom_components_cli, ["share"])

    assert result.exit_code == 0, result.output
    assert [d["feature_name"] for d in deprecations] == ["reflex component share"]
    assert deprecations[0]["removal_version"] == "1.0"
