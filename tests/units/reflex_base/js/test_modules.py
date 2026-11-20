"""Tests for importing JavaScript modules from Python."""

import importlib
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from reflex_base.event import EventSpec
from reflex_base.js.finder import ScriptFinder
from reflex_base.js.modules import JsFunction, find_package_imports, module_key
from reflex_base.js.source import find_exports
from reflex_base.registry import RegistrationContext
from reflex_base.vars.base import LiteralVar, Var

import reflex as rx

SOURCE = """
import confetti from "canvas-confetti";
import { describe } from "./helpers.js";
import { env } from "$/utils/script_env";
import "@scope/pkg/style.css";
// export function commentedOut() {}
/* export const alsoCommentedOut = 1; */
export function celebrate(count) {}
export async function load() {}
export function* steps() {}
export const arrow = () => 1;
function hidden() {}
export { hidden, describe as describeIt };
export { other as reexported } from "lodash/fp";
export default function () {}
const later = await import("dayjs");
"""


def test_find_package_imports():
    """Only specifiers naming an npm package are installed."""
    assert find_package_imports(SOURCE) == [
        "canvas-confetti",
        "@scope/pkg/style.css",
        "lodash/fp",
        "dayjs",
    ]


def test_module_key_cannot_collide():
    """Module keys are JavaScript identifiers no two module names share."""
    assert module_key("app.scripts.party") == "app$scripts$party"
    assert module_key("app.scripts__party") != module_key("app__scripts.party")


def test_calling_a_function_builds_the_call_js_event():
    """Calling an export builds the event that names it, with JSON arguments."""
    spec = JsFunction("app.scripts.party", "celebrate")(200, "results")
    assert isinstance(spec, EventSpec)
    assert str(LiteralVar.create(spec)) == (
        '(ReflexEvent("_call_js", ({ ["module"] : "app$scripts$party", '
        '["function"] : "celebrate", ["args"] : [200, "results"] }), ({  })))'
    )


def test_an_event_handler_argument_is_sent_as_its_name():
    """An event handler argument arrives in JavaScript as its full name."""

    class JsHandlerState(rx.State):
        @rx.event
        def done(self, value: str):
            """Receive a value.

            Args:
                value: The value.
            """

    spec = JsFunction("app.scripts.party", "report")(JsHandlerState.done, "x")
    name = f"{JsHandlerState.get_full_name()}.done"
    assert str(LiteralVar.create(spec)) == (
        '(ReflexEvent("_call_js", ({ ["module"] : "app$scripts$party", '
        f'["function"] : "report", ["args"] : ["{name}", "x"] }}), ({{  }})))'
    )


def test_var_arguments_are_compiled_into_the_event():
    """A Var argument is compiled into the event payload."""
    count = Var(_js_expr="count").to(int)
    spec = JsFunction("app.scripts.party", "celebrate")(count)
    literal = LiteralVar.create(spec)
    assert str(literal) == (
        '(ReflexEvent("_call_js", ({ ["module"] : "app$scripts$party", '
        '["function"] : "celebrate", ["args"] : [count] }), ({  })))'
    )


@pytest.fixture
def script_package(
    tmp_path: Path, clean_registration_context: RegistrationContext
) -> Generator[Path, None, None]:
    """Put a package with a JavaScript module on sys.path.

    Args:
        tmp_path: pytest tmp_path fixture.
        clean_registration_context: a fresh registry for the imported module.

    Yields:
        The package directory.
    """
    package = tmp_path / "js_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "party.js").write_text(SOURCE)
    (package / "typed.ts").write_text("export function typed(n: number) {}\n")
    sys.path.insert(0, str(tmp_path))
    yield package
    sys.path.remove(str(tmp_path))
    for name in [n for n in sys.modules if n == "js_pkg" or n.startswith("js_pkg.")]:
        del sys.modules[name]


def test_importing_a_module_exposes_its_exports(
    script_package: Path, clean_registration_context: RegistrationContext
):
    """Importing a JavaScript module exposes its exports and registers it.

    Args:
        script_package: a package with JavaScript modules on sys.path.
        clean_registration_context: the registry the import fills.
    """
    assert any(isinstance(finder, ScriptFinder) for finder in sys.meta_path)
    party = importlib.import_module("js_pkg.party")
    assert party.__all__ == find_exports(SOURCE)
    assert party.celebrate == JsFunction("js_pkg.party", "celebrate")
    assert party.__spec__ is not None
    assert party.__spec__.origin == str(script_package / "party.js")
    typed = importlib.import_module("js_pkg.typed")
    assert typed.typed == JsFunction("js_pkg.typed", "typed")
    assert clean_registration_context.script_modules == {
        "js_pkg.party": script_package / "party.js",
        "js_pkg.typed": script_package / "typed.ts",
    }


def test_a_missing_module_still_fails_to_import(script_package: Path):
    """A name with neither a Python nor a JavaScript module still fails.

    Args:
        script_package: a package with JavaScript modules on sys.path.
    """
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("js_pkg.missing")


def test_a_python_module_wins_over_a_script_of_the_same_name(script_package: Path):
    """The finder runs last, so a Python module shadows a script of its name.

    Args:
        script_package: a package with JavaScript modules on sys.path.
    """
    (script_package / "both.py").write_text("VALUE = 'python'\n")
    (script_package / "both.js").write_text("export function VALUE() {}\n")
    assert importlib.import_module("js_pkg.both").VALUE == "python"


def test_a_function_is_an_event_trigger(script_package: Path):
    """An export works in an event trigger, called or uncalled.

    Args:
        script_package: a package with JavaScript modules on sys.path.
    """
    from js_pkg.party import celebrate  # pyright: ignore[reportMissingImports]

    called = rx.button("go", on_click=celebrate(1, "out"))
    assert str(LiteralVar.create(called.event_triggers["on_click"])) == (
        '((_e) => (addEvents([(ReflexEvent("_call_js", ({ ["module"] : '
        '"js_pkg$party", ["function"] : "celebrate", ["args"] : [1, "out"] }), '
        "({  })))], [_e], ({  }))))"
    )
    # Like an event handler, an uncalled function takes the trigger's arguments.
    uncalled = rx.input(on_change=celebrate)
    assert str(LiteralVar.create(uncalled.event_triggers["on_change"])) == (
        '((_e) => (addEvents([(ReflexEvent("_call_js", ({ ["module"] : '
        '"js_pkg$party", ["function"] : "celebrate", '
        '["args"] : [_e?.["target"]?.["value"]] }), ({  })))], [_e], ({  }))))'
    )


def test_the_finder_imports_nothing_heavy():
    """``import reflex`` installs the finder, so loading it stays cheap."""
    loaded = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, reflex_base.js.finder; "
                "print(sorted({'pathlib', 'typing', 'importlib.abc', 'reflex_base.event'}"
                " & set(sys.modules)))"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert loaded == "[]\n"
