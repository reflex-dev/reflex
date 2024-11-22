"""Helper functions for adding assets to the app."""

import inspect
from pathlib import Path
from typing import Optional

from reflex import constants
from reflex.utils.exec import is_backend_only


def asset(
    path: str,
    shared: bool = False,
    subfolder: Optional[str] = None,
    _stack_level: int = 1,
) -> str:
    """Add an asset to the app, either shared as a symlink or local.

    Shared/External/Library assets:
        Place the file next to your including python file.
        Links the file to the app's external assets directory.

    Example:
    ```python
    # my_custom_javascript.js is a shared asset located next to the including python file.
    rx.script(src=rx.asset(path="my_custom_javascript.js", shared=True))
    rx.image(src=rx.asset(path="test_image.png", shared=True, subfolder="subfolder"))
    ```

    Local/Internal assets:
        Place the file in the app's assets/ directory.

    Example:
    ```python
    # local_image.png is an asset located in the app's assets/ directory. It cannot be shared when developing a library.
    rx.image(src=rx.asset(path="local_image.png"))
    ```

    Args:
        path: The relative path of the asset.
        subfolder: The directory to place the shared asset in.
        shared: Whether to expose the asset to other apps.
        _stack_level: The stack level to determine the calling file, defaults to
            the immediate caller 1. When using rx.asset via a helper function,
            increase this number for each helper function in the stack.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If subfolder is provided for local assets.

    Returns:
        The relative URL to the asset.
    """
    assets = constants.Dirs.APP_ASSETS
    backend_only = is_backend_only()

    # Local asset handling
    if not shared:
        cwd = Path.cwd()
        src_file_local = cwd / assets / path
        if subfolder is not None:
            raise ValueError("Subfolder is not supported for local assets.")
        if not backend_only and not src_file_local.exists():
            raise FileNotFoundError(f"File not found: {src_file_local}")
        return f"/{path}"

    # Shared asset handling
    # Determine the file by which the asset is exposed.
    frame = inspect.stack()[_stack_level]
    calling_file = frame.filename
    module = inspect.getmodule(frame[0])
    assert module is not None

    external = constants.Dirs.EXTERNAL_APP_ASSETS
    src_file_shared = Path(calling_file).parent / path
    if not src_file_shared.exists():
        raise FileNotFoundError(f"File not found: {src_file_shared}")

    caller_module_path = module.__name__.replace(".", "/")
    subfolder = f"{caller_module_path}/{subfolder}" if subfolder else caller_module_path

    # Symlink the asset to the app's external assets directory if running frontend.
    if not backend_only:
        # Create the asset folder in the currently compiling app.
        asset_folder = Path.cwd() / assets / external / subfolder
        asset_folder.mkdir(parents=True, exist_ok=True)

        dst_file = asset_folder / path

        if not dst_file.exists() and (
            not dst_file.is_symlink() or dst_file.resolve() != src_file_shared.resolve()
        ):
            dst_file.symlink_to(src_file_shared)

    return f"/{external}/{subfolder}/{path}"
