"""Tests for the functions of JavaScript modules imported from Python."""

import importlib
from pathlib import Path

import pytest
from reflex_base.js.modules import _JsFunction, _package_imports
from reflex_base.utils.exceptions import ReflexRuntimeError
from reflex_base.vars.base import LiteralVar, Var

import reflex as rx


def test_package_imports():
    """Only specifiers naming an npm package are installed, without a query."""
    assert _package_imports(
        Path("party.js"),
        [
            "canvas-confetti",
            "./helpers.js",
            "/abs.js",
            "$/utils/reflex",
            "#internal",
            "@/components/button",
            "virtual:pwa-register",
            "https://esm.sh/lodash",
            "@scope/pkg/style.css",
            "pkg/a.css?inline",
            "pkg/a.css",
            "path",
        ],
    ) == ["canvas-confetti", "@scope/pkg/style.css", "pkg/a.css", "path"]


@pytest.mark.parametrize("specifier", ["fs", "fs/promises", "node:path"])
def test_package_imports_rejects_node_builtins(specifier: str):
    """A Node.js built-in module cannot run in the browser.

    Args:
        specifier: the built-in module's specifier.
    """
    with pytest.raises(ReflexRuntimeError) as error:
        _package_imports(Path("/app/party.js"), ["canvas-confetti", specifier])
    assert str(error.value) == (
        f"The JavaScript file /app/party.js imports {specifier!r}, a Node.js "
        "built-in module, which does not exist in the browser. Remove the "
        "import, and do the work that needs it in a backend event handler "
        "instead."
    )


def test_calling_a_function_builds_the_call_js_event():
    """Calling a function builds the event that names it, with JSON arguments.

    The module is named as Python names it, whatever characters that has.
    """
    spec = _JsFunction("app.my-widget", "celebrate")(200, "results")
    assert str(LiteralVar.create(spec)) == (
        '(ReflexEvent("_call_js", ({ ["module"] : "app.my-widget", '
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

    spec = _JsFunction("app.scripts.party", "report")(JsHandlerState.done, "x")
    name = f"{JsHandlerState.get_full_name()}.done"
    assert str(LiteralVar.create(spec)) == (
        '(ReflexEvent("_call_js", ({ ["module"] : "app.scripts.party", '
        f'["function"] : "report", ["args"] : ["{name}", "x"] }}), ({{  }})))'
    )


def test_var_arguments_are_compiled_into_the_event():
    """A Var argument is compiled into the event payload."""
    count = Var(_js_expr="count").to(int)
    spec = _JsFunction("app.scripts.party", "celebrate")(count)
    assert str(LiteralVar.create(spec)) == (
        '(ReflexEvent("_call_js", ({ ["module"] : "app.scripts.party", '
        '["function"] : "celebrate", ["args"] : [count] }), ({  })))'
    )


def test_a_function_is_an_event_trigger(app_package: Path):
    """A function works in an event trigger, called or uncalled.

    Args:
        app_package: the app package, on sys.path.
    """
    from js_app.party import celebrate  # pyright: ignore[reportMissingImports]

    called = rx.button("go", on_click=celebrate(1, "out"))
    assert str(LiteralVar.create(called.event_triggers["on_click"])) == (
        '((_e) => (addEvents([(ReflexEvent("_call_js", ({ ["module"] : '
        '"js_app.party", ["function"] : "celebrate", ["args"] : [1, "out"] }), '
        "({  })))], [_e], ({  }))))"
    )
    # Like an event handler, an uncalled function takes the trigger's arguments:
    # none, one, or several.
    on_mount = rx.box(on_mount=celebrate)
    assert str(LiteralVar.create(on_mount.event_triggers["on_mount"])) == (
        '((...args) => (addEvents([(ReflexEvent("_call_js", ({ ["module"] : '
        '"js_app.party", ["function"] : "celebrate", ["args"] : [] }), '
        "({  })))], args, ({  }))))"
    )
    uncalled = rx.input(on_change=celebrate)
    assert str(LiteralVar.create(uncalled.event_triggers["on_change"])) == (
        '((_e) => (addEvents([(ReflexEvent("_call_js", ({ ["module"] : '
        '"js_app.party", ["function"] : "celebrate", '
        '["args"] : [_e?.["target"]?.["value"]] }), ({  })))], [_e], ({  }))))'
    )


def test_importing_a_missing_function_says_what_the_file_exports(app_package: Path):
    """The error names the file, its functions, and the export to add.

    Args:
        app_package: the app package, on sys.path.
    """
    with pytest.raises(ImportError) as error:
        from js_app.party import (  # pyright: ignore[reportMissingImports]
            nope,  # noqa: F401
        )
    assert str(error.value) == (
        f"Cannot import nope from js_app.party: {app_package / 'party.js'} "
        "exports no function named nope (its functions: celebrate, load, "
        "arrow). Export it from party.js, as in `export function nope() { ... }`."
    )
    (app_package / "empty.js").write_text("export class Widget {}\n")
    with pytest.raises(ImportError) as error:
        from js_app.empty import (  # pyright: ignore[reportMissingImports]
            Widget,  # noqa: F401
        )
    assert str(error.value) == (
        f"Cannot import Widget from js_app.empty: {app_package / 'empty.js'} "
        "exports no function named Widget (its functions: none). Export it "
        "from empty.js, as in `export function Widget() { ... }`."
    )


def test_importing_a_value_says_only_functions_can_be_called(app_package: Path):
    """A ``const`` bound to a literal is a value, which Python cannot call.

    Args:
        app_package: the app package, on sys.path.
    """
    with pytest.raises(ImportError) as error:
        from js_app.party import (  # pyright: ignore[reportMissingImports]
            notAFunction,  # noqa: F401
        )
    assert str(error.value) == (
        f"Cannot import notAFunction from js_app.party: {app_package / 'party.js'} "
        "exports notAFunction as a value, not a function, and Python can only "
        "call functions. Export a function instead, as in "
        "`export function notAFunction() { ... }`."
    )


def test_a_private_name_is_a_plain_attribute_error(app_package: Path):
    """Names tools probe a module for raise the AttributeError they expect.

    Args:
        app_package: the app package, on sys.path.
    """
    party = importlib.import_module("js_app.party")
    assert getattr(party, "__wrapped__", None) is None
    with pytest.raises(AttributeError) as error:
        _ = party._private
    assert str(error.value) == "module 'js_app.party' has no attribute '_private'"
