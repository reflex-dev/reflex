"""Helper functions for adding assets to the app."""

import inspect
from pathlib import Path
from typing import Optional

from reflex import constants


def asset(relative_filename: str, subfolder: Optional[str] = None) -> str:
    """Add an asset to the app.
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

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the module is None.

    Returns:
        The relative URL to the copied asset.
    """
    # Determine the file by which the asset is exposed.
    calling_file = inspect.stack()[1].filename
    module = inspect.getmodule(inspect.stack()[1][0])
    if module is None:
        raise ValueError("Module is None")
    caller_module_path = module.__name__.replace(".", "/")

    subfolder = f"{caller_module_path}/{subfolder}" if subfolder else caller_module_path

    src_file = Path(calling_file).parent / relative_filename

    assets = constants.Dirs.APP_ASSETS
    external = constants.Dirs.EXTERNAL_APP_ASSETS

    if not src_file.exists():
        raise FileNotFoundError(f"File not found: {src_file}")

    # Create the asset folder in the currently compiling app.
    asset_folder = Path.cwd() / assets / external / subfolder
    asset_folder.mkdir(parents=True, exist_ok=True)

    dst_file = asset_folder / relative_filename

    if not dst_file.exists():
        dst_file.symlink_to(src_file)

    asset_url = f"/{external}/{subfolder}/{relative_filename}"
    return asset_url
