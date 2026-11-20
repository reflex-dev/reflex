"""Tests for the type stubs of JavaScript modules imported from Python."""

import json
from pathlib import Path

import pytest
from reflex_base.js.stubs import (
    TYPESCRIPT_PACKAGE,
    Export,
    Parameter,
    module_digest,
    python_type,
    render_stub,
    render_untyped_stub,
    stub_header,
)

FRONTEND_PACKAGE_JSON = (
    Path(__file__).parents[4] / "packages/reflex-frontend/package.json"
)

IMPORTS = (
    "from builtins import bool as _bool, float as _float, int as _int, str as _str\n"
    "from builtins import tuple as _tuple\n"
    "from collections.abc import Mapping as _Mapping, Sequence as _Sequence\n"
    "from typing import Any as _Any, overload as _overload\n"
    "\n"
    "from reflex_base.event import EventCallback as _EventCallback, EventSpec as _EventSpec\n"
    "from reflex_base.vars.base import Var as _Var\n"
)


@pytest.mark.parametrize(
    ("ts_type", "expected"),
    [
        ("number", "float"),
        ("bigint", "int"),
        ("string", "str"),
        ("boolean", "bool"),
        ("true", "bool"),
        ("null", "None"),
        ("undefined", "None"),
        ("void", "None"),
        ("any", "Any"),
        ("unknown", "Any"),
        ("never", "Any"),
        ("object", "Mapping[str, Any]"),
        ("{ a: number; }", "Mapping[str, Any]"),
        ("Record<string, number>", "Mapping[str, Any]"),
        ("string | null", "str | None"),
        ("string | number | string", "str | float"),
        ("string | HTMLElement", "Any"),
        ('"a" | "b"', "str"),
        ("1 | 2", "float"),
        ("number[]", "Sequence[float]"),
        ("readonly string[]", "Sequence[str]"),
        ("(string | null)[]", "Sequence[str | None]"),
        ("Array<boolean>", "Sequence[bool]"),
        ("Set<number>", "Sequence[float]"),
        ("Promise<string>", "str"),
        ("[number, string]", "Sequence[Any]"),
        ("(a: number) => void", "Any"),
        ("HTMLElement", "Any"),
        ("Options", "Any"),
    ],
)
def test_python_type(ts_type: str, expected: str):
    """A TypeScript type maps to the Python type of the JSON value.

    Args:
        ts_type: The TypeScript type.
        expected: The Python type.
    """
    assert python_type(ts_type) == expected


def _param(
    name: str, ts_type: str, optional: bool = False, rest: bool = False
) -> Parameter:
    return {"name": name, "type": ts_type, "optional": optional, "rest": rest}


def _export(name: str, *signatures: list[Parameter], untyped: bool = False) -> Export:
    return {
        "name": name,
        "signatures": [{"parameters": parameters} for parameters in signatures],
        "untyped": untyped,
    }


HANDLER = "_str | _Var[_str] | _EventCallback[*_tuple[_Any, ...]]"


def test_render_stub():
    """Each export becomes a positional-only def with Var-accepting arguments."""
    exports = [
        _export(
            "celebrate",
            [
                _param("count", "number"),
                _param("elementId", "string"),
                _param("loud", "boolean | undefined", optional=True),
            ],
        ),
        _export("many", [_param("class", "any"), _param("names", "string", rest=True)]),
        _export("pick", [_param("n", "number")], []),
        _export("MAX"),
        _export("anything", untyped=True),
        _export("$private", []),
    ]
    assert render_stub(Path("party.js"), "abc", exports) == (
        stub_header(Path("party.js"), "abc") + "\n" + IMPORTS + "\n"
        "def celebrate(count: _float | _Var[_float], "
        f"elementId: {HANDLER}, loud: _bool | _Var[_bool] = ..., /) -> _EventSpec: ...\n"
        f"def many(arg0: _Any, /, *names: {HANDLER}) -> _EventSpec: ...\n"
        "@_overload\n"
        "def pick(n: _float | _Var[_float], /) -> _EventSpec: ...\n"
        "@_overload\n"
        "def pick() -> _EventSpec: ...\n"
        "def anything(*args: _Any) -> _EventSpec: ...\n"
    )


def test_renamed_parameters_do_not_collide():
    """A parameter renamed from a non-identifier never takes another's name."""
    exports = [
        _export(
            "send",
            [_param("$value", "any"), _param("arg0", "any"), _param("arg0_", "any")],
        )
    ]
    assert render_stub(Path("send.js"), "abc", exports).splitlines()[-1] == (
        "def send(arg0__: _Any, arg0: _Any, arg0_: _Any, /) -> _EventSpec: ..."
    )


def test_only_trailing_optional_parameters_have_defaults():
    """A default that a required parameter follows cannot be omitted in Python."""
    exports = [
        _export(
            "send",
            [
                _param("prefix", "string", optional=True),
                _param("count", "number"),
                _param("suffix", "string | undefined", optional=True),
            ],
        )
    ]
    assert render_stub(Path("send.ts"), "abc", exports).splitlines()[-1] == (
        f"def send(prefix: {HANDLER}, count: _float | _Var[_float], "
        f"suffix: {HANDLER} = ..., /) -> _EventSpec: ..."
    )


def test_exports_named_like_types_do_not_replace_them():
    """An export named ``str`` or ``Var`` leaves the stub's annotations intact.

    The stub uses private aliases for the types; an export named like one of
    those cannot be imported through the stub.
    """
    exports = [
        _export("str", [_param("value", "string"), _param("str", "number")]),
        _export("Var", [_param("n", "number")]),
        _export("_str", []),
    ]
    assert render_stub(Path("m.js"), "abc", exports).splitlines()[-2:] == [
        f"def str(value: {HANDLER}, str: _float | _Var[_float], /) -> _EventSpec: ...",
        "def Var(n: _float | _Var[_float], /) -> _EventSpec: ...",
    ]


def test_render_untyped_stub():
    """Without types, every export takes any arguments."""
    assert render_untyped_stub(Path("party.ts"), "untyped", ["go", "class"]) == (
        "# Generated by Reflex from party.ts (untyped); rewritten when it changes.\n"
        + IMPORTS
        + "\n"
        "def go(*args: _Any) -> _EventSpec: ...\n"
    )


def test_module_digest_covers_imports_and_packages(tmp_path: Path):
    """The digest changes with the module's local imports and the app's packages.

    Args:
        tmp_path: pytest tmp_path fixture.
    """
    (tmp_path / "lib").mkdir()
    module = tmp_path / "party.js"
    module.write_text('import { T } from "./lib/helpers";\nexport function go() {}\n')
    helper = tmp_path / "lib" / "helpers.ts"
    helper.write_text("export type T = number;\n")
    digest = module_digest(module, b'{"a": "1"}')
    assert len(digest) == 16
    (tmp_path / "unused.js").write_text("export const u = 1;\n")
    assert module_digest(module, b'{"a": "1"}') == digest
    assert module_digest(module, b'{"a": "2"}') != digest
    helper.write_text("export type T = string;\n")
    assert module_digest(module, b'{"a": "1"}') != digest


def test_module_digest_covers_the_types_a_module_reads(tmp_path: Path):
    """Declaration files and JSDoc type imports are part of the digest.

    Args:
        tmp_path: pytest tmp_path fixture.
    """
    module = tmp_path / "party.js"
    module.write_text(
        '/// <reference path="./globals.d.ts" />\n'
        '/** @param {import("./types").Count} n */\n'
        "export function go(n) {}\n"
    )
    declarations = tmp_path / "types.d.ts"
    declarations.write_text("export type Count = number;\n")
    globals_ = tmp_path / "globals.d.ts"
    globals_.write_text("declare const VERSION: string;\n")
    digest = module_digest(module)
    declarations.write_text("export type Count = string;\n")
    changed = module_digest(module)
    assert changed != digest
    globals_.write_text("declare const VERSION: number;\n")
    assert module_digest(module) != changed


def test_module_digest_is_the_same_on_every_machine(tmp_path: Path):
    """The same sources in different directories give the same digest.

    Args:
        tmp_path: pytest tmp_path fixture.
    """
    for checkout in ("one", "two"):
        (tmp_path / checkout).mkdir()
        (tmp_path / checkout / "party.js").write_text("export function go() {}\n")
    assert module_digest(tmp_path / "one" / "party.js") == module_digest(
        tmp_path / "two" / "party.js"
    )


def test_typescript_matches_the_frontend_package():
    """The typescript installed to read types is the one reflex-frontend uses."""
    dev_dependencies = json.loads(FRONTEND_PACKAGE_JSON.read_text())["devDependencies"]
    assert f"typescript@{dev_dependencies['typescript']}" == TYPESCRIPT_PACKAGE
