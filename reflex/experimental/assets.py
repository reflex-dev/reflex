"""Helper functions for adding assets to the app."""

import inspect
import os
from pathlib import Path
from typing import Optional

from reflex import constants


def asset(
    path: str,
    subfolder: Optional[str] = None,
    shared: Optional[bool] = None,
) -> str:
    """Add an asset to the app, either shared as a symlink or local.

    Shared/External/Library assets:
    Place the file next to your including python file.
    Links the file to the app's external assets directory.

    Local/Internal assets:
    Place the file in the app's assets/ directory.

    Example:
    ```python
    rx.script(src=rx._x.asset("my_custom_javascript.js"))
    rx.image(src=rx._x.asset("test_image.png","subfolder"))
    ```

    Args:
        path: The relative path of the asset.
        subfolder: The directory to place the asset in.
        shared: Whether to expose the asset to other apps. None means auto-detect.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If shared is not explicitly set and both shared and local assets exist.

    Returns:
        The relative URL to the asset.
    """
    # Determine the file by which the asset is exposed.
    calling_file = inspect.stack()[1].filename
    module = inspect.getmodule(inspect.stack()[1][0])
    assert module is not None

    cwd = Path.cwd()
    assets = constants.Dirs.APP_ASSETS
    external = constants.Dirs.EXTERNAL_APP_ASSETS

    src_file_shared = Path(calling_file).parent / path
    src_file_local = cwd / assets / path

    shared_exists = src_file_shared.exists()
    local_exists = src_file_local.exists()

    # Determine whether the asset is shared or local.
    if shared is None:
        if shared_exists and local_exists:
            raise ValueError(
                f"Both shared and local assets exist for {path}. "
                + "Please explicitly set shared=True or shared=False."
            )
        if not shared_exists and not local_exists:
            raise FileNotFoundError(
                f"Could not find file, neither at shared location {src_file_shared} nor at local location {src_file_local}"
            )
        shared = shared_exists

    # Local asset handling
    if not shared:
        if subfolder is not None:
            raise ValueError("Subfolder is not supported for local assets.")
        if not local_exists:
            raise FileNotFoundError(f"File not found: {src_file_local}")
        return f"/{path}"

    # Shared asset handling
    if not shared_exists:
        raise FileNotFoundError(f"File not found: {src_file_shared}")

    caller_module_path = module.__name__.replace(".", "/")
    subfolder = f"{caller_module_path}/{subfolder}" if subfolder else caller_module_path

    # Symlink the asset to the app's external assets directory if running frontend.
    if not os.environ.get(constants.ENV_BACKEND_ONLY):
        # Create the asset folder in the currently compiling app.
        asset_folder = Path.cwd() / assets / external / subfolder
        asset_folder.mkdir(parents=True, exist_ok=True)

        dst_file = asset_folder / path

        if not dst_file.exists() and (
            not dst_file.is_symlink() or dst_file.resolve() != src_file_shared.resolve()
        ):
            dst_file.symlink_to(src_file_shared)

    asset_url = f"/{external}/{subfolder}/{path}"
    return asset_url
