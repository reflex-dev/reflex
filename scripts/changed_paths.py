"""Evaluate GitHub Actions path filters outside of a workflow trigger.

A workflow that ``on.paths``/``on.paths-ignore`` filters out never starts, so its
checks are never reported and a branch rule requiring them blocks the pull
request forever. Leaving the trigger unfiltered and skipping the jobs instead
reports those checks as skipped, which counts as a pass. This script evaluates
the filter that used to sit on the trigger, so the jobs skip on exactly the pull
requests the trigger used to drop.

Reads the changed paths from stdin, one per line, and writes ``true`` or
``false`` to stdout. The filter comes from whichever of ``FILTER_PATHS`` or
``FILTER_PATHS_IGNORE`` is set, as a newline-separated pattern list using
GitHub's filter pattern syntax.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterable, Sequence

# GitHub allows only alphanumerics and ranges inside a filter pattern's `[]`, so
# the contents pass through to the regex unescaped once they look like that.
_RANGE_BODY = re.compile(r"[A-Za-z0-9-]+")


def translate(pattern: str) -> re.Pattern[str]:
    """Compile one GitHub filter pattern into a regular expression.

    Args:
        pattern: A filter pattern, without any leading ``!``.

    Returns:
        A regex matching the repo-relative paths the pattern selects.

    Raises:
        ValueError: If the pattern contains an unsupported character range.
    """
    out: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        # `**/` spans zero or more leading directories, which is what makes
        # `**/*.md` cover a top-level README.md as well as docs/guide.md.
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
            continue
        if pattern.startswith("**", index):
            out.append(".*")
            index += 2
            continue
        if char == "[":
            end = pattern.find("]", index + 1)
            body = pattern[index + 1 : end] if end != -1 else ""
            if not _RANGE_BODY.fullmatch(body):
                msg = f"unsupported character range in filter pattern: {pattern!r}"
                raise ValueError(msg)
            out.append(f"[{body}]")
            index = end + 1
            continue
        if char == "\\" and index + 1 < len(pattern):
            out.append(re.escape(pattern[index + 1]))
            index += 2
            continue
        if char == "*":
            out.append("[^/]*")
        elif char in "?+":
            # GitHub reads these as quantifiers on the preceding character.
            out.append(char)
        else:
            out.append(re.escape(char))
        index += 1
    return re.compile("".join(out))


def compile_filters(patterns: Iterable[str]) -> list[tuple[bool, re.Pattern[str]]]:
    """Compile an ordered filter pattern list once, for reuse across paths.

    Args:
        patterns: Filter patterns, each optionally prefixed with ``!``.

    Returns:
        ``(negated, regex)`` pairs in the order the patterns were given.
    """
    return [
        (pattern.startswith("!"), translate(pattern.removeprefix("!")))
        for pattern in patterns
    ]


def selects(filters: Sequence[tuple[bool, re.Pattern[str]]], path: str) -> bool:
    """Return whether a compiled filter list selects one path.

    Args:
        filters: Compiled filters, in pattern order.
        path: A repo-relative changed path.

    Returns:
        True when the last pattern matching the path is a positive one.
    """
    selected = False
    for negated, regex in filters:
        if regex.fullmatch(path):
            selected = not negated
    return selected


def triggers(
    changed: Sequence[str],
    paths: Sequence[str] = (),
    paths_ignore: Sequence[str] = (),
) -> bool:
    """Return whether a path filter would have started a run for these changes.

    Args:
        changed: The repo-relative paths the pull request changes.
        paths: ``on.paths`` patterns; a run starts when a changed path matches.
        paths_ignore: ``on.paths-ignore`` patterns; a run starts when a changed
            path matches none of them.

    Returns:
        True when the filter selects the change set. A change set with no paths
        at all also returns True, so an unreadable diff runs the jobs rather
        than silently skipping them.
    """
    if not changed:
        return True
    if paths:
        filters = compile_filters(paths)
        return any(selects(filters, path) for path in changed)
    filters = compile_filters(paths_ignore)
    return any(not selects(filters, path) for path in changed)


def lines(text: str) -> list[str]:
    """Split a newline-separated input into stripped, non-empty entries.

    Args:
        text: The raw input.

    Returns:
        The non-empty lines, stripped of surrounding whitespace.
    """
    return [stripped for line in text.splitlines() if (stripped := line.strip())]


def main() -> int:
    """Evaluate the configured filter against the paths on stdin.

    Returns:
        The process exit code.
    """
    paths = lines(os.environ.get("FILTER_PATHS", ""))
    paths_ignore = lines(os.environ.get("FILTER_PATHS_IGNORE", ""))
    if bool(paths) == bool(paths_ignore):
        print(
            "set exactly one of FILTER_PATHS or FILTER_PATHS_IGNORE",
            file=sys.stderr,
        )
        return 2
    print("true" if triggers(lines(sys.stdin.read()), paths, paths_ignore) else "false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
