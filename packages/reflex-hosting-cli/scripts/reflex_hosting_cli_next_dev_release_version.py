"""Script to check the versions of reflex-hosting-cli on PyPI and return the next pre-release version."""

import json
import sys

from packaging import version

MODULE_NAME = "reflex-hosting-cli"


def get_latest_package_version_info(
    package_name: str, index_url: str, dev: bool = True
) -> version.Version:
    """Check if the latest version of the package on the index.

    Args:
        package_name: The name of the package.
        index_url: The index URL to check, e.g. https://pypi.org or https://test.pypi.org
        dev: Whether to include dev releases only

    Raises:
        httpx.HTTPError: If the request fails.

    Returns:
        The latest version of the package published on the specified index

    """
    import httpx

    try:
        # Get the latest version from specified index
        url = f"{index_url}/pypi/{package_name}/json"
        response = httpx.get(url)
        response.raise_for_status()
        response_json = response.json()
        if not dev:
            # Stable release
            return version.parse(response_json["info"]["version"])
        # All the releases including pre-releases
        releases = response_json["releases"]
        parsed_versions = [version.parse(v) for v in releases]
        dev_releases = [v for v in parsed_versions if v.dev is not None]
        return max(dev_releases)
    except httpx.HTTPError as he:
        sys.stderr.write(f"Failed to fetch package info from PyPI: {he}")
        raise
    except (
        json.JSONDecodeError,
        KeyError,
        AttributeError,
        ValueError,
        version.InvalidVersion,
    ) as ex:
        sys.stderr.write(f"Unexpected response format from PyPI: {ex}")
        raise


def get_next_dev_release_version(
    latest_stable_version: version.Version, latest_dev_version: version.Version
) -> str:
    """Get the next dev release version.

    Args:
        latest_stable_version: The latest stable version of the package on PyPI.
        latest_dev_version: The latest dev version of the package on Test PyPI.

    Raises:
        ValueError: if the dev version is ill-formed.

    Returns:
        The next dev release version in string.

    """
    if latest_stable_version > latest_dev_version:
        # we bump the micro version
        return f"{latest_stable_version.major}.{latest_stable_version.minor}.{latest_stable_version.micro + 1}dev0"
    dev = latest_dev_version.dev
    if dev is None:
        raise ValueError(
            f"The latest dev version not in expected format: got {latest_dev_version}"
        )
    # we bump the dev build version
    return f"{latest_dev_version.major}.{latest_dev_version.minor}.{latest_dev_version.micro}dev{dev + 1}"


def main():
    """Return the latest version of reflex-hosting-cli on PyPI or Test PyPI."""
    latest_stable_version = get_latest_package_version_info(
        MODULE_NAME, "https://pypi.org", dev=False
    )
    latest_dev_version = get_latest_package_version_info(
        MODULE_NAME, "https://test.pypi.org", dev=True
    )
    next_dev_version = get_next_dev_release_version(
        latest_stable_version, latest_dev_version
    )
    sys.stdout.write(str(next_dev_version))


if __name__ == "__main__":
    main()
