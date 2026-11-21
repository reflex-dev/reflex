"""Tests for reading the exports and imports of JavaScript modules."""

from pathlib import Path

import pytest
from reflex_base.js.source import (
    find_stylesheet_references,
    module_files,
    parse_script,
    read_script,
)

SOURCE = r"""
import confetti from
  "canvas-confetti";
import {
  describe,
} from "./helpers.js";
import "@scope/pkg/style.css";
const route = "/api/*";
const pattern = /["'`]\/*/g, ratio = 4 / 2 / 1;
const text = `export function fake() {} ${`nested ${"}"}`} import "nope"`;
// export function commentedOut() {}
/* export const alsoCommentedOut = 1; */
export function celebrate(count) {}
export async function load() {}
export function* steps() {}
export const first = () => 1, second = (a, b) => [a, b];
export let typed: Record<string, number> = {}, other = 2
export const count = 5, label = "party", flags = [1, 2], options = { a: 1 }, none = null;
export const total = count + 1;
export const { pickA, pickB: renamed, ...rest } = obj;
export const [x0, , x2 = 3] = arr;
export const multiline = (a) =>
  a + 1;
export class NotAFunction {}
function hidden() {}
export { hidden, describe as describeIt, "string name" as quoted };
export { other2 as reexported } from "lodash/fp";
export * from "everything";
export * as namespace from "namespaced";
import type { Party } from "party-types";
export type { Guest } from "guest-types";
export type * from "all-types";
import type, { other3 } from "type-named";
export default function () {}
const later = await import("dayjs");
thing.export = 1;
thing.import("not-an-import");
"""


def test_parse_script():
    """Every export and import is found, and nothing inside text or comments.

    A ``const`` bound to a literal is a value; anything else may be a function.
    Type-only imports load nothing.
    """
    script = parse_script(SOURCE)
    assert script.text == SOURCE
    assert script.functions == [
        "celebrate",
        "load",
        "steps",
        "first",
        "second",
        "typed",
        "other",
        "total",
        "pickA",
        "renamed",
        "rest",
        "x0",
        "x2",
        "multiline",
        "hidden",
        "describeIt",
        "quoted",
        "reexported",
    ]
    assert script.values == ["count", "label", "flags", "options", "none"]
    assert script.imports == [
        "canvas-confetti",
        "./helpers.js",
        "@scope/pkg/style.css",
        "lodash/fp",
        "everything",
        "namespaced",
        "type-named",
        "dayjs",
    ]


@pytest.mark.parametrize(
    ("source", "functions", "values"),
    [
        # A comment opener inside a string hides nothing.
        (
            'const route = "/api/*";\nexport function after() {}\n/* note */\n',
            ["after"],
            [],
        ),
        # A slash after `++` or `--` divides; it does not start a regex.
        ("let i = 0; const y = i++ / 2; export function after() {}", ["after"], []),
        ("let i = 9; const y = i-- / 2; export function after() {}", ["after"], []),
        # TypeScript: a type item of an export list exports no value.
        ("export { type Foo, bar, type, type as t };", ["bar", "type", "t"], []),
        # `=>` and type arguments in an annotation.
        (
            "export const f: () => Map<string, Map<string, number>> = () => new Map();",
            ["f"],
            [],
        ),
        # Type parameters of a generic arrow function; a comparison.
        (
            "export const id = <T,>(x: T) => x, two = 2, less = 1 < 2, more = 3;",
            ["id", "less"],
            ["two", "more"],
        ),
        # A statement ends at a line break that nothing continues.
        ("export const a = 1\nexport const b = () =>\n  2\n", ["b"], ["a"]),
        ("export let mutable = 1;", ["mutable"], []),
        ("export function () {}\nexport function* () {}", [], []),
        # Escaped and unterminated strings and regular expressions.
        ("const s = 'it\\'s'; export function after() {}", ["after"], []),
        ("export function a() {}\nconst s = 'open", ["a"], []),
        ("export function a() {}\nconst r = /open", ["a"], []),
        # Nested patterns, declarators without an initializer, and no names.
        ("export const { a: { b }, c: [d, [e]] } = obj;", ["b", "d", "e"], []),
        ("export let later, typedLater: number;", ["later", "typedLater"], []),
        ("export let;", [], []),
        ("export", [], []),
        ("export const a = 1,", [], ["a"]),
    ],
)
def test_parse_script_exports(source: str, functions: list[str], values: list[str]):
    """Exports are read past regexes, divisions and TypeScript syntax.

    Args:
        source: The module source.
        functions: The exports that may be functions.
        values: The exports known to be values.
    """
    script = parse_script(source)
    assert (script.functions, script.values) == (functions, values)


def test_parse_script_skips_jsx():
    """In JSX, text and attributes are not code, but expressions in braces are."""
    source = (
        "const el = <div title=\"it's\" onClick={() => go(1 > 0)}>it's {`a${'}'}`}"
        "<br/><><span>/* not a comment</span></></div>; export function same() {}\n"
        "const id = <T,>(x: T) => x;\n"
        "export const element = <p>it's</p>;\n"
    )
    script = parse_script(source, jsx=True)
    assert (script.functions, script.values) == (["same"], ["element"])


@pytest.mark.parametrize(
    ("source", "jsx", "functions"),
    [
        ("const t = `${\nexport function a() {}", False, []),
        ("const t = `abc\nexport function a() {}", False, []),
        ("/* open\nexport function a() {}", False, []),
        ("export { a", False, []),
        # A regular expression ends at the end of its line.
        ("const r = /abc\nexport function a() {}", False, ["a"]),
        ("const e = <div>{\nexport function a() {}", True, []),
        ("const e = <div>text\nexport function a() {}", True, []),
        ("const e = <div title\nexport function a() {}", True, []),
    ],
)
def test_unterminated_code_runs_to_the_end(
    source: str, jsx: bool, functions: list[str]
):
    """A template, comment, group or JSX element left open runs to the end.

    Args:
        source: The module source.
        jsx: Whether it can contain JSX.
        functions: The exports found.
    """
    assert parse_script(source, jsx=jsx).functions == functions


def test_read_script_reads_jsx_by_extension(tmp_path: Path):
    """A ``.jsx`` or ``.tsx`` file is read with JSX; a ``.js`` file is not.

    Args:
        tmp_path: pytest tmp_path fixture.
    """
    source = "const el = <p>it's</p>; export function same() {}\n"
    for name in ("a.jsx", "a.tsx", "a.js"):
        (tmp_path / name).write_text(source)
    assert [
        read_script(tmp_path / name).functions for name in ("a.jsx", "a.tsx", "a.js")
    ] == [["same"], ["same"], []]


def test_module_files_follows_relative_imports(tmp_path: Path):
    """The module's local imports are found transitively, as the bundler resolves them.

    Args:
        tmp_path: pytest tmp_path fixture.
    """
    (tmp_path / "lib").mkdir()
    (tmp_path / "widgets").mkdir()
    module = tmp_path / "party.js"
    module.write_text(
        'import { a } from "./lib/a";\n'
        'import { b } from "./b.js";\n'
        'import "./party.css";\n'
        'import { w } from "./widgets";\n'
        'import { missing } from "./missing";\n'
        'import text from "./message.txt?raw";\n'
        'import confetti from "canvas-confetti";\n'
    )
    (tmp_path / "lib" / "a.ts").write_text('import { b } from "../b.js";\n')
    (tmp_path / "b.ts").write_text('import { a } from "./lib/a.js";\n')
    (tmp_path / "party.css").write_text(
        '@import "./theme.css";\nbody { background: url(img/bg.png?v=1); }\n'
    )
    (tmp_path / "theme.css").write_text("@import url('./missing.css');\n")
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "bg.png").write_bytes(b"\x89PNG")
    (tmp_path / "widgets" / "index.js").write_text("export const w = 1;\n")
    (tmp_path / "unused.js").write_text("export const u = 1;\n")
    (tmp_path / "message.txt").write_text("hello\n")
    files = module_files(module)
    assert list(files) == [
        module.resolve(),
        (tmp_path / "lib" / "a.ts").resolve(),
        (tmp_path / "b.ts").resolve(),
        (tmp_path / "party.css").resolve(),
        (tmp_path / "widgets" / "index.js").resolve(),
        (tmp_path / "message.txt").resolve(),
        (tmp_path / "theme.css").resolve(),
        (tmp_path / "img" / "bg.png").resolve(),
    ]
    # Each script is read once, and other files are not scripts.
    assert {file: script and script.text for file, script in files.items()} == {
        file: file.read_text() if file.suffix in (".js", ".ts") else None
        for file in files
    }


def test_find_stylesheet_references():
    """Local @import and url() references, without absolute paths, URLs or data."""
    source = """
    /* @import "./commented.css"; */
    @import "./theme.css";
    @import url('fonts.css') screen;
    @import "https://fonts.example.com/inter.css";
    .a { background: url(./bg.png?v=2#x); }
    .b { background: url("/static/abs.png"), url(data:image/png;base64,AAA); }
    .c { mask: url(#clip); }
    """
    assert find_stylesheet_references(source) == [
        "./theme.css",
        "fonts.css",
        "./bg.png",
    ]
