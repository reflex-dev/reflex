"""Install each release artifact independently before allowing publication.

Run from the publish workflow's post-build hook with DIST_DIR in the environment.
Use fresh virtual environments outside the checkout with no uv cache or
configuration so a working wheel cannot mask a broken sdist. Skip runtime
dependencies because their required versions may not be published yet.
"""

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def install_artifact(artifact: Path) -> None:
    """Install one archive without runtime dependencies in an isolated environment.

    Args:
        artifact: The absolute path to a wheel or source distribution.

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
                "--no-deps",
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
    for artifact in [*wheels, *sdists]:
        print(f"Checking installation of {artifact.name}", flush=True)
        try:
            install_artifact(artifact)
        except subprocess.CalledProcessError:
            print(f"Error: installation failed for {artifact.name}", file=sys.stderr)
            return 1
        print(f"Verified installation of {artifact.name}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
