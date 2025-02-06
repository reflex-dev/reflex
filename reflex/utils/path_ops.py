"""Path operations."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
from pathlib import Path

from reflex import constants
from reflex.config import environment, get_config

# Shorthand for join.
join = os.linesep.join


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


def cp(src: str | Path, dest: str | Path, overwrite: bool = True) -> bool:
    """Copy a file or directory.

    Args:
        src: The path to the file or directory.
        dest: The path to the destination.
        overwrite: Whether to overwrite the destination.

    Returns:
        Whether the copy was successful.
    """
    src, dest = Path(src), Path(dest)
    if src == dest:
        return False
    if not overwrite and dest.exists():
        return False
    if src.is_dir():
        rm(dest)
        shutil.copytree(src, dest)
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


def use_system_node() -> bool:
    """Check if the system node should be used.

    Returns:
        Whether the system node should be used.
    """
    return environment.REFLEX_USE_SYSTEM_NODE.get()


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
    bin_path = Path(constants.Node.BIN_PATH)
    if not bin_path.exists():
        path = which("node")
        return path.parent.absolute() if path else None
    return bin_path.absolute()


def get_node_path() -> Path | None:
    """Get the node binary path.

    Returns:
        The path to the node binary file.
    """
    node_path = Path(constants.Node.PATH)
    if use_system_node() or not node_path.exists():
        node_path = which("node")
    return node_path


def get_npm_path() -> Path | None:
    """Get npm binary path.

    Returns:
        The path to the npm binary file.
    """
    npm_path = Path(constants.Node.NPM_PATH)
    if use_system_node() or not npm_path.exists():
        npm_path = which("npm")
    return npm_path.absolute() if npm_path else None


def get_bun_path() -> Path | None:
    """Get bun binary path.

    Returns:
        The path to the bun binary file.
    """
    bun_path = get_config().bun_path
    if use_system_bun() or not bun_path.exists():
        bun_path = which("bun")
    return bun_path.absolute() if bun_path else None


def update_json_file(file_path: str | Path, update_dict: dict[str, int | str]):
    """Update the contents of a json file.

    Args:
        file_path: the path to the JSON file.
        update_dict: object to update json.
    """
    fp = Path(file_path)

    # Create the parent directory if it doesn't exist.
    fp.parent.mkdir(parents=True, exist_ok=True)

    # Create the file if it doesn't exist.
    fp.touch(exist_ok=True)

    # Create an empty json object if file is empty
    fp.write_text("{}") if fp.stat().st_size == 0 else None

    # Read the existing json object from the file.
    json_object = {}
    if fp.stat().st_size:
        with fp.open() as f:
            json_object = json.load(f)

    # Update the json object with the new data.
    json_object.update(update_dict)

    # Write the updated json object to the file
    with fp.open("w") as f:
        json.dump(json_object, f, ensure_ascii=False)


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
