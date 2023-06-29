"""Path operations."""

from __future__ import annotations

import os
import shutil
from typing import Optional

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


def which(program: str) -> Optional[str]:
    """Find the path to an executable.

    Args:
        program: The name of the executable.

    Returns:
        The path to the executable.
    """
    return shutil.which(program)
