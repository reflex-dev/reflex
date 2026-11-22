"""This module provides utilities for renaming directories and files in a Reflex app."""

import logging
import re
import sys
import tokenize
from pathlib import Path

from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.utils import console, log
from rich.markup import escape

from reflex.utils.misc import get_module_path

logger = logging.getLogger(__name__)


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
            logger.debug(f"Renamed {current_path} -> {new_path}")
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
        logger.error(
            "No rxconfig.py found. Make sure you are in the root directory of your app."
        )
        raise SystemExit(1)

    sys.path.insert(0, str(Path.cwd()))

    config = get_config()
    module_path = get_module_path(config.module)
    if module_path is None:
        logger.error(f"Could not find module {config.module}.")
        raise SystemExit(1)

    logger.info(f"Renaming app directory to {new_app_name}.")
    process_directory(
        Path.cwd(),
        config.app_name,
        new_app_name,
        exclude_dirs=[constants.Dirs.WEB, constants.Dirs.APP_ASSETS],
        main_module=tuple(config.module.split(".")),
    )

    rename_path_up_tree(module_path, config.app_name, new_app_name)

    logger.log(
        log.SUCCESS,
        f"App directory renamed to [bold]{escape(new_app_name)}[/bold].",
        extra={"rich": True},
    )


def _rename_main_module_imports(
    content: str,
    package: tuple[str, ...],
    main_module: tuple[str, ...],
    new_main_module: tuple[str, ...],
) -> str:
    """Point the imports of the app module in a file at the module's new path.

    Both absolute imports and imports relative to the file's package are renamed,
    including imports of the module's submodules when it is a package.

    Args:
        content: The source of the file.
        package: The path parts of the package holding the file, from the app root.
        main_module: The parts of the app module's import path.
        new_main_module: The parts of its import path after the rename.

    Returns:
        The source with the imports of the app module renamed.
    """
    parent = main_module[:-1]
    modules = {".".join(main_module): ".".join(new_main_module)}
    # A file in the module's package or below can import it relatively.
    if package[: len(parent)] == parent:
        dots = "." * (len(package) - len(parent) + 1)
        modules[dots + main_module[-1]] = dots + new_main_module[-1]
    for old, new in modules.items():
        content = re.sub(
            rf"(\b(?:from|import)\s+){re.escape(old)}(?!\w)", rf"\g<1>{new}", content
        )
    return content


def rename_imports_and_app_name(
    file_path: str | Path,
    old_name: str,
    new_name: str,
    package: tuple[str, ...] = (),
    main_module: tuple[str, ...] = (),
):
    """Rename imports the file using string replacement as well as app_name in rxconfig.py.

    Args:
        file_path: The file to process.
        old_name: The old name to replace.
        new_name: The new name to use.
        package: The path parts of the package holding the file, from the app root.
        main_module: The parts of the app module's import path, which is renamed
            along with its file and directories.
    """
    file_path = Path(file_path)
    if file_path.suffix == constants.Ext.PY:
        with file_path.open("rb") as source:
            encoding = tokenize.detect_encoding(source.readline)[0]
    else:
        encoding = "utf-8"
    with file_path.open("r", encoding=encoding, newline="") as source:
        content = source.read()

    if old_name in main_module:
        content = _rename_main_module_imports(
            content,
            package,
            main_module,
            tuple(new_name if part == old_name else part for part in main_module),
        )

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

    file_path.write_text(content, encoding=encoding, newline="")


def process_directory(
    directory: str | Path,
    old_name: str,
    new_name: str,
    exclude_dirs: list | None = None,
    extensions: list | None = None,
    main_module: tuple[str, ...] = (),
):
    """Process files with specified extensions in a directory, excluding specified directories.

    Args:
        directory: The root directory to process.
        old_name: The old name to replace.
        new_name: The new name to use.
        exclude_dirs: List of directory names to exclude. Defaults to None.
        extensions: List of file extensions to process.
        main_module: The parts of the app module's import path, which is renamed
            along with its file and directories.
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
        p
        for p in directory.glob("**/*")
        if p.is_file() and p.suffix.lstrip(".") in extensions_set
    )

    for path in files:
        file_path = path.resolve()
        if not any(
            file_path.is_relative_to(exclude_dir) for exclude_dir in root_exclude_dirs
        ):
            rename_imports_and_app_name(
                file_path,
                old_name,
                new_name,
                # Taken before resolving, so a link to a file outside the app is fine.
                package=path.parent.relative_to(directory).parts,
                main_module=main_module,
            )
