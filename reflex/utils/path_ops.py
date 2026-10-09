"""Path operations."""

from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import stat
import sys
import unicodedata
from collections.abc import Iterator
from pathlib import Path

from reflex_base.config import get_config
from reflex_base.environment import environment

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

logger = logging.getLogger(__name__)
_JSON_LOCKS_DIR = "locks/json"

# Shorthand for join.
join = os.linesep.join


def write_file(path: str | Path, code: str):
    """Write the given code to the given path, skipping unchanged contents.

    Args:
        path: The path to write the code to.
        code: The code to write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == code:
        return
    path.write_text(code, encoding="utf-8")


def chmod_rm(path: Path):
    """Remove a file or directory with chmod.

    Args:
        path: The path to the file or directory.
    """
    path.chmod(stat.S_IWRITE)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()


def rm(path: str | Path):
    """Remove a file or directory.

    Args:
        path: The path to the file or directory.
    """
    path = Path(path)
    if path.is_dir():
        # In Python 3.12, onerror is deprecated in favor of onexc
        shutil.rmtree(path, onerror=lambda _func, _path, _info: chmod_rm(path))
    elif path.is_file():
        path.unlink()


def copy_tree(
    src: str | Path,
    dest: str | Path,
    ignore: tuple[str, ...] | None = None,
):
    """Copy a directory tree.

    Args:
        src: The path to the source directory.
        dest: The path to the destination directory.
        ignore: Ignoring files and directories that match one of the glob-style patterns provided
    """
    src = Path(src)
    dest = Path(dest)
    if dest.exists():
        for item in dest.iterdir():
            rm(item)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns(*ignore) if ignore is not None else ignore,
        dirs_exist_ok=True,
    )


def cp(
    src: str | Path,
    dest: str | Path,
    overwrite: bool = True,
    ignore: tuple[str, ...] | None = None,
) -> bool:
    """Copy a file or directory.

    Args:
        src: The path to the file or directory.
        dest: The path to the destination.
        overwrite: Whether to overwrite the destination.
        ignore: Ignoring files and directories that match one of the glob-style patterns provided

    Returns:
        Whether the copy was successful.
    """
    src, dest = Path(src), Path(dest)
    if src == dest:
        return False
    if not overwrite and dest.exists():
        return False
    if src.is_dir():
        copy_tree(src, dest, ignore)
    else:
        shutil.copyfile(src, dest)
    return True


def mv(src: str | Path, dest: str | Path, overwrite: bool = True) -> bool:
    """Move a file or directory.

    Args:
        src: The path to the file or directory.
        dest: The path to the destination.
        overwrite: Whether to overwrite the destination.

    Returns:
        Whether the move was successful.
    """
    src, dest = Path(src), Path(dest)
    if src == dest:
        return False
    if not overwrite and dest.exists():
        return False
    rm(dest)
    shutil.move(src, dest)
    return True


def mkdir(path: str | Path):
    """Create a directory.

    Args:
        path: The path to the directory.
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def ls(path: str | Path) -> list[Path]:
    """List the contents of a directory.

    Args:
        path: The path to the directory.

    Returns:
        A list of paths to the contents of the directory.
    """
    return list(Path(path).iterdir())


def ln(src: str | Path, dest: str | Path, overwrite: bool = False) -> bool:
    """Create a symbolic link.

    Args:
        src: The path to the file or directory.
        dest: The path to the destination.
        overwrite: Whether to overwrite the destination.

    Returns:
        Whether the link was successful.
    """
    src, dest = Path(src), Path(dest)
    if src == dest:
        return False
    if not overwrite and (dest.exists() or dest.is_symlink()):
        return False
    if src.is_dir():
        rm(dest)
        src.symlink_to(dest, target_is_directory=True)
    else:
        src.symlink_to(dest)
    return True


def which(program: str | Path) -> Path | None:
    """Find the path to an executable.

    Args:
        program: The name of the executable.

    Returns:
        The path to the executable.
    """
    which_result = shutil.which(program)
    return Path(which_result) if which_result else None


def use_system_bun() -> bool:
    """Check if the system bun should be used.

    Returns:
        Whether the system bun should be used.
    """
    return environment.REFLEX_USE_SYSTEM_BUN.get()


def get_node_bin_path() -> Path | None:
    """Get the node binary dir path.

    Returns:
        The path to the node bin folder.
    """
    return bin_path.parent.absolute() if (bin_path := get_node_path()) else None


def get_node_path() -> Path | None:
    """Get the node binary path.

    Returns:
        The path to the node binary file.
    """
    return which("node")


def get_npm_path() -> Path | None:
    """Get npm binary path.

    Returns:
        The path to the npm binary file.
    """
    return npm_path.absolute() if (npm_path := which("npm")) else None


def get_bun_path() -> Path | None:
    """Get bun binary path.

    Returns:
        The path to the bun binary file.
    """
    bun_path = get_config().bun_path
    if use_system_bun() or not bun_path.exists():
        bun_path = which("bun")
    return bun_path.absolute() if bun_path else None


def _json_file_lock_path(file_path: Path) -> Path:
    """Get the stable lock path for a JSON file.

    Args:
        file_path: The normalized path of the JSON file.

    Returns:
        A path in Reflex's per-user data directory keyed by the target path.
    """
    normalized_path = os.path.normcase(os.fspath(file_path))
    if sys.platform == "darwin":
        # posixpath.normcase is a no-op on macOS, even when the underlying APFS
        # volume is case-insensitive and Unicode-normalizing.
        normalized_path = unicodedata.normalize("NFC", normalized_path).casefold()
    target_digest = hashlib.sha256(os.fsencode(normalized_path)).hexdigest()
    lock_directory = environment.REFLEX_DIR.get().expanduser() / _JSON_LOCKS_DIR
    return lock_directory / f"{target_digest}.lock"


@contextlib.contextmanager
def json_file_lock(file_path: str | Path) -> Iterator[Path]:
    """Lock a JSON file across processes, or proceed unlocked if unavailable.

    The lock lives outside the target directory so frontend cleanup can use it
    while replacing that directory. This context manager is not reentrant.

    Args:
        file_path: The path of the JSON file.

    Yields:
        The resolved target path. Callers must still write atomically because
        read-only lock directories and unsupported locks use an unlocked fallback.
    """
    file_path = Path(file_path).resolve()
    lock_fd = None
    try:
        try:
            lock_path = _json_file_lock_path(file_path)
            lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            if sys.platform == "win32":
                while True:
                    try:
                        msvcrt.locking(lock_fd, msvcrt.LK_LOCK, 1)
                        break
                    except OSError as error:
                        # LK_LOCK already waits between attempts, but gives up
                        # after ten attempts while another writer may own it.
                        if error.errno != errno.EDEADLK:
                            raise
            else:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
        except OSError as error:
            logger.debug(f"Cannot lock {file_path}; proceeding unlocked: {error}")
        yield file_path
    finally:
        if lock_fd is not None:
            # Closing releases the OS lock, including when the body raises.
            # Keep the lock file so waiting writers always use the same inode.
            os.close(lock_fd)


def _write_json_file(file_path: Path, value: dict[str, object]) -> None:
    """Atomically replace a JSON file with a complete document.

    Args:
        file_path: The destination JSON file.
        value: The complete JSON object to write.
    """
    open_flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    temp_path = file_path.with_name(f".{file_path.name}.{secrets.token_hex(8)}.tmp")
    # Preserve the old Path.touch behavior by letting umask set new-file mode.
    temp_fd = os.open(temp_path, open_flags, 0o666)

    try:
        if file_path.exists():
            shutil.copymode(file_path, temp_path)
        temp_file = os.fdopen(temp_fd, "w", encoding="utf-8")
        temp_fd = -1
        with temp_file:
            json.dump(value, temp_file, ensure_ascii=False)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        temp_path.replace(file_path)
    except BaseException:
        if temp_fd != -1:
            with contextlib.suppress(OSError):
                os.close(temp_fd)
        with contextlib.suppress(OSError):
            temp_path.unlink(missing_ok=True)
        raise


def update_json_file(file_path: str | Path, update_dict: dict[str, object]) -> None:
    """Update the contents of a json file.

    Args:
        file_path: the path to the JSON file.
        update_dict: object to update json.
    """
    with json_file_lock(file_path) as fp:
        fp.parent.mkdir(parents=True, exist_ok=True)
        # An absent or empty file represents an empty JSON object.
        json_object: dict[str, object] = {}
        if fp.exists() and fp.stat().st_size:
            with fp.open(encoding="utf-8") as json_file:
                json_object = json.load(json_file)

        json_object.update(update_dict)
        _write_json_file(fp, json_object)


def find_replace(directory: str | Path, find: str, replace: str):
    """Recursively find and replace text in files in a directory.

    Args:
        directory: The directory to search.
        find: The text to find.
        replace: The text to replace.
    """
    directory = Path(directory)
    for root, _dirs, files in os.walk(directory):
        for file in files:
            filepath = Path(root, file)
            text = filepath.read_text(encoding="utf-8")
            text = re.sub(find, replace, text)
            filepath.write_text(text, encoding="utf-8")


def samefile(file1: Path, file2: Path) -> bool:
    """Check if two files are the same.

    Args:
        file1: The first file.
        file2: The second file.

    Returns:
        Whether the files are the same. If either file does not exist, returns False.
    """
    if file1.exists() and file2.exists():
        return file1.samefile(file2)

    return False


def update_directory_tree(src: Path, dest: Path):
    """Recursively copies a directory tree from src to dest.
    Only copies files if the destination file is missing or modified earlier than the source file.

    Args:
        src: Source directory
        dest: Destination directory

    Raises:
        ValueError: If the source is not a directory
    """
    if not src.is_dir():
        msg = f"Source {src} is not a directory"
        raise ValueError(msg)

    # Ensure the destination directory exists
    dest.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        dest_item = dest / item.name

        if item.is_dir():
            # Recursively copy subdirectories
            update_directory_tree(item, dest_item)
        elif item.is_file() and (
            not dest_item.exists() or item.stat().st_mtime > dest_item.stat().st_mtime
        ):
            # Copy file if it doesn't exist in the destination or is older than the source
            shutil.copy2(item, dest_item)
