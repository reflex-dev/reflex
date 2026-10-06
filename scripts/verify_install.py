"""Install each release artifact independently before allowing publication.

Run from the publish workflow's post-build hook with PACKAGE and DIST_DIR in the
environment.
Use fresh virtual environments outside the checkout with no uv cache or
configuration so a working wheel cannot mask a broken sdist. Resolve runtime
dependencies except workspace siblings whose versions may not be published yet.
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "tomli; python_version < '3.11'",
# ]
# ///

import os
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # pyright: ignore[reportMissingImports]


def workspace_siblings(package: str) -> tuple[str, ...]:
    """Find other workspace packages whose releases may still be pending.

    Args:
        package: The package being verified, which must not be excluded.

    Returns:
        Names explicitly declared as workspace sources in the checkout.
    """
    with (Path(__file__).resolve().parent.parent / "pyproject.toml").open("rb") as f:
        project = tomllib.load(f)
    sources = project.get("tool", {}).get("uv", {}).get("sources", {})
    return tuple(
        name
        for name, source in sources.items()
        if source.get("workspace") and name != package
    )


def install_artifact(artifact: Path, excluded_packages: tuple[str, ...] = ()) -> None:
    """Install one archive and its external dependencies in isolation.

    Args:
        artifact: The absolute path to a wheel or source distribution.
        excluded_packages: Workspace siblings exempt from dependency resolution.

    Raises:
        subprocess.CalledProcessError: If environment creation or installation fails.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("UV_")
        and key not in {"VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"}
    }
    uv = ["uv", "--no-config", "--no-cache"]
    with tempfile.TemporaryDirectory(prefix="verify-install-") as directory:
        excludes = Path(directory) / "excludes.txt"
        excludes.write_text("\n".join(excluded_packages))
        venv = Path(directory) / "venv"
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [*uv, "venv", "--python", sys.executable, str(venv)],
            cwd=directory,
            env=env,
            check=True,
        )
        subprocess.run(
            [
                *uv,
                "pip",
                "install",
                "--excludes",
                str(excludes),
                "--python",
                str(python),
                str(artifact),
            ],
            cwd=directory,
            env=env,
            check=True,
        )


def main() -> int:
    """Verify that both distribution formats install before publishing either.

    Returns:
        Zero if every artifact installs or one if a format is missing or fails.
    """
    dist_dir = Path(os.environ["DIST_DIR"]).resolve()
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if not wheels or not sdists:
        print(f"Error: expected both wheels and sdists in {dist_dir}", file=sys.stderr)
        return 1
    excluded_packages = workspace_siblings(os.environ["PACKAGE"])
    if excluded_packages:
        print(
            f"Excluding workspace siblings: {', '.join(excluded_packages)}", flush=True
        )
    for artifact in [*wheels, *sdists]:
        print(f"Checking installation of {artifact.name}", flush=True)
        try:
            install_artifact(artifact, excluded_packages)
        except subprocess.CalledProcessError:
            print(f"Error: installation failed for {artifact.name}", file=sys.stderr)
            return 1
        print(f"Verified installation of {artifact.name}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
