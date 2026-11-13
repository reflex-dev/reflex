"""Edit an app's source the way a hot reload benchmark needs: prepared, atomic, undoable.

A :class:`Target` is a piece of text in a file of a staged app: a string literal
on a line carrying a ``# bench:hmr-target <name>`` pragma (:func:`find_target`),
or any text of a file (:func:`text_target`). An :class:`Edit` builds the new
file content in memory, then writes it to a sibling temporary file, syncs it and
moves it over the target with one ``rename`` (``os.replace``), the only syscall
between the edit's timestamp and the change (file watchers see one complete
change, never a truncated file). :meth:`Edit.restore` puts the original bytes
back the same way.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

_PRAGMA = re.compile(
    rb"#[ \t]*bench:hmr-target[ \t]+(?P<name>[\w-]+)[ \t\r]*$", re.MULTILINE
)
_STRING = re.compile(rb"([\"'])(?P<value>[^\"'\\\r\n]*)\1")


@dataclass(frozen=True)
class Target:
    """The text an edit replaces.

    Attributes:
        path: The file.
        line_no: The 1-based line holding the text.
        literal: The text, e.g. ``m-initial-leaf`` (a string literal's value).
        original: The file's bytes before any edit.
        span: The byte offsets of ``literal`` in ``original``.
    """

    path: Path
    line_no: int
    literal: str
    original: bytes
    span: tuple[int, int]


def _python_files(app_dir: Path) -> Iterator[Path]:
    """List an app's Python files, skipping hidden and dunder directories (``.web``, ``__pycache__``).

    Args:
        app_dir: The app directory.

    Yields:
        The files, in a stable order.
    """
    for root, dirs, files in os.walk(app_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith((".", "__")))
        for name in sorted(files):
            if name.endswith(".py"):
                yield Path(root, name)


def find_target(app_dir: Path, name: str) -> Target:
    """Find the string literal on the line carrying ``# bench:hmr-target <name>``.

    Args:
        app_dir: The staged app.
        name: The target name, e.g. ``leaf``.

    Returns:
        The target.

    Raises:
        LookupError: When no line carries the pragma.
        ValueError: When the line has no string literal before the pragma.
    """
    for path in _python_files(app_dir):
        data = path.read_bytes()
        for pragma in _PRAGMA.finditer(data):
            if pragma["name"].decode() != name:
                continue
            line_start = data.rfind(b"\n", 0, pragma.start()) + 1
            line_no = data.count(b"\n", 0, line_start) + 1
            string = _STRING.search(data, line_start, pragma.start())
            if string is None:
                msg = f"{path}:{line_no}: the bench:hmr-target {name} line has no string literal"
                raise ValueError(msg)
            return Target(
                path=path,
                line_no=line_no,
                literal=string["value"].decode(),
                original=data,
                span=string.span("value"),
            )
    msg = f"no '# bench:hmr-target {name}' line in the Python files of {app_dir}"
    raise LookupError(msg)


def text_target(path: Path, literal: str, *, after: str = "") -> Target:
    """Find the first occurrence of some text in a file.

    Args:
        path: The file.
        literal: The text.
        after: Only look after the first occurrence of this text, e.g. a CSS
            selector.

    Returns:
        The target.

    Raises:
        LookupError: When the text (after ``after``) is not in the file.
    """
    data = path.read_bytes()
    marker = after.encode()
    anchor = data.find(marker)
    start = data.find(literal.encode(), max(anchor, 0) + len(marker))
    if anchor < 0 or start < 0:
        where = f" after {after!r}" if after else ""
        msg = f"{literal!r} not found{where} in {path}"
        raise LookupError(msg)
    return Target(
        path=path,
        line_no=data.count(b"\n", 0, start) + 1,
        literal=literal,
        original=data,
        span=(start, start + len(literal.encode())),
    )


class Edit:
    """Rewrites a target's text, one prepared value at a time.

    Attributes:
        target: The target.
        edited: Whether the file holds an edit that was not restored.
    """

    def __init__(self, target: Target) -> None:
        """Plan edits of a target.

        Args:
            target: The target; its ``original`` bytes are what :meth:`restore`
                writes back.
        """
        self.target = target
        self.edited = False
        self._content: bytes | None = None
        # File watchers ignore names ending in "~" (watchfiles' default filter,
        # which granian extends), so only the final rename is a change.
        self._tmp = target.path.with_name(f".{target.path.name}.bench~")

    def prepare(self, value: str) -> bytes:
        """Build the file content with the target's text replaced by ``value``.

        Args:
            value: The new text.

        Returns:
            The new content, which :meth:`write` writes.
        """
        start, end = self.target.span
        original = self.target.original
        self._content = original[:start] + value.encode() + original[end:]
        return self._content

    def write(self) -> int:
        """Write the prepared content.

        Returns:
            ``time.time_ns()`` taken just before the ``os.replace`` that makes the
            change.

        Raises:
            RuntimeError: Before :meth:`prepare`.
        """
        if self._content is None:
            msg = "prepare() the edit before writing it"
            raise RuntimeError(msg)
        t0 = self._replace(self._content)
        self.edited = True
        return t0

    def restore(self) -> int:
        """Write the original bytes back.

        Returns:
            ``time.time_ns()`` taken just before the ``os.replace``.
        """
        t0 = self._replace(self.target.original)
        self.edited = False
        return t0

    def _replace(self, data: bytes) -> int:
        """Swap the target file's content in one ``os.replace``.

        Args:
            data: The new content.

        Returns:
            ``time.time_ns()`` taken just before the replace.
        """
        with self._tmp.open("wb") as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        t0 = time.time_ns()
        self._tmp.replace(self.target.path)
        return t0
