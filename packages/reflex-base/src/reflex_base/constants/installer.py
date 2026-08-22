"""File for constants related to the installation process. (Bun/Node)."""

from __future__ import annotations

from types import SimpleNamespace

from .base import IS_WINDOWS
from .utils import classproperty


# Bun config.
class Bun(SimpleNamespace):
    """Bun constants."""

    # The Bun version.
    VERSION = "1.3.14"

    # Min Bun Version
    MIN_VERSION = "1.3.0"

    # URL to bun install script.
    INSTALL_URL = "https://raw.githubusercontent.com/reflex-dev/reflex/main/scripts/bun_install.sh"

    # URL to windows install script.
    WINDOWS_INSTALL_URL = (
        "https://raw.githubusercontent.com/reflex-dev/reflex/main/scripts/install.ps1"
    )

    # Path of the bunfig file
    CONFIG_PATH = "bunfig.toml"

    # Path of the bun lockfile.
    LOCKFILE_PATH = "bun.lock"

    # Directory in the app root where the canonical bun lockfile is stored.
    # A dedicated directory avoids clashes with a user's own bun project
    # that may sit in the same directory as the Reflex project.
    ROOT_LOCKFILE_DIR = "reflex.lock"

    @classproperty
    @classmethod
    def ROOT_PATH(cls):
        """The directory to store the bun.

        Returns:
            The directory to store the bun.
        """
        from reflex_base.environment import environment

        return environment.REFLEX_DIR.get() / "bun"

    @classproperty
    @classmethod
    def DEFAULT_PATH(cls):
        """Default bun path.

        Returns:
            The default bun path.
        """
        return cls.ROOT_PATH / "bin" / ("bun" if not IS_WINDOWS else "bun.exe")

    DEFAULT_CONFIG = """
[install]
registry = "{registry}"
"""


# Node / NPM config
class Node(SimpleNamespace):
    """Node/ NPM constants."""

    # The minimum required node version.
    MIN_VERSION = "22.22.0"

    # Path of the node config file.
    CONFIG_PATH = ".npmrc"

    # Path of the npm lockfile.
    LOCKFILE_PATH = "package-lock.json"

    DEFAULT_CONFIG = """
registry={registry}
fetch-retries=0
"""


class PackageJson(SimpleNamespace):
    """Constants used to build the package.json file.

    Frontend dependency versions are not declared here: they live in the
    bundled ``@reflex-dev/reflex-base`` npm package's manifest (see
    :mod:`reflex_base.utils.frontend_package`), and users control versions
    via ``overrides`` in their ``reflex.lock/package.json``.
    """

    class Commands(SimpleNamespace):
        """The commands to define in package.json."""

        DEV = "react-router dev --host"
        EXPORT = "react-router build"

    PATH = "package.json"

    # Force specific transitive npm deps to a single resolved version when
    # needed. Prefer a pin in the frontend package's manifest when the package
    # is one it depends on directly: a manifest pin already satisfies and
    # dedupes every transitive requirer, and unlike an override it is not
    # persisted into a project's `reflex.lock/package.json` (where a later
    # removal here cannot clean it up again). Reserve overrides for packages
    # the manifest does not declare. Package managers ignore `overrides`
    # declared by a dependency's own manifest, so root-level merging stays a
    # Python responsibility.
    OVERRIDES: dict[str, str] = {}
