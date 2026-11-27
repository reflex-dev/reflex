"""Build hook that embeds the javascript package in reflex-components-ui."""

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Where the javascript lands inside the reflex_components_ui package.
JS_SRC = "reflex_components_ui/js/src"


class JavascriptBuildHook(BuildHookInterface):
    """Embed ``js/src`` in the wheel.

    The javascript package lives beside the python source rather than inside
    it. An sdist carries ``js/src`` where the repository has it, so a wheel
    built from the sdist finds it the same way a wheel built from a checkout
    does.
    """

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Add the javascript source to a wheel.

        Args:
            version: The kind of build: ``standard`` or ``editable``.
            build_data: Additional build data.

        Raises:
            FileNotFoundError: If there is no javascript to embed.
        """
        # An sdist includes js/src as it is. An editable install resolves
        # reflex_components_ui to the checkout, which reads js/src in place.
        if self.target_name != "wheel" or version == "editable":
            return
        js_src = Path(self.root) / "js" / "src"
        if not js_src.is_dir():
            msg = f"No javascript to embed: {js_src} does not exist."
            raise FileNotFoundError(msg)
        build_data["force_include"][str(js_src)] = JS_SRC
