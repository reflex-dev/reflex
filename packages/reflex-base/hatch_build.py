"""Build hook that embeds the frontend package in reflex-base."""

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Where the frontend lands inside the reflex_base package.
WEB_TEMPLATE = "reflex_base/.templates/web"


class FrontendBuildHook(BuildHookInterface):
    """Embed the frontend javascript package as the web template.

    The frontend is a package of its own, beside this one in the repository.
    An sdist carries its ``src`` inside ``reflex_base``, so a wheel built from
    the sdist finds it there like any other package file.
    """

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Add the frontend package's source to the distribution.

        Args:
            version: The kind of build: ``standard`` or ``editable``.
            build_data: Additional build data.

        Raises:
            FileNotFoundError: If there is no frontend to embed.
        """
        # An editable install resolves reflex_base to the checkout, which reads
        # the frontend package in place.
        if version == "editable":
            return
        root = Path(self.root)
        frontend = root.parent / "reflex-frontend" / "src"
        if frontend.is_dir():
            prefix = "src/" if self.target_name == "sdist" else ""
            build_data["force_include"][str(frontend)] = prefix + WEB_TEMPLATE
        elif not (root / "src" / WEB_TEMPLATE).is_dir():
            msg = (
                f"No frontend to embed: neither {frontend} nor an sdist's copy exists."
            )
            raise FileNotFoundError(msg)
