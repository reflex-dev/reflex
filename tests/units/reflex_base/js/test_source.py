"""Tests for reading the exports and imports of JavaScript modules."""

from pathlib import Path

from reflex_base.js.source import (
    find_exports,
    find_imports,
    find_stylesheet_references,
    module_files,
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
export default function () {}
const later = await import("dayjs");
thing.export = 1;
thing.import("not-an-import");
"""


def test_find_exports():
    """Every exported function name is found, and nothing inside text or comments."""
    assert find_exports(SOURCE) == [
        "celebrate",
        "load",
        "steps",
        "first",
        "second",
        "typed",
        "other",
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


def test_find_imports():
    """Static, side-effect, dynamic and re-export specifiers, across line breaks."""
    assert find_imports(SOURCE) == [
        "canvas-confetti",
        "./helpers.js",
        "@scope/pkg/style.css",
        "lodash/fp",
        "everything",
        "namespaced",
        "dayjs",
    ]


def test_a_string_with_a_comment_opener_hides_nothing():
    """A comment opener inside a string does not swallow the code after it."""
    source = 'const route = "/api/*";\nexport function after() {}\n/* note */\n'
    assert find_exports(source) == ["after"]


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
    assert module_files(module) == [
        module.resolve(),
        (tmp_path / "lib" / "a.ts").resolve(),
        (tmp_path / "b.ts").resolve(),
        (tmp_path / "party.css").resolve(),
        (tmp_path / "widgets" / "index.js").resolve(),
        (tmp_path / "theme.css").resolve(),
        (tmp_path / "img" / "bg.png").resolve(),
    ]


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
