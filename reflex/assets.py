"""Helper functions for adding assets to the app."""

import inspect
from pathlib import Path
from typing import TYPE_CHECKING, overload

from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import EnvironmentVariables

if TYPE_CHECKING:
    from typing_extensions import Buffer


class AssetPathStr(str):
    """The relative URL to an asset, with a build-time importable variant.

    Returned by :func:`asset`. The string value is the asset URL with the
    configured ``frontend_path`` prepended; :attr:`importable_path` is the
    same asset prefixed with ``$/public`` so the asset can be referenced by
    a component ``library`` or module import at build time.

    The constructor signature mirrors :class:`str`: the input is interpreted
    as the unprefixed asset path and both forms are derived from it at
    construction time.
    """

    __slots__ = ("importable_path",)

    importable_path: str

    @overload
    def __new__(cls, object: object = "") -> "AssetPathStr": ...
    @overload
    def __new__(
        cls,
        object: "Buffer",
        encoding: str = "utf-8",
        errors: str = "strict",
    ) -> "AssetPathStr": ...

    def __new__(
        cls,
        object: object = "",
        encoding: str | None = None,
        errors: str | None = None,
    ) -> "AssetPathStr":
        """Construct from an unprefixed, leading-slash asset path.

        Args/semantics mirror :class:`str`. The resulting string is interpreted
        as the asset path (e.g. ``"/external/mod/file.js"``); the
        frontend-prefixed URL is stored as the ``AssetPathStr`` value and
        ``$/public`` + ``relative_path`` as :attr:`importable_path`.

        Args:
            object: The object to stringify (str, bytes, or any object).
            encoding: Encoding to decode ``object`` with when it is bytes-like.
            errors: Error handler for decoding.

        Returns:
            A new ``AssetPathStr`` instance.
        """
        if encoding is None and errors is None:
            relative_path = str.__new__(str, object)
        else:
            relative_path = str.__new__(
                str,
                object,  # ty:ignore[invalid-argument-type]
                "utf-8" if encoding is None else encoding,
                "strict" if errors is None else errors,
            )
        instance = super().__new__(
            cls, get_config().prepend_frontend_path(relative_path)
        )
        instance.importable_path = f"$/public{relative_path}"
        return instance

    def __getnewargs__(self) -> tuple[str]:
        """Return the unprefixed path for pickle/copy reconstruction.

        Python's default ``str`` pickle path would feed the frontend-prefixed
        value back into :meth:`__new__`, double-applying the prefix and
        losing the :attr:`importable_path` slot. Returning the raw path
        (recovered by stripping the ``$/public`` prefix) lets ``__new__``
        rebuild both forms correctly.

        Returns:
            A one-tuple containing the unprefixed asset path.
        """
        return (self.importable_path[len("$/public") :],)


def remove_stale_external_asset_symlinks():
    """Remove broken symlinks and empty directories in assets/external/.

    When a Python module directory that uses rx.asset(shared=True) is renamed
    or deleted, stale symlinks remain in assets/external/ pointing to the old
    path. This cleanup prevents issues with file watchers detecting symlink
    re-creation during import.
    """
    external_dir = (
        Path.cwd() / constants.Dirs.APP_ASSETS / constants.Dirs.EXTERNAL_APP_ASSETS
    )
    if not external_dir.exists():
        return

    # Remove broken symlinks.
    broken = [
        p
        for p in external_dir.rglob("*")
        if p.is_symlink() and not p.resolve().exists()
    ]
    for path in broken:
        path.unlink()

    # Remove empty directories left behind (deepest first).
    for dirpath in sorted(external_dir.rglob("*"), reverse=True):
        if dirpath.is_dir() and not dirpath.is_symlink() and not any(dirpath.iterdir()):
            dirpath.rmdir()


def asset(
    path: str,
    shared: bool = False,
    subfolder: str | None = None,
    _stack_level: int = 1,
) -> AssetPathStr:
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

    Returns:
        The relative URL to the asset, with an ``importable_path`` property
        for use as a build-time module reference.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If subfolder is provided for local assets.
    """
    assets = constants.Dirs.APP_ASSETS
    backend_only = EnvironmentVariables.REFLEX_BACKEND_ONLY.get()

    # Local asset handling
    if not shared:
        cwd = Path.cwd()
        src_file_local = cwd / assets / path
        if subfolder is not None:
            msg = "Subfolder is not supported for local assets."
            raise ValueError(msg)
        if not backend_only and not src_file_local.exists():
            msg = f"File not found: {src_file_local}"
            raise FileNotFoundError(msg)
        return AssetPathStr(f"/{path}")

    # Shared asset handling
    # Determine the file by which the asset is exposed.
    frame = inspect.stack()[_stack_level]
    calling_file = frame.filename
    module = inspect.getmodule(frame[0])
    assert module is not None

    external = constants.Dirs.EXTERNAL_APP_ASSETS
    src_file_shared = Path(calling_file).parent / path
    if not src_file_shared.exists():
        msg = f"File not found: {src_file_shared}"
        raise FileNotFoundError(msg)

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
            try:
                dst_file.symlink_to(src_file_shared)
            except FileExistsError:
                # This happens when Simon builds the app on a bind mount in a docker container.
                dst_file.unlink()
                dst_file.symlink_to(src_file_shared)

    return AssetPathStr(f"/{external}/{subfolder}/{path}")
