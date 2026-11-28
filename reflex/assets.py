"""Helper functions for adding assets to the app."""

import hashlib
import logging
import sys
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, overload

from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import EnvironmentVariables

logger = logging.getLogger(__name__)

_HASH_CHUNK_SIZE = 1024 * 1024
_MAX_HASH_ATTEMPTS = 3
# The coarsest file timestamp granularity in common use (FAT's 2 s): a file
# written again within it can keep the stat it had after the previous write.
_RECENT_CHANGE_WINDOW_NS = 2_000_000_000
_MAX_LINK_ATTEMPTS = 3
_LINK_RETRY_DELAY = 0.01

if TYPE_CHECKING:
    from typing_extensions import Buffer


class _FileSignature(NamedTuple):
    """The stat fields that change whenever a file's content changes."""

    device: int
    inode: int
    size: int
    mtime_ns: int
    ctime_ns: int


_content_hash_cache: dict[Path, tuple[_FileSignature, str]] = {}


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

    __slots__ = ("_raw_path", "importable_path")

    _raw_path: str
    importable_path: str

    @overload
    def __new__(cls, object: object = "") -> "AssetPathStr": ...
    @overload
    def __new__(
        cls,
        object: object = "",
        *,
        importable_path: str | None = None,
    ) -> "AssetPathStr": ...
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
        *,
        importable_path: str | None = None,
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
            importable_path: Optional unversioned path to use for build-time imports.

        Returns:
            A new ``AssetPathStr`` instance.
        """
        if encoding is None and errors is None:
            relative_path = str.__new__(str, object)
        else:
            relative_path = str.__new__(
                str,
                object,  # pyright: ignore[reportArgumentType]
                "utf-8" if encoding is None else encoding,
                "strict" if errors is None else errors,
            )
        instance = super().__new__(
            cls, get_config().prepend_frontend_path(relative_path)
        )
        instance._raw_path = relative_path
        instance.importable_path = f"$/public{importable_path or relative_path}"
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
        return (self._raw_path,)

    def __getnewargs_ex__(self) -> tuple[tuple[str], dict[str, str]]:
        """Return constructor args and kwargs for pickle/copy reconstruction.

        Returns:
            Constructor args and kwargs preserving the unversioned import path.
        """
        return (
            (self._raw_path,),
            {"importable_path": self.importable_path[len("$/public") :]},
        )


def _short_content_hash(path: Path) -> str:
    """Get a short content hash for an asset file.

    Args:
        path: The file to hash.

    Returns:
        The first 8 hex characters of the file's SHA-256 hash.
    """
    for _ in range(_MAX_HASH_ATTEMPTS):
        digest = _content_digest(path)
        if digest == _content_digest(path):
            break
    else:
        logger.warning(
            f"{path} was modified {_MAX_HASH_ATTEMPTS} times while calculating hash."
        )
        return str(time.time())
    return digest[:8]


def _content_digest(path: Path) -> str:
    """Get the SHA-256 digest for the current file content.

    Args:
        path: The file to hash.

    Returns:
        The full SHA-256 digest for the file content.
    """
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _file_signature(path: Path) -> _FileSignature:
    """Get the stat signature of a file.

    Args:
        path: The file to inspect.

    Returns:
        The file's current signature.
    """
    stat = path.stat()
    return _FileSignature(
        stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
    )


def _cached_short_content_hash(path: Path) -> str:
    """Get a short content hash for an asset file, reading it only when it changed.

    The hash is cached under the file's stat signature. A file changed within
    ``_RECENT_CHANGE_WINDOW_NS`` is hashed but not cached, because another
    write in the same timestamp tick would leave the signature unchanged.

    Args:
        path: The file to hash.

    Returns:
        The first 8 hex characters of the file's SHA-256 hash.
    """
    signature = _file_signature(path)
    cached = _content_hash_cache.get(path)
    if cached is not None and cached[0] == signature:
        return cached[1]
    hashed_at = time.time_ns()
    short_hash = _short_content_hash(path)
    # On Windows st_ctime is the creation time, so the newer of both counts.
    last_change = max(signature.mtime_ns, signature.ctime_ns)
    if (
        last_change < hashed_at - _RECENT_CHANGE_WINDOW_NS
        and _file_signature(path) == signature
    ):
        _content_hash_cache[path] = (signature, short_hash)
    return short_hash


def _versioned_asset_path(relative_path: str, source_file: Path) -> AssetPathStr:
    """Create an asset URL with a content-hash query parameter.

    Args:
        relative_path: The unprefixed public asset path.
        source_file: The source file used to calculate the content hash.

    Returns:
        A versioned asset URL that preserves an unversioned import path.
    """
    versioned_path = f"{relative_path}?v={_cached_short_content_hash(source_file)}"
    return AssetPathStr(versioned_path, importable_path=relative_path)


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


def _links_to(dst_file: Path, src_file: Path) -> bool:
    """Check whether dst_file is already a symlink to src_file.

    Args:
        dst_file: The path to inspect.
        src_file: The asset the symlink should point at.

    Returns:
        Whether dst_file is a symlink resolving to src_file.
    """
    try:
        if not dst_file.is_symlink():
            return False
        resolved = dst_file.resolve()
    except (OSError, RuntimeError):
        # An unresolvable destination, such as the symlink loop a crashed or
        # racing writer can leave behind, which Python below 3.13 reports as
        # RuntimeError. It is not the link we want either way, so replace it.
        return False
    # The source is the caller's to validate, so its errors are not caught
    # here: replacing the destination on a bad source would destroy a good
    # link on the way to failing anyway.
    return resolved == src_file.resolve()


def _link_shared_asset(dst_file: Path, src_file: Path) -> None:
    """Point dst_file at src_file with a symlink, regardless of what is there.

    Several processes routinely compile into the same assets/external/
    directory at once: pytest-xdist workers, parallel builds, or containers
    sharing a bind mount. Linking in place would be check-then-act, so the link
    is built under a unique temporary name in the destination directory and
    renamed over dst_file instead, which is one atomic replace on POSIX and
    leaves no window to interleave with. Whichever process wins the race,
    dst_file is a symlink to src_file once this returns.

    Windows is the exception: replacing a destination that another process is
    itself replacing is denied rather than serialised, so the rename is retried
    there, conceding as soon as the other process turns out to have linked the
    same asset.

    Args:
        dst_file: The symlink to create in the app's external assets directory.
        src_file: The asset file the symlink should point at.

    Raises:
        PermissionError: If the destination could not be replaced.
    """
    if _links_to(dst_file, src_file):
        # Already correct: leave it alone so file watchers see no change.
        return

    # The staged name deliberately does not derive from the asset name: that
    # would have to be truncated to fit the filesystem's limit on a path
    # component, and cutting a name to a byte budget without splitting a
    # character is more machinery than a transient name is worth.
    tmp_file = dst_file.with_name(f".{uuid.uuid4().hex}.tmp")
    try:
        tmp_file.symlink_to(src_file)
        for attempt in range(_MAX_LINK_ATTEMPTS):
            try:
                tmp_file.replace(dst_file)
            except PermissionError:  # bounded, and dwarfed by the syscall
                if _links_to(dst_file, src_file):
                    # The process that denied us wanted the same link.
                    return
                if attempt == _MAX_LINK_ATTEMPTS - 1:
                    raise
                time.sleep(_LINK_RETRY_DELAY * (attempt + 1))
            else:
                return
    finally:
        # A no-op once the rename succeeded, and the cleanup if it did not.
        tmp_file.unlink(missing_ok=True)


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
        relative_path = f"/{path}"
        if backend_only and not src_file_local.exists():
            return AssetPathStr(relative_path)
        return _versioned_asset_path(relative_path, src_file_local)

    # Shared asset handling
    # Determine the file by which the asset is exposed. inspect.stack() would
    # read the source context of every frame on the stack, on every call.
    frame = sys._getframe(_stack_level)
    calling_file = frame.f_code.co_filename
    module_name: str | None = frame.f_globals.get("__name__")
    assert module_name is not None

    external = constants.Dirs.EXTERNAL_APP_ASSETS
    src_file_shared = Path(calling_file).parent / path
    if not src_file_shared.exists():
        msg = f"File not found: {src_file_shared}"
        raise FileNotFoundError(msg)

    caller_module_path = module_name.replace(".", "/")
    subfolder = f"{caller_module_path}/{subfolder}" if subfolder else caller_module_path

    # Symlink the asset to the app's external assets directory if running frontend.
    if not backend_only:
        # Create the asset folder in the currently compiling app.
        dst_file = Path.cwd() / assets / external / subfolder / path
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        _link_shared_asset(dst_file, src_file_shared)

    return _versioned_asset_path(
        f"/{external}/{subfolder}/{path}",
        src_file_shared,
    )
