"""This module provides utilities for renaming directories and files in a Reflex app."""

import re
import sys
from pathlib import Path

from reflex import constants
from reflex.config import get_config
from reflex.utils import console
from reflex.utils.misc import get_module_path


def rename_path_up_tree(full_path: str | Path, old_name: str, new_name: str) -> Path:
    """Rename all instances of `old_name` in the path (file and directories) to `new_name`.
    The renaming stops when we reach the directory containing `rxconfig.py`.

    Args:
        full_path: The full path to start renaming from.
        old_name: The name to be replaced.
        new_name: The replacement name.

    Returns:
         The updated path after renaming.
    """
    current_path = Path(full_path)
    new_path = None

    while True:
        directory, base = current_path.parent, current_path.name
        # Stop renaming when we reach the root dir (which contains rxconfig.py)
        if current_path.is_dir() and (current_path / "rxconfig.py").exists():
            new_path = current_path
            break

        if old_name == base.removesuffix(constants.Ext.PY):
            new_base = base.replace(old_name, new_name)
            new_path = directory / new_base
            current_path.rename(new_path)
            console.debug(f"Renamed {current_path} -> {new_path}")
            current_path = new_path
        else:
            new_path = current_path

        # Move up the directory tree
        current_path = directory

    return new_path


def rename_app(new_app_name: str, loglevel: constants.LogLevel):
    """Rename the app directory.

    Args:
        new_app_name: The new name for the app.
        loglevel: The log level to use.

    Raises:
        SystemExit: If the command is not ran in the root dir or the app module cannot be imported.
    """
    # Set the log level.
    console.set_log_level(loglevel)

    if not constants.Config.FILE.exists():
        console.error(
            "No rxconfig.py found. Make sure you are in the root directory of your app."
        )
        raise SystemExit(1)

    sys.path.insert(0, str(Path.cwd()))

    config = get_config()
    module_path = get_module_path(config.module)
    if module_path is None:
        console.error(f"Could not find module {config.module}.")
        raise SystemExit(1)

    console.info(f"Renaming app directory to {new_app_name}.")
    process_directory(
        Path.cwd(),
        config.app_name,
        new_app_name,
        exclude_dirs=[constants.Dirs.WEB, constants.Dirs.APP_ASSETS],
    )

    rename_path_up_tree(module_path, config.app_name, new_app_name)

    console.success(f"App directory renamed to [bold]{new_app_name}[/bold].")


def rename_imports_and_app_name(file_path: str | Path, old_name: str, new_name: str):
    """Rename imports the file using string replacement as well as app_name in rxconfig.py.

    Args:
        file_path: The file to process.
        old_name: The old name to replace.
        new_name: The new name to use.
    """
    file_path = Path(file_path)
    content = file_path.read_text()

    # Replace `from old_name.` or `from old_name` with `from new_name`
    content = re.sub(
        rf"\bfrom {re.escape(old_name)}(\b|\.|\s)",
        lambda match: f"from {new_name}{match.group(1)}",
        content,
    )

    # Replace `import old_name` with `import new_name`
    content = re.sub(
        rf"\bimport {re.escape(old_name)}\b",
        f"import {new_name}",
        content,
    )

    # Replace `app_name="old_name"` in rx.Config
    content = re.sub(
        rf'\bapp_name\s*=\s*["\']{re.escape(old_name)}["\']',
        f'app_name="{new_name}"',
        content,
    )

    # Replace positional argument `"old_name"` in rx.Config
    content = re.sub(
        rf'\brx\.Config\(\s*["\']{re.escape(old_name)}["\']',
        f'rx.Config("{new_name}"',
        content,
    )

    file_path.write_text(content)


def process_directory(
    directory: str | Path,
    old_name: str,
    new_name: str,
    exclude_dirs: list | None = None,
    extensions: list | None = None,
):
    """Process files with specified extensions in a directory, excluding specified directories.

    Args:
        directory: The root directory to process.
        old_name: The old name to replace.
        new_name: The new name to use.
        exclude_dirs: List of directory names to exclude. Defaults to None.
        extensions: List of file extensions to process.
    """
    exclude_dirs = exclude_dirs or []
    extensions = extensions or [
        constants.Ext.PY,
        constants.Ext.MD,
    ]  # include .md files, typically used in reflex-web.
    extensions_set = {ext.lstrip(".") for ext in extensions}
    directory = Path(directory)

    root_exclude_dirs = {directory / exclude_dir for exclude_dir in exclude_dirs}

    files = (
        p.resolve()
        for p in directory.glob("**/*")
        if p.is_file() and p.suffix.lstrip(".") in extensions_set
    )

    for file_path in files:
        if not any(
            file_path.is_relative_to(exclude_dir) for exclude_dir in root_exclude_dirs
        ):
            rename_imports_and_app_name(file_path, old_name, new_name)
