"""Read the exports and imports of a JavaScript or TypeScript module.

A small tokenizer, not a parser: it knows enough of the language (strings,
template literals, regular expressions and comments) that text inside them is
never read as code, which is what a regular expression over the source gets
wrong. Exports and imports are then read from the tokens.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

# Files whose imports are followed; other local files (CSS, JSON) are copied.
SCRIPT_SOURCE_EXTENSIONS = (".js", ".ts", ".mjs", ".jsx", ".tsx")
# Tried in order for an import without an extension, as the bundler does.
_RESOLVE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs")

_IDENTIFIER_RE = re.compile(r"[A-Za-z_$\u0080-￿][\w$\u0080-￿]*")
# A `/` after one of these starts a regular expression, not a division.
_PUNCT_BEFORE_REGEX = frozenset("(,=:[!&|?{};+-*%<>~^")
_KEYWORDS_BEFORE_REGEX = frozenset({
    "return",
    "typeof",
    "instanceof",
    "in",
    "of",
    "new",
    "delete",
    "void",
    "throw",
    "case",
    "do",
    "else",
    "yield",
    "await",
})
# A line break before a token ends a declaration unless the line before ends
# in, or the next one starts with, one of these.
_CONTINUES_EXPRESSION = frozenset("=,+-*/%&|^!~?:<>.([{")
_STARTS_CONTINUATION = frozenset(".,?:+-*/%&|^=<>)]}")


@dataclasses.dataclass(frozen=True, slots=True)
class Token:
    """A token: a name (identifiers, keywords, numbers), a string, or punctuation."""

    # "name", "string", "punct", or "literal" for templates and regexes.
    kind: str
    # The text; the contents for a string.
    value: str
    # Whether a line break precedes the token.
    newline: bool


def _read_string(source: str, start: int) -> tuple[str, int]:
    """Read a quoted string.

    Args:
        source: The source.
        start: The index of the opening quote.

    Returns:
        The contents, and the index after the closing quote.
    """
    quote = source[start]
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char in (quote, "\n"):
            return source[start + 1 : index], index + 1
        index += 1
    return source[start + 1 :], len(source)


def _skip_template(source: str, start: int) -> int:
    """Skip a template literal, including the expressions in it.

    Args:
        source: The source.
        start: The index of the opening backtick.

    Returns:
        The index after the closing backtick.
    """
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
        elif char == "`":
            return index + 1
        elif source.startswith("${", index):
            index = _skip_braces(source, index + 2)
        else:
            index += 1
    return len(source)


def _skip_braces(source: str, index: int) -> int:
    """Skip to the brace that closes one already open.

    Args:
        source: The source.
        index: The index after the opening brace.

    Returns:
        The index after the closing brace.
    """
    depth = 1
    while index < len(source):
        char = source[index]
        if char in "'\"":
            index = _read_string(source, index)[1]
        elif char == "`":
            index = _skip_template(source, index)
        elif source.startswith("//", index):
            index = _line_end(source, index)
        elif source.startswith("/*", index):
            index = _comment_end(source, index)
        else:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index + 1
            index += 1
    return len(source)


def _skip_regex(source: str, start: int) -> int:
    """Skip a regular expression literal and its flags.

    Args:
        source: The source.
        start: The index of the opening slash.

    Returns:
        The index after it.
    """
    index = start + 1
    in_class = False
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char == "\n":
            return index
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            index += 1
            while index < len(source) and (
                source[index].isalnum() or source[index] == "_"
            ):
                index += 1
            return index
        index += 1
    return len(source)


def _line_end(source: str, index: int) -> int:
    end = source.find("\n", index)
    return len(source) if end < 0 else end


def _comment_end(source: str, index: int) -> int:
    end = source.find("*/", index + 2)
    return len(source) if end < 0 else end + 2


def _regex_allowed(previous: Token | None) -> bool:
    """Whether a slash after a token starts a regular expression.

    Args:
        previous: The token before the slash.

    Returns:
        Whether it starts a regular expression rather than a division.
    """
    if previous is None:
        return True
    if previous.kind == "punct":
        return previous.value in _PUNCT_BEFORE_REGEX or previous.value == "}"
    return previous.kind == "name" and previous.value in _KEYWORDS_BEFORE_REGEX


def tokenize(source: str) -> list[Token]:
    """Split a JavaScript or TypeScript source into tokens, without comments.

    Args:
        source: The source.

    Returns:
        The tokens.
    """
    tokens: list[Token] = []
    newline = False
    index = 0
    length = len(source)
    while index < length:
        char = source[index]
        if char == "\n":
            newline = True
            index += 1
            continue
        if char.isspace():
            index += 1
            continue
        if source.startswith("//", index):
            index = _line_end(source, index)
            continue
        if source.startswith("/*", index):
            end = _comment_end(source, index)
            newline = newline or "\n" in source[index:end]
            index = end
            continue
        if char in "'\"":
            value, index = _read_string(source, index)
            tokens.append(Token("string", value, newline))
        elif char == "`":
            index = _skip_template(source, index)
            tokens.append(Token("literal", "", newline))
        elif char == "/" and _regex_allowed(tokens[-1] if tokens else None):
            index = _skip_regex(source, index)
            tokens.append(Token("literal", "", newline))
        elif char.isalnum() or char in "_$" or ord(char) > 127:
            end = index + 1
            while end < length and (
                source[end].isalnum() or source[end] in "_$" or ord(source[end]) > 127
            ):
                end += 1
            tokens.append(Token("name", source[index:end], newline))
            index = end
        else:
            tokens.append(Token("punct", char, newline))
            index += 1
        newline = False
    return tokens


def _is(token: Token | None, kind: str, value: str | None = None) -> bool:
    return (
        token is not None
        and token.kind == kind
        and (value is None or token.value == value)
    )


def _at(tokens: list[Token], index: int) -> Token | None:
    return tokens[index] if 0 <= index < len(tokens) else None


def _pattern_names(tokens: list[Token], index: int) -> tuple[list[str], int]:
    """Read the names a destructuring pattern declares.

    Args:
        tokens: The tokens.
        index: The index of the pattern's opening brace or bracket.

    Returns:
        The names, and the index after the pattern.
    """
    names: list[str] = []
    depth = 0
    skip_depth = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "punct" and token.value in "{[(":
            depth += 1
        elif token.kind == "punct" and token.value in "}])":
            if skip_depth == depth:
                skip_depth = 0
            depth -= 1
            if depth == 0:
                return names, index + 1
        elif _is(token, "punct", ",") and skip_depth == depth:
            skip_depth = 0
        elif _is(token, "punct", "="):
            # A default value, up to the next element of this pattern.
            skip_depth = skip_depth or depth
        elif (
            token.kind == "name"
            and not skip_depth
            and _IDENTIFIER_RE.fullmatch(token.value)
            and not _is(_at(tokens, index + 1), "punct", ":")
        ):
            names.append(token.value)
        index += 1
    return names, index


def _declared_names(tokens: list[Token], index: int) -> list[str]:
    """Read the names of an exported ``const``, ``let`` or ``var`` declaration.

    Args:
        tokens: The tokens.
        index: The index after the keyword.

    Returns:
        Every declared name, ``export const a = 1, b = 2`` declaring two.
    """
    names: list[str] = []
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "name" and _IDENTIFIER_RE.fullmatch(token.value):
            names.append(token.value)
            index += 1
        elif token.kind == "punct" and token.value in "{[":
            pattern, index = _pattern_names(tokens, index)
            names.extend(pattern)
        else:
            return names
        # Skip a type annotation and the initializer, up to the next declarator.
        depth = 0
        angle = 0
        annotation = _is(_at(tokens, index), "punct", ":")
        while index < len(tokens):
            token = tokens[index]
            previous = tokens[index - 1]
            if token.kind == "punct":
                if token.value in "([{":
                    depth += 1
                elif token.value in ")]}":
                    if depth == 0:
                        return names
                    depth -= 1
                elif annotation and depth == 0 and token.value in "<>":
                    angle += 1 if token.value == "<" else -1
                elif depth == 0 and angle == 0 and token.value == "=":
                    annotation = False
                elif depth == 0 and angle == 0 and token.value == ",":
                    index += 1
                    break
                elif depth == 0 and token.value == ";":
                    return names
            if (
                depth == 0
                and token.newline
                and not (
                    previous.kind == "punct" and previous.value in _CONTINUES_EXPRESSION
                )
                and not (token.kind == "punct" and token.value in _STARTS_CONTINUATION)
            ):
                return names
            index += 1
        else:
            return names
    return names


def _list_names(tokens: list[Token], index: int) -> list[str]:
    """Read the names an export list exports: ``{ a, b as c, "d" as e }``.

    Args:
        tokens: The tokens.
        index: The index after the opening brace.

    Returns:
        The exported names.
    """
    names: list[str] = []
    current: str | None = None
    while index < len(tokens):
        token = tokens[index]
        if _is(token, "punct", "}") or _is(token, "punct", ","):
            if current is not None:
                names.append(current)
            current = None
            if token.value == "}":
                break
        elif token.kind in ("name", "string") and token.value != "as":
            # The last name of an item is its exported name: `a as b` exports b.
            current = token.value
        index += 1
    return names


def _export_names(tokens: list[Token], index: int) -> list[str]:
    """Read the names one ``export`` statement exports.

    Args:
        tokens: The tokens.
        index: The index after ``export``.

    Returns:
        The names; none for a default export, a class, a namespace re-export or
        a type.
    """
    token = _at(tokens, index)
    if _is(token, "name", "async"):
        index += 1
        token = _at(tokens, index)
    if _is(token, "name", "function"):
        index += 1
        if _is(_at(tokens, index), "punct", "*"):
            index += 1
        name = _at(tokens, index)
        return [name.value] if name is not None and name.kind == "name" else []
    if (
        token is not None
        and token.kind == "name"
        and token.value in ("const", "let", "var")
    ):
        return _declared_names(tokens, index + 1)
    if _is(token, "punct", "{"):
        return _list_names(tokens, index + 1)
    return []


def find_exports(source: str) -> list[str]:
    """Find the names of the functions a module may export.

    Covers declared functions and variables (``export function f``,
    ``export const f = ...``, also several or destructured) and export lists
    (``export { a, b as c }``, also re-exported ``from`` another module). A
    default export, a class, ``export *`` and TypeScript types have no function
    name to import in Python and are left out.

    Args:
        source: The module source.

    Returns:
        The names, in the order they appear, without duplicates.
    """
    tokens = tokenize(source)
    names: list[str] = []
    for index, token in enumerate(tokens):
        if _is(token, "name", "export") and not _is(
            _at(tokens, index - 1), "punct", "."
        ):
            names.extend(_export_names(tokens, index + 1))
    return [name for name in dict.fromkeys(names) if name != "default"]


def find_imports(source: str) -> list[str]:
    """Find the specifiers a module imports or re-exports from.

    Covers ``import ... from "x"``, ``import "x"``, ``import("x")`` and
    ``export ... from "x"``, wherever line breaks fall.

    Args:
        source: The module source.

    Returns:
        The specifiers, without duplicates.
    """
    tokens = tokenize(source)
    specifiers: list[str] = []
    for index, token in enumerate(tokens):
        if token.kind != "string":
            continue
        keyword_index = index - 1
        if _is(_at(tokens, keyword_index), "punct", "("):
            # A dynamic import: `import("x")`.
            keyword_index -= 1
            if not _is(_at(tokens, keyword_index), "name", "import"):
                continue
        keyword = _at(tokens, keyword_index)
        if (
            keyword is not None
            and keyword.kind == "name"
            and keyword.value in ("from", "import")
            and not _is(_at(tokens, keyword_index - 1), "punct", ".")
        ):
            specifiers.append(token.value)
    return list(dict.fromkeys(specifiers))


def _resolve_local(directory: Path, specifier: str) -> Path | None:
    """Find the file a relative import names, as the bundler would.

    Args:
        directory: The importing file's directory.
        specifier: The relative specifier, such as ``./helpers`` or ``./x.js``.

    Returns:
        The file, or None if there is none.
    """
    target = directory / specifier
    candidates = [
        target,
        *(target.with_name(target.name + ext) for ext in _RESOLVE_EXTENSIONS),
    ]
    if target.suffix == ".js":
        # TypeScript imports a .ts file by the .js name it compiles to.
        candidates.append(target.with_suffix(".ts"))
    candidates.extend(target / f"index{ext}" for ext in _RESOLVE_EXTENSIONS)
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def module_files(path: Path) -> list[Path]:
    """Find a module and every local file it imports, directly or not.

    Args:
        path: The module.

    Returns:
        The resolved files, the module first.
    """
    files = {path.resolve(): None}
    pending = [path.resolve()]
    while pending:
        file = pending.pop()
        if file.suffix not in SCRIPT_SOURCE_EXTENSIONS:
            continue
        for specifier in find_imports(file.read_text(encoding="utf-8")):
            if not specifier.startswith("."):
                continue
            target = _resolve_local(file.parent, specifier)
            if target is not None and (target := target.resolve()) not in files:
                files[target] = None
                pending.append(target)
    return list(files)
