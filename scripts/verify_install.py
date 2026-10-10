"""Install each release artifact independently before allowing publication.

Run from the publish workflow's post-build hook with PACKAGE and DIST_DIR in the
environment.
Use fresh virtual environments outside the checkout with no uv cache or
configuration so a working wheel cannot mask a broken sdist. Resolve runtime
dependencies except workspace siblings whose versions may not be published yet.
Build required siblings locally into a temporary wheelhouse for isolated builds.
"""

# /// script
# requires-python = ">=3.11"
# ///

import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any


def clean_environment() -> dict[str, str]:
    """Remove inherited settings that could bypass artifact verification.

    Returns:
        Environment variables without uv overrides or active Python environments.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("UV_")
        and key not in {"VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"}
    }


def package_requirements(project: dict[str, Any]) -> list[str]:
    """Collect runtime and build requirements that can reference workspace siblings.

    Args:
        project: A package's parsed pyproject.toml.

    Returns:
        Requirements from package metadata, build backends and Hatch hooks.
    """
    requirements = [
        *project.get("project", {}).get("dependencies", []),
        *project.get("build-system", {}).get("requires", []),
    ]
    build = project.get("tool", {}).get("hatch", {}).get("build", {})
    for scope in [build, *build.get("targets", {}).values()]:
        for hook in scope.get("hooks", {}).values():
            requirements.extend(hook.get("dependencies", []))
    return requirements


def build_workspace_wheelhouse(package: str, wheelhouse: Path) -> None:
    """Build required workspace siblings for isolated source builds.

    Args:
        package: The package being verified, never included in the wheelhouse.
        wheelhouse: Temporary directory shared by the artifact checks.

    Raises:
        subprocess.CalledProcessError: If a sibling wheel cannot be built.
    """
    root = Path(__file__).resolve().parent.parent
    with (root / "pyproject.toml").open("rb") as f:
        config = tomllib.load(f)
    siblings = workspace_siblings(package)
    projects = {}
    for path in [root / "pyproject.toml", *root.glob("packages/*/pyproject.toml")]:
        with path.open("rb") as f:
            project = tomllib.load(f)
        name = project["project"]["name"]
        if name == package or name in siblings:
            projects[name] = project
    order = []
    seen = {package}

    def visit(name: str) -> None:
        """Append a sibling after its own dependencies.

        Args:
            name: The package whose dependency graph to traverse.
        """
        for requirement in package_requirements(projects[name]):
            dependency = re.split(r"[;\s\[<>=!~@]", requirement, maxsplit=1)[0]
            dependency = re.sub(r"[-_.]+", "-", dependency).lower()
            if dependency in projects and dependency not in seen:
                seen.add(dependency)
                visit(dependency)
                order.append(dependency)

    visit(package)
    lockstep = config.get("tool", {}).get("reflex-release", {}).get("lockstep", [])
    for name in order:
        env = clean_environment()
        if "VERSION" in env and any(
            group.get("pin-exact")
            and package in group["members"]
            and name in group["members"]
            for group in lockstep
        ):
            env["UV_DYNAMIC_VERSIONING_BYPASS"] = env["VERSION"]
        subprocess.run(
            [
                "uv",
                "build",
                "--package",
                name,
                "--wheel",
                "--out-dir",
                str(wheelhouse),
                "--find-links",
                str(wheelhouse),
            ],
            cwd=root,
            env=env,
            check=True,
        )


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


def install_artifact(
    artifact: Path,
    excluded_packages: tuple[str, ...] = (),
    wheelhouse: Path | None = None,
) -> None:
    """Install one archive and its external dependencies in isolation.

    Args:
        artifact: The absolute path to a wheel or source distribution.
        excluded_packages: Workspace siblings exempt from dependency resolution.
        wheelhouse: Locally built siblings available to isolated build environments.

    Raises:
        subprocess.CalledProcessError: If environment creation or installation fails.
    """
    env = clean_environment()
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
                *(["--find-links", str(wheelhouse)] if wheelhouse is not None else []),
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
    with tempfile.TemporaryDirectory(prefix="verify-build-") as directory:
        try:
            build_workspace_wheelhouse(os.environ["PACKAGE"], Path(directory))
        except subprocess.CalledProcessError:
            print("Error: workspace build dependencies failed", file=sys.stderr)
            return 1
        for artifact in [*wheels, *sdists]:
            print(f"Checking installation of {artifact.name}", flush=True)
            try:
                install_artifact(artifact, excluded_packages, Path(directory))
            except subprocess.CalledProcessError:
                print(
                    f"Error: installation failed for {artifact.name}", file=sys.stderr
                )
                return 1
            print(f"Verified installation of {artifact.name}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
