"""Exercise pre-publication installation checks with real distribution files."""

import io
import shutil
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import verify_install

pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="uv is required")


@pytest.fixture
def distributions(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """Create a wheel and an independently buildable sdist.

    Args:
        tmp_path: The temporary test directory.
        request: Whether to include an unavailable dependency in both artifacts.

    Returns:
        The directory containing both distributions.
    """
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_name = "install_check-1.0-py3-none-any.whl"
    metadata = "Metadata-Version: 2.3\nName: install-check\nVersion: 1.0\n"
    if getattr(request, "param", False):
        missing = tmp_path / "missing_dependency-1.0-py3-none-any.whl"
        metadata += f"Requires-Dist: missing-dependency @ {missing.as_uri()}\n"
    with zipfile.ZipFile(dist_dir / wheel_name, "w") as wheel:
        wheel.writestr("install_check.py", "VALUE = 1\n")
        wheel.writestr(
            "install_check-1.0.dist-info/METADATA",
            metadata,
        )
        wheel.writestr(
            "install_check-1.0.dist-info/WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        wheel.writestr("install_check-1.0.dist-info/RECORD", "")
    files = {
        "pyproject.toml": (
            b'[build-system]\nrequires = []\nbuild-backend = "backend"\n'
            b'backend-path = ["."]\n[project]\nname = "install-check"\nversion = "1.0"\n'
        ),
        "backend.py": (
            "from pathlib import Path\n"
            "import shutil\n"
            "def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):\n"
            f"    name = {wheel_name!r}\n"
            "    shutil.copyfile(Path(__file__).parent / name, Path(wheel_directory) / name)\n"
            "    return name\n"
        ).encode(),
        wheel_name: (dist_dir / wheel_name).read_bytes(),
    }
    with tarfile.open(dist_dir / "install_check-1.0.tar.gz", "w:gz") as sdist:
        for name, content in files.items():
            member = tarfile.TarInfo(f"install_check-1.0/{name}")
            member.size = len(content)
            sdist.addfile(member, io.BytesIO(content))
    return dist_dir


@pytest.mark.parametrize(
    "distributions",
    [False, True],
    indirect=True,
    ids=["no-dependencies", "unavailable-dependency"],
)
def test_installs_both_distributions(
    distributions: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """Both artifacts install without resolving unavailable runtime dependencies.

    Args:
        distributions: The built wheel and sdist.
        monkeypatch: The pytest monkeypatch fixture.
        capsys: The output capture fixture.
    """
    monkeypatch.setenv("UV_NO_BUILD", "1")
    monkeypatch.setenv("UV_NO_DEPS", "false")
    monkeypatch.setenv("DIST_DIR", str(distributions))
    assert verify_install.main() == 0
    output = capsys.readouterr().out
    assert "Verified installation of install_check-1.0-py3-none-any.whl" in output
    assert "Verified installation of install_check-1.0.tar.gz" in output


@pytest.mark.parametrize("suffix", [".whl", ".tar.gz"])
def test_rejects_broken_artifact(
    distributions: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
):
    """A working sibling artifact must not hide an un-installable archive.

    Args:
        distributions: The built wheel and sdist.
        monkeypatch: The pytest monkeypatch fixture.
        suffix: The artifact format to corrupt.
    """
    next(distributions.glob(f"*{suffix}")).write_bytes(b"broken archive")
    monkeypatch.setenv("DIST_DIR", str(distributions))
    assert verify_install.main() == 1


def test_requires_sdist_build(distributions: Path, monkeypatch: pytest.MonkeyPatch):
    """A valid wheel must not mask a source archive with an unavailable backend.

    Args:
        distributions: The built wheel and sdist.
        monkeypatch: The pytest monkeypatch fixture.
    """
    path = next(distributions.glob("*.tar.gz"))
    content = (
        b'[build-system]\nrequires = []\nbuild-backend = "missing_backend"\n'
        b'[project]\nname = "install-check"\nversion = "1.0"\n'
    )
    with tarfile.open(path, "w:gz") as sdist:
        member = tarfile.TarInfo("install_check-1.0/pyproject.toml")
        member.size = len(content)
        sdist.addfile(member, io.BytesIO(content))
    monkeypatch.setenv("DIST_DIR", str(distributions))
    assert verify_install.main() == 1


def test_checks_every_artifact(distributions: Path, monkeypatch: pytest.MonkeyPatch):
    """A valid pair must not hide another broken artifact in the release.

    Args:
        distributions: The built wheel and sdist.
        monkeypatch: The pytest monkeypatch fixture.
    """
    (distributions / "install_check-2.0.tar.gz").write_bytes(b"broken archive")
    monkeypatch.setenv("DIST_DIR", str(distributions))
    assert verify_install.main() == 1


@pytest.mark.parametrize("missing", [".whl", ".tar.gz", "both"])
def test_requires_both_formats(
    distributions: Path, monkeypatch: pytest.MonkeyPatch, missing: str
):
    """The check must fail when either expected distribution format is absent.

    Args:
        distributions: The built wheel and sdist.
        monkeypatch: The pytest monkeypatch fixture.
        missing: The artifact format to remove.
    """
    for path in distributions.iterdir():
        if missing == "both" or path.name.endswith(missing):
            path.unlink()
    monkeypatch.setenv("DIST_DIR", str(distributions))
    assert verify_install.main() == 1
