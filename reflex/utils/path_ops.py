"""Path operations."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from reflex import constants

# Shorthand for join.
join = os.linesep.join


def rm(path: str):
    """Remove a file or directory.

    Args:
        path: The path to the file or directory.
    """
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def cp(src: str, dest: str, overwrite: bool = True) -> bool:
    """Copy a file or directory.

    Args:
        src: The path to the file or directory.
        dest: The path to the destination.
        overwrite: Whether to overwrite the destination.

    Returns:
        Whether the copy was successful.
    """
    if src == dest:
        return False
    if not overwrite and os.path.exists(dest):
        return False
    if os.path.isdir(src):
        rm(dest)
        shutil.copytree(src, dest)
    else:
        shutil.copyfile(src, dest)
    return True


def mv(src: str, dest: str, overwrite: bool = True) -> bool:
    """Move a file or directory.

    Args:
        src: The path to the file or directory.
        dest: The path to the destination.
        overwrite: Whether to overwrite the destination.

    Returns:
        Whether the move was successful.
    """
    if src == dest:
        return False
    if not overwrite and os.path.exists(dest):
        return False
    rm(dest)
    shutil.move(src, dest)
    return True


def mkdir(path: str):
    """Create a directory.

    Args:
        path: The path to the directory.
    """
    os.makedirs(path, exist_ok=True)


def ln(src: str, dest: str, overwrite: bool = False) -> bool:
    """Create a symbolic link.

    Args:
        src: The path to the file or directory.
        dest: The path to the destination.
        overwrite: Whether to overwrite the destination.

    Returns:
        Whether the link was successful.
    """
    if src == dest:
        return False
    if not overwrite and (os.path.exists(dest) or os.path.islink(dest)):
        return False
    if os.path.isdir(src):
        rm(dest)
        os.symlink(src, dest, target_is_directory=True)
    else:
        os.symlink(src, dest)
    return True


def which(program: str) -> str | None:
    """Find the path to an executable.

    Args:
        program: The name of the executable.

    Returns:
        The path to the executable.
    """
    return shutil.which(program)


def get_node_bin_path() -> str | None:
    """Get the node binary dir path.

    Returns:
        The path to the node bin folder.
    """
    if not os.path.exists(constants.Node.BIN_PATH):
        str_path = which("node")
        return str(Path(str_path).parent) if str_path else str_path
    return constants.Node.BIN_PATH


def get_node_path() -> str | None:
    """Get the node binary path.

    Returns:
        The path to the node binary file.
    """
    if not os.path.exists(constants.Node.PATH):
        return which("node")
    return constants.Node.PATH


def get_npm_path() -> str | None:
    """Get npm binary path.

    Returns:
        The path to the npm binary file.
    """
    if not os.path.exists(constants.Node.PATH):
        return which("npm")
    return constants.Node.NPM_PATH


def update_json_file(file_path: str, update_dict: dict[str, int | str]):
    """Update the contents of a json file.

    Args:
        file_path: the path to the JSON file.
        update_dict: object to update json.
    """
    fp = Path(file_path)

    # Create the file if it doesn't exist.
    fp.touch(exist_ok=True)

    # Create an empty json object if file is empty
    fp.write_text("{}") if fp.stat().st_size == 0 else None

    # Read the existing json object from the file.
    json_object = {}
    if fp.stat().st_size == 0:
        with open(fp) as f:
            json_object = json.load(f)

    # Update the json object with the new data.
    json_object.update(update_dict)

    # Write the updated json object to the file
    with open(fp, "w") as f:
        json.dump(json_object, f, ensure_ascii=False)
