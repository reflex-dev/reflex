"""Exercise pre-publication installation checks with real distribution files."""

import io
import json
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import verify_install

pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="uv is required")


@pytest.fixture
def distributions(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Create a wheel and an independently buildable sdist.

    Args:
        tmp_path: The temporary test directory.
        request: The dependency scenario to include in both artifacts.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The directory containing both distributions.
    """
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_name = "install_check-1.0-py3-none-any.whl"
    metadata = "Metadata-Version: 2.3\nName: install-check\nVersion: 1.0\n"
    scenario = getattr(request, "param", "none")
    missing = tmp_path / "missing_dependency-1.0-py3-none-any.whl"
    requirements = []
    if scenario == "workspace":
        requirements.append("missing-dependency>=9999")
    elif scenario != "none":
        requirements.append(f"missing-dependency @ {missing.as_uri()}")
    metadata += "".join(f"Requires-Dist: {req}\n" for req in requirements)
    sources = "[tool.uv.sources]\ninstall-check.workspace = true\n"
    if scenario == "workspace":
        sources += "missing-dependency.workspace = true\n"
    elif scenario == "external":
        sources += f'missing-dependency.url = "{missing.as_uri()}"\n'
    (tmp_path / "pyproject.toml").write_text(sources)
    monkeypatch.setattr(
        verify_install, "__file__", str(tmp_path / "scripts" / "verify_install.py")
    )
    monkeypatch.setenv("PACKAGE", "install-check")
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
            + f"dependencies = {json.dumps(requirements)}\n".encode()
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
    ["none", "workspace"],
    indirect=True,
    ids=["no-dependencies", "unpublished-sibling"],
)
def test_installs_both_distributions(
    distributions: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """Both artifacts install even when a workspace sibling is not yet published.

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


@pytest.mark.parametrize("distributions", ["third-party", "external"], indirect=True)
def test_rejects_unavailable_external_dependencies(
    distributions: Path, monkeypatch: pytest.MonkeyPatch
):
    """Unavailable dependencies outside the workspace must block publication.

    Args:
        distributions: The built wheel and sdist.
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setenv("UV_NO_DEPS", "1")
    monkeypatch.setenv("DIST_DIR", str(distributions))
    assert verify_install.main() == 1


@pytest.mark.parametrize("distributions", ["third-party"], indirect=True)
@pytest.mark.parametrize("suffix", [".whl", ".tar.gz"])
def test_resolves_each_artifacts_dependencies(distributions: Path, suffix: str):
    """Both formats must fail when their runtime dependencies cannot be installed.

    Args:
        distributions: The built wheel and sdist.
        suffix: The artifact format to install.
    """
    with pytest.raises(subprocess.CalledProcessError):
        verify_install.install_artifact(next(distributions.glob(f"*{suffix}")))


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
