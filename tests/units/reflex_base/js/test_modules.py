"""Tests for the functions of JavaScript modules imported from Python."""

import importlib
import json
from pathlib import Path

import pytest
from reflex_base.event import Event
from reflex_base.event.context import EventContext
from reflex_base.js.modules import (
    _app_modules,
    _JsFunction,
    _package_imports,
    _render_stub,
)
from reflex_base.utils import format
from reflex_base.utils.exceptions import ReflexRuntimeError
from reflex_base.vars.base import LiteralVar, Var

import reflex as rx


def test_package_imports():
    """Only specifiers naming an npm package are installed, without a query."""
    assert _package_imports(
        Path("party.js"),
        [
            "canvas-confetti",
            "/abs.js",
            "$/utils/reflex",
            "#internal",
            "@/components/button",
            "virtual:pwa-register",
            "https://esm.sh/lodash",
            "@scope/pkg/style.css",
            "pkg/a.css?inline",
            "pkg/a.css#top",
            "path",
        ],
    ) == ["canvas-confetti", "@scope/pkg/style.css", "pkg/a.css", "path"]


@pytest.mark.parametrize("specifier", ["fs", "fs/promises", "node:path"])
def test_package_imports_rejects_node_builtins(specifier: str):
    """A Node.js built-in module cannot run in the browser.

    Args:
        specifier: the built-in module's specifier.
    """
    file = Path("/app/party.js")
    with pytest.raises(ReflexRuntimeError) as error:
        _package_imports(file, ["canvas-confetti", specifier])
    assert str(error.value) == (
        f"The JavaScript file {file} imports {specifier!r}, a Node.js "
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
    """An event handler argument arrives in JavaScript as its full name, in a list or a dict too."""

    class JsHandlerState(rx.State):
        @rx.event
        def done(self, value: str):
            """Receive a value.

            Args:
                value: The value.
            """

    done = JsHandlerState.done
    spec = _JsFunction("app.scripts.party", "report")(
        done, "x", [done, (done,)], {"on": {"done": done}}
    )
    name = f"{JsHandlerState.get_full_name()}.done"
    assert str(LiteralVar.create(spec)) == (
        '(ReflexEvent("_call_js", ({ ["module"] : "app.scripts.party", '
        f'["function"] : "report", ["args"] : ["{name}", "x", ["{name}", '
        f'["{name}"]], ({{ ["on"] : ({{ ["done"] : "{name}" }}) }})] }}), '
        "({  })))"
    )


def test_a_bound_event_argument_arrives_as_the_same_event_from_a_trigger_or_a_handler():
    """A bound event arrives as the event ``{name, payload}``, however it is sent.

    The event keeps its event actions, which ``addEvents`` applies.
    """

    class JsBoundEventState(rx.State):
        @rx.event
        def done(self, value: str):
            """Receive a value.

            Args:
                value: The value.
            """

    spec = _JsFunction("app.scripts.party", "report")(
        JsBoundEventState.done("v"), [JsBoundEventState.done("w").debounce(100)]
    )
    name = f"{JsBoundEventState.get_full_name()}.done"
    assert str(LiteralVar.create(spec)) == (
        '(ReflexEvent("_call_js", ({ ["module"] : "app.scripts.party", '
        f'["function"] : "report", ["args"] : [({{ ["name"] : "{name}", '
        '["payload"] : ({ ["value"] : "v" }) }), [({ ["name"] : '
        f'"{name}", ["payload"] : ({{ ["value"] : "w" }}), ["event_actions"] : '
        '({ ["debounce"] : 100 }) })]] }), ({  })))'
    )
    (event,) = Event.from_event_type(spec)
    assert json.loads(format.json_dumps(event.payload["args"])) == [
        {"name": name, "payload": {"value": "v"}},
        [{"name": name, "payload": {"value": "w"}, "event_actions": {"debounce": 100}}],
    ]


def test_handler_and_bound_event_arguments_send_the_same_values_from_a_trigger_or_a_handler():
    """A trigger compiles the arguments that a backend handler sends as JSON.

    Event handlers and bound events, in lists and dicts too, arrive with the
    same values either way.
    """

    class JsSameArgumentsState(rx.State):
        @rx.event
        def done(self, value: str):
            """Receive a value.

            Args:
                value: The value.
            """

    done = JsSameArgumentsState.done
    report = _JsFunction("app.scripts.party", "report")
    args = (done, done("v"), [done("w").debounce(100), (done,)], {"on": {"x": done}})
    trigger = str(
        LiteralVar.create(rx.button(on_click=report(*args)).event_triggers["on_click"])
    )
    (event,) = Event.from_event_type(report(*args))
    sent = json.loads(format.json_dumps(event.payload["args"]))
    assert f'["args"] : {LiteralVar.create(sent)!s} }}' in trigger


def test_an_uncalled_function_in_a_cond_is_called_with_no_arguments():
    """In ``rx.cond``, an uncalled function is called with no arguments, as an event handler is."""
    celebrate = _JsFunction("app.scripts.party", "celebrate")
    flag = Var(_js_expr="flag").to(bool)
    button = rx.button(on_click=rx.cond(flag, celebrate, celebrate(2)))
    assert str(LiteralVar.create(button.event_triggers["on_click"])) == (
        '((_e) => (addEvents([(flag ? (ReflexEvent("_call_js", ({ ["module"] : '
        '"app.scripts.party", ["function"] : "celebrate", ["args"] : [] }), '
        '({  }))) : (ReflexEvent("_call_js", ({ ["module"] : "app.scripts.party", '
        '["function"] : "celebrate", ["args"] : [2] }), ({  }))))], [_e], ({  }))))'
    )


def test_an_uncalled_function_keeps_its_event_actions():
    """Event actions set on an uncalled function apply to the call a trigger makes."""
    celebrate = _JsFunction("app.scripts.party", "celebrate").debounce(100)
    field = rx.input(on_change=celebrate)
    assert str(LiteralVar.create(field.event_triggers["on_change"])) == (
        '((_e) => (addEvents([(ReflexEvent("_call_js", ({ ["module"] : '
        '"app.scripts.party", ["function"] : "celebrate", '
        '["args"] : [_e?.["target"]?.["value"]] }), ({ ["debounce"] : 100 })))], '
        "[_e], ({  }))))"
    )


def test_an_uncalled_function_returned_by_a_handler_is_called_with_no_arguments():
    """A handler can return a function uncalled, as it can return an event handler."""
    assert Event.from_event_type(_JsFunction("app.scripts.party", "celebrate")) == [
        Event(
            name="_call_js",
            payload={
                "module": "app.scripts.party",
                "function": "celebrate",
                "args": [],
            },
        )
    ]


def test_var_arguments_are_compiled_into_the_event():
    """A Var argument is compiled into the event payload."""
    count = Var(_js_expr="count").to(int)
    spec = _JsFunction("app.scripts.party", "celebrate")(count)
    assert str(LiteralVar.create(spec)) == (
        '(ReflexEvent("_call_js", ({ ["module"] : "app.scripts.party", '
        '["function"] : "celebrate", ["args"] : [count] }), ({  })))'
    )


def test_render_stub_skips_names_python_cannot_import():
    """The stub leaves out functions whose names are not Python identifiers."""
    assert _render_stub(Path("party.js"), ["celebrate", "$private", "class"]) == (
        "# Generated by Reflex from party.js; rewritten when it changes.\n"
        "from typing import Any\n"
        "\n"
        "from reflex_base.event import EventSpec\n"
        "\n"
        "def celebrate(*args: Any) -> EventSpec: ...\n"
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


def test_an_uncalled_function_is_a_result_callback(app_package: Path):
    """Passed uncalled as a callback, a function receives the result, as a lambda does.

    Args:
        app_package: the app package, on sys.path.
    """
    from js_app.party import celebrate  # pyright: ignore[reportMissingImports]

    uncalled = str(LiteralVar.create(rx.call_script("[7, 8]", callback=celebrate)))
    assert uncalled == str(
        LiteralVar.create(
            rx.call_script("[7, 8]", callback=lambda result: celebrate(result))
        )
    )
    assert uncalled == (
        '(ReflexEvent("_call_script", ({ ["javascript_code"] : "[7, 8]", '
        '["callback"] : "(_result) => {addEvents([ReflexEvent(\\"_call_js\\", '
        '{module:\\"js_app.party\\",function:\\"celebrate\\",args:[_result]})])}" '
        "}), ({  })))"
    )


def test_a_module_first_imported_while_an_event_runs_is_an_error(app_package: Path):
    """A module first imported by an event handler was not imported when the app compiled.

    The frontend does not include it, so the import fails with the fix. The
    event processor's own context, which belongs to no event, does not count.

    Args:
        app_package: the app package, on sys.path.
    """

    def context(txid: str) -> EventContext:
        """Build an event context that runs nothing.

        Args:
            txid: the transaction id, empty for no event.

        Returns:
            The context.
        """
        return EventContext(
            token="t",
            state_manager=None,  # pyright: ignore[reportArgumentType]
            enqueue_impl=None,  # pyright: ignore[reportArgumentType]
            txid=txid,
        )

    with context("event"), pytest.raises(ReflexRuntimeError) as error:
        importlib.import_module("js_app.party")
    assert str(error.value) == (
        "The JavaScript module js_app.party is first imported while an event "
        "handler runs, after the app compiled, so the frontend does not include "
        "it. Import it at the top of a Python module that the app imports when "
        "it loads, such as the module that defines the event handler."
    )
    with context(""):
        assert importlib.import_module("js_app.party").celebrate == _JsFunction(
            "js_app.party", "celebrate"
        )


def test_names_become_functions_on_first_use(app_package: Path):
    """Any identifier is a function, recorded for the compiler and cached.

    Args:
        app_package: the app package, on sys.path.
    """
    party = importlib.import_module("js_app.party")
    from js_app.party import celebrate  # pyright: ignore[reportMissingImports]

    assert celebrate == _JsFunction("js_app.party", "celebrate")
    assert party.__dict__["celebrate"] is celebrate
    assert party._private == _JsFunction("js_app.party", "_private")
    assert _app_modules()["js_app.party"].names == {
        "celebrate",
        "_private",
    }


@pytest.mark.parametrize("name", ["__wrapped__", "not-an-identifier"])
def test_special_names_are_plain_attribute_errors(app_package: Path, name: str):
    """Names tools probe a module for raise the AttributeError they expect.

    Args:
        app_package: the app package, on sys.path.
        name: the name looked up.
    """
    party = importlib.import_module("js_app.party")
    assert getattr(party, name, None) is None
    with pytest.raises(AttributeError) as error:
        getattr(party, name)
    assert str(error.value) == f"module 'js_app.party' has no attribute {name!r}"
