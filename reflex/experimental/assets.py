"""Helper functions for adding assets to the app."""

from typing import Optional

from reflex import assets
from reflex.utils import console


def asset(relative_filename: str, subfolder: Optional[str] = None) -> str:
    """DEPRECATED: use `rx.asset` with `shared=True` instead.

    Add an asset to the app.
    Place the file next to your including python file.
    Copies the file to the app's external assets directory.

    Example:
    ```python
    rx.script(src=rx._x.asset("my_custom_javascript.js"))
    rx.image(src=rx._x.asset("test_image.png","subfolder"))
    ```

    Args:
        relative_filename: The relative filename of the asset.
        subfolder: The directory to place the asset in.

    Returns:
        The relative URL to the copied asset.
    """
    console.deprecate(
        feature_name="rx._x.asset",
        reason="Use `rx.asset` with `shared=True` instead of `rx._x.asset`.",
        deprecation_version="0.6.6",
        removal_version="0.7.0",
    )
    return assets.asset(
        relative_filename, shared=True, subfolder=subfolder, _stack_level=2
    )
