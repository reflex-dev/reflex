"""Read the exports and imports of a JavaScript or TypeScript module.

A small tokenizer, not a parser: it knows enough of the language (strings,
template literals, regular expressions, comments and, in ``.jsx`` and ``.tsx``
files, JSX elements) that text inside them is never read as code, which is what
a regular expression over the source gets wrong. Exports and imports are then
read from the tokens.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterator, Sequence
from pathlib import Path

# Files whose imports are followed; other local files (CSS, JSON) are copied.
SCRIPT_SOURCE_EXTENSIONS = (".js", ".ts", ".mjs", ".jsx", ".tsx")
# Files whose `<` can start a JSX element.
_JSX_EXTENSIONS = (".jsx", ".tsx")
# Stylesheets, whose `@import` and `url(...)` references are followed.
STYLESHEET_EXTENSION = ".css"
# Tried in order for an import without an extension, as the bundler does.
_RESOLVE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs")

_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_REFERENCE_RE = re.compile(
    r"""@import\s+(?:url\(\s*)?["']?([^"')\s;]+)|url\(\s*["']?([^"')\s]+)["']?\s*\)"""
)
# Whitespace and comments; an unterminated block comment runs to the end.
_SPACE_RE = re.compile(r"(?:\s+|//[^\n]*|/\*.*?(?:\*/|\Z))*", re.DOTALL)
# Identifiers, keywords and numbers.
_NAME_RE = re.compile(r"[\w$\u0080-\U0010ffff]+")
# A `<` that starts a JSX element or fragment, and not the type parameters of a
# generic arrow function, which a `.tsx` file writes `<T,>` or `<T extends U>`.
_JSX_START_RE = re.compile(r"<(?!\s*[\w$]+\s*(?:,|extends\b))(?=>|[A-Za-z_$])")
# What ends the text of a template literal, of a JSX element and of a JSX tag.
_TEMPLATE_STOP_RE = re.compile(r"[\\`]|\$\{")
_JSX_STOP_RE = re.compile(r"[{<]")
_JSX_TAG_STOP_RE = re.compile(r"""["'{>]""")
# Punctuation read as one token: `=>`, so that `>` only closes brackets, and
# `++` and `--`, so that a slash after them is a division.
_LONG_PUNCTUATION = ("=>", "++", "--")
# After these, a value is expected: a slash starts a regular expression, and a
# `<` a JSX element or type parameters.
_PUNCT_BEFORE_OPERAND = frozenset([*"(,=:[!&|?{};+-*%<>~^}", "=>"])
_KEYWORDS_BEFORE_OPERAND = frozenset({
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
_CONTINUES_EXPRESSION = frozenset([*"=,+-*/%&|^!~?:<>.([{", "=>"])
_STARTS_CONTINUATION = frozenset(".,?:+-*/%&|^=<>)]}")
# Brackets, by their opening character.
_CLOSERS = {"(": ")", "[": "]", "{": "}", "<": ">"}
# Names a lone initializer can be that are never functions.
_LITERAL_NAMES = frozenset({"true", "false", "null", "undefined"})


@dataclasses.dataclass(frozen=True, slots=True)
class Token:
    """A token: a name (identifiers, keywords, numbers), a string, or punctuation."""

    # "name", "string", "punct", or "literal" for templates, regexes and JSX.
    kind: str
    # The text; the contents for a string.
    value: str
    # Whether a line break precedes the token.
    newline: bool
    # For a template or JSX literal, the tokens of the expressions in it.
    inner: tuple[Token, ...] = ()


@dataclasses.dataclass(frozen=True, slots=True)
class ScriptSource:
    """A module's source, with the names it exports and the modules it loads."""

    text: str
    # Exported names that may be functions, in the order they appear.
    functions: list[str]
    # Exported names known not to be functions, such as `export const n = 5`.
    values: list[str]
    # The specifiers it imports from, without TypeScript's type-only imports.
    imports: list[str]


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


def _skip_expression(source: str, index: int, jsx: bool, inner: list[Token]) -> int:
    """Skip the expression in a template's ``${...}`` or JSX's ``{...}``.

    Args:
        source: The source.
        index: The index after the opening brace.
        jsx: Whether the source can contain JSX.
        inner: Receives the expression's tokens.

    Returns:
        The index after the closing brace.
    """
    tokens, index = _scan(source, index, jsx, nested=True)
    inner.extend(tokens)
    return index


def _skip_template(source: str, start: int, jsx: bool, inner: list[Token]) -> int:
    """Skip a template literal, including the expressions in it.

    Args:
        source: The source.
        start: The index of the opening backtick.
        jsx: Whether the source can contain JSX.
        inner: Receives the tokens of its expressions.

    Returns:
        The index after the closing backtick.
    """
    index = start + 1
    while match := _TEMPLATE_STOP_RE.search(source, index):
        stop = match.group()
        if stop == "`":
            return match.end()
        index = (
            match.end() + 1
            if stop == "\\"
            else _skip_expression(source, match.end(), jsx, inner)
        )
    return len(source)


def _skip_jsx_tag(source: str, index: int, inner: list[Token]) -> tuple[int, bool]:
    """Skip a JSX tag, with its attributes.

    Args:
        source: The source.
        index: The index after the tag's ``<``.
        inner: Receives the tokens of its attribute expressions.

    Returns:
        The index after the tag's ``>``, and whether the tag closes itself.
    """
    while match := _JSX_TAG_STOP_RE.search(source, index):
        stop = match.group()
        if stop == ">":
            return match.end(), source[match.start() - 1] == "/"
        index = (
            _skip_expression(source, match.end(), True, inner)
            if stop == "{"
            else _read_string(source, match.start())[1]
        )
    return len(source), True


def _skip_jsx(source: str, index: int, inner: list[Token]) -> int:
    """Skip a JSX element or fragment, with its children.

    Args:
        source: The source.
        index: The index of its opening ``<``.
        inner: Receives the tokens of the expressions in it.

    Returns:
        The index after its closing tag.
    """
    depth = 0
    while match := _JSX_STOP_RE.search(source, index):
        if match.group() == "{":
            index = _skip_expression(source, match.end(), True, inner)
            continue
        closing = source.startswith("</", match.start())
        index, self_closing = _skip_jsx_tag(source, match.end(), inner)
        depth += -1 if closing else 0 if self_closing else 1
        if depth == 0:
            return index
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
            flags = _NAME_RE.match(source, index + 1)
            return flags.end() if flags else index + 1
        index += 1
    return len(source)


def _operand_expected(previous: Token | None) -> bool:
    """Whether a value, rather than an operator, follows a token.

    Args:
        previous: The token, or None at the start.

    Returns:
        Whether a slash after it starts a regular expression rather than a
        division, and a ``<`` starts a JSX element or type parameters rather
        than a comparison.
    """
    if previous is None:
        return True
    if previous.kind == "punct":
        return previous.value in _PUNCT_BEFORE_OPERAND
    return previous.kind == "name" and previous.value in _KEYWORDS_BEFORE_OPERAND


def _skip_operand(source: str, index: int, jsx: bool, inner: list[Token]) -> int | None:
    """Skip a regular expression or JSX element, where a value is expected.

    Args:
        source: The source.
        index: The index of a character that could start one.
        jsx: Whether the source can contain JSX.
        inner: Receives the tokens of a JSX element's expressions.

    Returns:
        The index after it, or None if none starts here.
    """
    if source[index] == "/":
        return _skip_regex(source, index)
    if jsx and _JSX_START_RE.match(source, index):
        return _skip_jsx(source, index, inner)
    return None


def _read_token(
    source: str, index: int, previous: Token | None, jsx: bool, inner: list[Token]
) -> tuple[str, str, int]:
    """Read the token at an index.

    Args:
        source: The source.
        index: The index, where no whitespace or comment starts.
        previous: The token before, or None at the start.
        jsx: Whether the source can contain JSX.
        inner: Receives the tokens of the expressions in a template or JSX.

    Returns:
        The token's kind and value, and the index after it.
    """
    char = source[index]
    if char in "'\"":
        value, end = _read_string(source, index)
        return "string", value, end
    if char == "`":
        return "literal", "", _skip_template(source, index, jsx, inner)
    if _operand_expected(previous) and (
        (end := _skip_operand(source, index, jsx, inner)) is not None
    ):
        return "literal", "", end
    if name := _NAME_RE.match(source, index):
        return "name", name.group(), name.end()
    if source.startswith(_LONG_PUNCTUATION, index):
        return "punct", source[index : index + 2], index + 2
    return "punct", char, index + 1


def _scan(source: str, index: int, jsx: bool, nested: bool) -> tuple[list[Token], int]:
    """Split a source into tokens, leaving out whitespace and comments.

    Args:
        source: The source.
        index: The index to start at.
        jsx: Whether the source can contain JSX.
        nested: Whether to stop after the ``}`` that closes a brace opened
            before the index, as for the expression in ``${...}``.

    Returns:
        The tokens, and the index after the last.
    """
    tokens: list[Token] = []
    depth = 0
    while True:
        # The pattern matches the empty string, so it always matches.
        start = _SPACE_RE.match(source, index).end()  # pyright: ignore[reportOptionalMemberAccess]
        if start >= len(source):
            return tokens, start
        newline = "\n" in source[index:start]
        inner: list[Token] = []
        kind, value, index = _read_token(
            source, start, tokens[-1] if tokens else None, jsx, inner
        )
        if kind == "punct" and value in "{}":
            depth += 1 if value == "{" else -1
            if nested and depth < 0:
                return tokens, index
        tokens.append(Token(kind, value, newline, tuple(inner)))


def tokenize(source: str, jsx: bool = False) -> list[Token]:
    """Split a JavaScript or TypeScript source into tokens, without comments.

    Args:
        source: The source.
        jsx: Whether the source can contain JSX, as a ``.jsx`` or ``.tsx`` file.

    Returns:
        The tokens.
    """
    return _scan(source, 0, jsx, nested=False)[0]


def _is(token: Token | None, kind: str, value: str | None = None) -> bool:
    """Whether a token is of a kind, and has a value if one is given.

    Args:
        token: The token, or None past the end.
        kind: The kind.
        value: The value, or None for any.

    Returns:
        Whether it matches.
    """
    return (
        token is not None
        and token.kind == kind
        and (value is None or token.value == value)
    )


def _at(tokens: Sequence[Token], index: int) -> Token | None:
    """Get the token at an index.

    Args:
        tokens: The tokens.
        index: The index, which may be out of range.

    Returns:
        The token, or None if there is none.
    """
    return tokens[index] if 0 <= index < len(tokens) else None


def _is_keyword(tokens: Sequence[Token], index: int, keyword: str) -> bool:
    """Whether a token is a keyword, and not a property of that name.

    Args:
        tokens: The tokens.
        index: The index, which may be out of range.
        keyword: The keyword.

    Returns:
        Whether the token is the keyword and does not follow a ``.``.
    """
    return _is(_at(tokens, index), "name", keyword) and not _is(
        _at(tokens, index - 1), "punct", "."
    )


def _skip_group(tokens: list[Token], start: int) -> int:
    """Skip a bracketed group, with the groups nested in it.

    Args:
        tokens: The tokens.
        start: The index of the opening bracket: ``(``, ``[``, ``{`` or ``<``.

    Returns:
        The index after the closing bracket.
    """
    opener = tokens[start].value
    brackets = (opener, _CLOSERS[opener])
    depth = 0
    for index in range(start, len(tokens)):
        token = tokens[index]
        if token.kind == "punct" and token.value in brackets:
            depth += 1 if token.value == opener else -1
            if depth == 0:
                return index + 1
    return len(tokens)


def _ends_statement(tokens: list[Token], index: int) -> bool:
    """Whether automatic semicolon insertion ends a statement before a token.

    Args:
        tokens: The tokens.
        index: The index of the token, after the statement's first.

    Returns:
        Whether a line break precedes the token and neither the line before
        nor the token continues the expression.
    """
    token = tokens[index]
    previous = tokens[index - 1]
    return (
        token.newline
        and not (previous.kind == "punct" and previous.value in _CONTINUES_EXPRESSION)
        and not (token.kind == "punct" and token.value in _STARTS_CONTINUATION)
    )


def _skip_to(tokens: list[Token], index: int, stops: str, annotation: bool) -> int:
    """Skip a type annotation or an expression, with the groups in it.

    Args:
        tokens: The tokens.
        index: The index after the ``:`` or ``=`` it follows.
        stops: The punctuation that ends it outside any group.
        annotation: Whether it is a type annotation, where every ``<`` opens
            type arguments. In an expression, only a ``<`` where a value is
            expected does, as type parameters or a type assertion; others
            compare.

    Returns:
        The index of the token that ends it, or the number of tokens.
    """
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "punct" and token.value in stops:
            return index
        if _ends_statement(tokens, index):
            return index
        opens = token.kind == "punct" and token.value in _CLOSERS
        if opens and (
            annotation or token.value != "<" or _operand_expected(tokens[index - 1])
        ):
            index = _skip_group(tokens, index)
        else:
            index += 1
    return index


def _skip_annotation(tokens: list[Token], index: int) -> int:
    """Skip a declarator's type annotation.

    Args:
        tokens: The tokens.
        index: The index after its ``:``.

    Returns:
        The index of the initializer's ``=``, or of what ends the declarator.
    """
    return _skip_to(tokens, index, "=,;)]}", annotation=True)


def _skip_initializer(tokens: list[Token], index: int) -> int:
    """Skip a declarator's initializer, or a default value in a pattern.

    Args:
        tokens: The tokens.
        index: The index after its ``=``.

    Returns:
        The index of the ``,`` before the next declarator, or of what ends the
        declaration.
    """
    return _skip_to(tokens, index, ",;)]}", annotation=False)


def _is_plain_value(tokens: list[Token], start: int, end: int) -> bool:
    """Whether an initializer is a literal that is never a function.

    Args:
        tokens: The tokens.
        start: The index of its first token.
        end: The index after its last token.

    Returns:
        Whether it is a lone string, number, template, regular expression, JSX
        element, boolean, null or undefined, or an array or object literal.
    """
    first = tokens[start]
    if first.kind == "punct":
        return first.value in ("[", "{") and _skip_group(tokens, start) == end
    return end == start + 1 and (
        first.kind in ("string", "literal")
        or first.value[0].isdigit()
        or first.value in _LITERAL_NAMES
    )


def _pattern_names(tokens: list[Token], start: int) -> tuple[list[str], int]:
    """Read the names a destructuring pattern declares.

    Args:
        tokens: The tokens.
        start: The index of the pattern's opening brace or bracket.

    Returns:
        The names, and the index after the pattern.
    """
    end = _skip_group(tokens, start)
    names: list[str] = []
    index = start + 1
    while index < end - 1:
        token = tokens[index]
        if token.kind == "punct" and token.value in ("{", "["):
            nested, index = _pattern_names(tokens, index)
            names.extend(nested)
        elif _is(token, "punct", "="):
            index = _skip_initializer(tokens, index + 1)
        else:
            # `{ key: name }` declares name, not key.
            if token.kind == "name" and not _is(tokens[index + 1], "punct", ":"):
                names.append(token.value)
            index += 1
    return names, end


def _declared_names(
    tokens: list[Token], index: int, constant: bool
) -> list[tuple[str, bool]]:
    """Read the names of an exported ``const``, ``let`` or ``var`` declaration.

    Args:
        tokens: The tokens.
        index: The index after the keyword.
        constant: Whether it is ``const``, whose names keep their initial value.

    Returns:
        Every declared name, ``export const a = 1, b = 2`` declaring two, and
        whether it may be a function.
    """
    names: list[tuple[str, bool]] = []
    while (token := _at(tokens, index)) is not None:
        if token.kind == "name":
            declared = [token.value]
            index += 1
        elif token.kind == "punct" and token.value in ("{", "["):
            declared, index = _pattern_names(tokens, index)
        else:
            break
        if _is(_at(tokens, index), "punct", ":"):
            index = _skip_annotation(tokens, index + 1)
        callable_ = True
        if _is(_at(tokens, index), "punct", "="):
            start = index + 1
            index = _skip_initializer(tokens, start)
            # Only a name bound by `const` to a literal is known not to be one.
            callable_ = not (
                constant
                and token.kind == "name"
                and _is_plain_value(tokens, start, index)
            )
        names.extend((name, callable_) for name in declared)
        if not _is(_at(tokens, index), "punct", ","):
            break
        index += 1
    return names


def _list_names(tokens: list[Token], start: int) -> list[str]:
    """Read the names an export list exports: ``{ a, b as c, "d" as e }``.

    Args:
        tokens: The tokens.
        start: The index of the opening brace.

    Returns:
        The exported names, without TypeScript's ``type`` items.
    """
    end = _skip_group(tokens, start)
    names: list[str] = []
    item_start = start + 1
    for index in range(item_start, end):
        if index < end - 1 and not _is(tokens[index], "punct", ","):
            continue
        item = tokens[item_start:index]
        item_start = index + 1
        # `type Foo` exports a type, but `type` alone or `type as t` a value.
        is_type = (
            len(item) > 1
            and _is(item[0], "name", "type")
            and not _is(item[1], "name", "as")
        )
        if item and not is_type:
            # The last name of an item is its exported name: `a as b` exports b.
            names.append(item[-1].value)
    return names


def _function_name(tokens: list[Token], index: int) -> list[tuple[str, bool]]:
    """Read the name of an exported function declaration.

    Args:
        tokens: The tokens.
        index: The index after ``function``.

    Returns:
        The name, or none for an anonymous function.
    """
    if _is(_at(tokens, index), "punct", "*"):
        index += 1
    name = _at(tokens, index)
    return [(name.value, True)] if name is not None and name.kind == "name" else []


def _export_names(tokens: list[Token], index: int) -> list[tuple[str, bool]]:
    """Read the names one ``export`` statement exports.

    Args:
        tokens: The tokens.
        index: The index after ``export``.

    Returns:
        The names, and whether each may be a function; none for a default
        export, a class, a namespace re-export or a type.
    """
    if _is(_at(tokens, index), "name", "async"):
        index += 1
    token = _at(tokens, index)
    if token is None:
        return []
    if _is(token, "name", "function"):
        return _function_name(tokens, index + 1)
    if token.kind == "name" and token.value in ("const", "let", "var"):
        return _declared_names(tokens, index + 1, constant=token.value == "const")
    if _is(token, "punct", "{"):
        return [(name, True) for name in _list_names(tokens, index)]
    return []


def _statement_start(tokens: Sequence[Token], index: int) -> int:
    """Find the ``import`` or ``export`` keyword an import clause follows.

    Args:
        tokens: The tokens.
        index: The index of the clause's last token, before ``from``.

    Returns:
        The index of the keyword.
    """
    while index > 0 and not (
        tokens[index].kind == "name" and tokens[index].value in ("import", "export")
    ):
        index -= 1
    return index


def _is_runtime_import(tokens: Sequence[Token], index: int) -> bool:
    """Whether a string is the specifier of a module the source loads.

    Covers ``import ... from "x"``, ``import "x"``, ``import("x")`` and
    ``export ... from "x"``, but not TypeScript's ``import type`` and
    ``export type``, which load nothing.

    Args:
        tokens: The tokens.
        index: The index of the string.

    Returns:
        Whether it is such a specifier.
    """
    if _is(_at(tokens, index - 1), "punct", "("):
        return _is_keyword(tokens, index - 2, "import")
    if _is_keyword(tokens, index - 1, "import"):
        return True
    if not _is(_at(tokens, index - 1), "name", "from"):
        return False
    start = _statement_start(tokens, index - 2)
    # `import type X from` loads nothing, but `import type from` and
    # `import type, { x } from` import a default export named type.
    after = _at(tokens, start + 2)
    return not (
        _is(tokens[start + 1], "name", "type")
        and not _is(after, "name", "from")
        and not _is(after, "punct", ",")
    )


def _runtime_imports(tokens: Sequence[Token]) -> Iterator[str]:
    """Yield the specifiers of the modules some tokens load.

    Args:
        tokens: The tokens, which may hold templates and JSX with expressions.

    Yields:
        Each specifier, including those inside a template's or JSX's expressions.
    """
    for index, token in enumerate(tokens):
        if token.kind == "string" and _is_runtime_import(tokens, index):
            yield token.value
        elif token.inner:
            yield from _runtime_imports(token.inner)


def parse_script(text: str, jsx: bool = False) -> ScriptSource:
    """Read the exports and imports of a module.

    Exports cover declared functions and variables (``export function f``,
    ``export const f = ...``, also several or destructured) and export lists
    (``export { a, b as c }``, also re-exported ``from`` another module). A
    default export, a class, ``export *`` and TypeScript types have no function
    name to import in Python and are left out.

    Args:
        text: The module source.
        jsx: Whether it can contain JSX, as a ``.jsx`` or ``.tsx`` file.

    Returns:
        The source with its exports and imports, each without duplicates.
    """
    tokens = tokenize(text, jsx)
    exports: dict[str, bool] = {}
    for index in range(len(tokens)):
        if _is_keyword(tokens, index, "export"):
            for name, callable_ in _export_names(tokens, index + 1):
                exports.setdefault(name, callable_)
    exports.pop("default", None)
    return ScriptSource(
        text=text,
        functions=[name for name, callable_ in exports.items() if callable_],
        values=[name for name, callable_ in exports.items() if not callable_],
        imports=list(dict.fromkeys(_runtime_imports(tokens))),
    )


def read_script(path: Path) -> ScriptSource:
    """Read a module file's exports and imports.

    Args:
        path: The file.

    Returns:
        Its source with its exports and imports.
    """
    return parse_script(
        path.read_text(encoding="utf-8"), jsx=path.suffix in _JSX_EXTENSIONS
    )


def find_stylesheet_references(source: str) -> list[str]:
    """Find the local files a stylesheet references.

    Covers ``@import`` and ``url(...)``. Absolute paths, URLs, data URIs and
    fragment references are not local files and are left out.

    Args:
        source: The stylesheet source.

    Returns:
        The relative references, without query or fragment, without duplicates.
    """
    references = (
        import_ or url
        for import_, url in _CSS_REFERENCE_RE.findall(_CSS_COMMENT_RE.sub("", source))
    )
    return list(
        dict.fromkeys(
            strip_query(reference)
            for reference in references
            if not reference.startswith(("/", "#", "data:")) and "://" not in reference
        )
    )


def strip_query(specifier: str) -> str:
    """Remove the query and fragment of an import specifier.

    Args:
        specifier: The specifier, such as ``./logo.png?url``.

    Returns:
        The path part, such as ``./logo.png``.
    """
    return specifier.split("?", 1)[0].split("#", 1)[0]


def _resolve_local(directory: Path, specifier: str) -> Path | None:
    """Find the file a relative import names, as the bundler would.

    A query or fragment, as in Vite's ``./logo.png?url``, is not part of the
    file name; the copied module keeps it.

    Args:
        directory: The importing file's directory.
        specifier: The relative specifier, such as ``./helpers`` or ``./x.js``.

    Returns:
        The file, or None if there is none.
    """
    target = directory / strip_query(specifier)
    candidates = [
        target,
        *(target.with_name(target.name + ext) for ext in _RESOLVE_EXTENSIONS),
    ]
    if target.suffix == ".js":
        # TypeScript imports a .ts file by the .js name it compiles to.
        candidates.append(target.with_suffix(".ts"))
    candidates.extend(target / f"index{ext}" for ext in _RESOLVE_EXTENSIONS)
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _read_references(file: Path) -> tuple[ScriptSource | None, list[Path]]:
    """Read a file and find the local files it references.

    Args:
        file: The file.

    Returns:
        The script, or None for another kind of file, and the resolved files
        its relative imports, or a stylesheet's ``@import`` and ``url(...)``
        references, name.
    """
    if file.suffix in SCRIPT_SOURCE_EXTENSIONS:
        script = read_script(file)
        return script, [
            target.resolve()
            for specifier in script.imports
            if specifier.startswith(".")
            and (target := _resolve_local(file.parent, specifier)) is not None
        ]
    if file.suffix == STYLESHEET_EXTENSION:
        return None, [
            target.resolve()
            for reference in find_stylesheet_references(
                file.read_text(encoding="utf-8")
            )
            if (target := file.parent / reference).is_file()
        ]
    # Images, fonts, data: nothing further to follow.
    return None, []


def module_files(path: Path) -> dict[Path, ScriptSource | None]:
    """Find a module and every local file it imports, directly or not.

    Scripts' relative imports are followed, and so are the ``@import`` and
    ``url(...)`` references of the stylesheets among them. Each file is read
    once.

    Args:
        path: The module.

    Returns:
        The resolved files, the module first, each with its script, or None if
        it is not a script.
    """
    files: dict[Path, ScriptSource | None] = {path.resolve(): None}
    pending = [path.resolve()]
    while pending:
        file = pending.pop()
        files[file], targets = _read_references(file)
        for target in targets:
            if target not in files:
                files[target] = None
                pending.append(target)
    return files
