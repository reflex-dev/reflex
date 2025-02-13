from __future__ import annotations

import datetime
import json
from typing import Any

import plotly.graph_objects as go
import pytest

from reflex.components.tags.tag import Tag
from reflex.event import EventChain, EventHandler, EventSpec, JavascriptInputEvent
from reflex.style import Style
from reflex.utils import format
from reflex.utils.serializers import serialize_figure
from reflex.vars.base import LiteralVar, Var
from reflex.vars.object import ObjectVar
from tests.units.test_state import (
    ChildState,
    ChildState2,
    ChildState3,
    DateTimeState,
    GrandchildState,
    GrandchildState2,
    GrandchildState3,
    TestState,
)


def mock_event(arg):
    pass


@pytest.mark.parametrize(
    "input,output",
    [
        ("{", "}"),
        ("(", ")"),
        ("[", "]"),
        ("<", ">"),
        ('"', '"'),
        ("'", "'"),
    ],
)
def test_get_close_char(input: str, output: str):
    """Test getting the close character for a given open character.

    Args:
        input: The open character.
        output: The expected close character.
    """
    assert format.get_close_char(input) == output


@pytest.mark.parametrize(
    "text,open,expected",
    [
        ("", "{", False),
        ("{wrap}", "{", True),
        ("{wrap", "{", False),
        ("{wrap}", "(", False),
        ("(wrap)", "(", True),
    ],
)
def test_is_wrapped(text: str, open: str, expected: bool):
    """Test checking if a string is wrapped in the given open and close characters.

    Args:
        text: The text to check.
        open: The open character.
        expected: Whether the text is wrapped.
    """
    assert format.is_wrapped(text, open) == expected


@pytest.mark.parametrize(
    "text,open,check_first,num,expected",
    [
        ("", "{", True, 1, "{}"),
        ("wrap", "{", True, 1, "{wrap}"),
        ("wrap", "(", True, 1, "(wrap)"),
        ("wrap", "(", True, 2, "((wrap))"),
        ("(wrap)", "(", True, 1, "(wrap)"),
        ("{wrap}", "{", True, 2, "{wrap}"),
        ("(wrap)", "{", True, 1, "{(wrap)}"),
        ("(wrap)", "(", False, 1, "((wrap))"),
    ],
)
def test_wrap(text: str, open: str, expected: str, check_first: bool, num: int):
    """Test wrapping a string.

    Args:
        text: The text to wrap.
        open: The open character.
        expected: The expected output string.
        check_first: Whether to check if the text is already wrapped.
        num: The number of times to wrap the text.
    """
    assert format.wrap(text, open, check_first=check_first, num=num) == expected


@pytest.mark.parametrize(
    "input,output",
    [
        ("", ""),
        ("hello", "hello"),
        ("Hello", "hello"),
        ("camelCase", "camel_case"),
        ("camelTwoHumps", "camel_two_humps"),
        ("_start_with_underscore", "_start_with_underscore"),
        ("__start_with_double_underscore", "__start_with_double_underscore"),
        ("kebab-case", "kebab_case"),
        ("double-kebab-case", "double_kebab_case"),
        (":start-with-colon", ":start_with_colon"),
        (":-start-with-colon-dash", ":_start_with_colon_dash"),
    ],
)
def test_to_snake_case(input: str, output: str):
    """Test converting strings to snake case.

    Args:
        input: The input string.
        output: The expected output string.
    """
    assert format.to_snake_case(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("", ""),
        ("hello", "hello"),
        ("Hello", "Hello"),
        ("snake_case", "snakeCase"),
        ("snake_case_two", "snakeCaseTwo"),
        ("kebab-case", "kebabCase"),
        ("kebab-case-two", "kebabCaseTwo"),
        ("snake_kebab-case", "snakeKebabCase"),
        ("_hover", "_hover"),
        ("-starts-with-hyphen", "-startsWithHyphen"),
        ("--starts-with-double-hyphen", "--startsWithDoubleHyphen"),
        ("_starts_with_underscore", "_startsWithUnderscore"),
        ("__starts_with_double_underscore", "__startsWithDoubleUnderscore"),
        (":start-with-colon", ":startWithColon"),
        (":-start-with-colon-dash", ":StartWithColonDash"),
    ],
)
def test_to_camel_case(input: str, output: str):
    """Test converting strings to camel case.

    Args:
        input: The input string.
        output: The expected output string.
    """
    assert format.to_camel_case(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("", ""),
        ("hello", "Hello"),
        ("Hello", "Hello"),
        ("snake_case", "SnakeCase"),
        ("snake_case_two", "SnakeCaseTwo"),
    ],
)
def test_to_title_case(input: str, output: str):
    """Test converting strings to title case.

    Args:
        input: The input string.
        output: The expected output string.
    """
    assert format.to_title_case(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("", ""),
        ("hello", "hello"),
        ("Hello", "hello"),
        ("snake_case", "snake-case"),
        ("snake_case_two", "snake-case-two"),
        (":startWithColon", ":start-with-colon"),
        (":StartWithColonDash", ":-start-with-colon-dash"),
        (":start_with_colon", ":start-with-colon"),
        (":_start_with_colon_dash", ":-start-with-colon-dash"),
    ],
)
def test_to_kebab_case(input: str, output: str):
    """Test converting strings to kebab case.

    Args:
        input: the input string.
        output: the output string.
    """
    assert format.to_kebab_case(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (LiteralVar.create(value="test"), '"test"'),
        (Var(_js_expr="test"), "test"),
    ],
)
def test_format_var(input: Var, output: str):
    assert str(input) == output


@pytest.mark.parametrize(
    "route,format_case,expected",
    [
        ("", True, "index"),
        ("/", True, "index"),
        ("custom-route", True, "custom-route"),
        ("custom-route", False, "custom-route"),
        ("custom-route/", True, "custom-route"),
        ("custom-route/", False, "custom-route"),
        ("/custom-route", True, "custom-route"),
        ("/custom-route", False, "custom-route"),
        ("/custom_route", True, "custom-route"),
        ("/custom_route", False, "custom_route"),
        ("/CUSTOM_route", True, "custom-route"),
        ("/CUSTOM_route", False, "CUSTOM_route"),
    ],
)
def test_format_route(route: str, format_case: bool, expected: bool):
    """Test formatting a route.

    Args:
        route: The route to format.
        format_case: Whether to change casing to snake_case.
        expected: The expected formatted route.
    """
    assert format.format_route(route, format_case=format_case) == expected


@pytest.mark.parametrize(
    "prop,formatted",
    [
        ("string", '"string"'),
        ("{wrapped_string}", '"{wrapped_string}"'),
        (True, "true"),
        (False, "false"),
        (123, "123"),
        (3.14, "3.14"),
        ([1, 2, 3], "[1, 2, 3]"),
        (["a", "b", "c"], '["a", "b", "c"]'),
        ({"a": 1, "b": 2, "c": 3}, '({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })'),
        ({"a": 'foo "bar" baz'}, r'({ ["a"] : "foo \"bar\" baz" })'),
        (
            {
                "a": 'foo "{ "bar" }" baz',
                "b": Var(_js_expr="val", _var_type=str).guess_type(),
            },
            r'({ ["a"] : "foo \"{ \"bar\" }\" baz", ["b"] : val })',
        ),
        (
            EventChain(
                events=[EventSpec(handler=EventHandler(fn=mock_event))],
                args_spec=lambda: [],
            ),
            '((...args) => (addEvents([(Event("mock_event", ({  }), ({  })))], args, ({  }))))',
        ),
        (
            EventChain(
                events=[
                    EventSpec(
                        handler=EventHandler(fn=mock_event),
                        args=(
                            (
                                Var(_js_expr="arg"),
                                Var(
                                    _js_expr="_e",
                                )
                                .to(ObjectVar, JavascriptInputEvent)
                                .target.value,
                            ),
                        ),
                    )
                ],
                args_spec=lambda e: [e.target.value],
            ),
            '((_e) => (addEvents([(Event("mock_event", ({ ["arg"] : _e["target"]["value"] }), ({  })))], [_e], ({  }))))',
        ),
        (
            EventChain(
                events=[EventSpec(handler=EventHandler(fn=mock_event))],
                args_spec=lambda: [],
                event_actions={"stopPropagation": True},
            ),
            '((...args) => (addEvents([(Event("mock_event", ({  }), ({  })))], args, ({ ["stopPropagation"] : true }))))',
        ),
        (
            EventChain(
                events=[
                    EventSpec(
                        handler=EventHandler(fn=mock_event),
                        event_actions={"stopPropagation": True},
                    )
                ],
                args_spec=lambda: [],
            ),
            '((...args) => (addEvents([(Event("mock_event", ({  }), ({ ["stopPropagation"] : true })))], args, ({  }))))',
        ),
        (
            EventChain(
                events=[EventSpec(handler=EventHandler(fn=mock_event))],
                args_spec=lambda: [],
                event_actions={"preventDefault": True},
            ),
            '((...args) => (addEvents([(Event("mock_event", ({  }), ({  })))], args, ({ ["preventDefault"] : true }))))',
        ),
        ({"a": "red", "b": "blue"}, '({ ["a"] : "red", ["b"] : "blue" })'),
        (Var(_js_expr="var", _var_type=int).guess_type(), "var"),
        (
            Var(
                _js_expr="_",
                _var_type=Any,
            ),
            "_",
        ),
        (
            Var(_js_expr='state.colors["a"]', _var_type=str).guess_type(),
            'state.colors["a"]',
        ),
        (
            {"a": Var(_js_expr="val", _var_type=str).guess_type()},
            '({ ["a"] : val })',
        ),
        (
            {"a": Var(_js_expr='"val"', _var_type=str).guess_type()},
            '({ ["a"] : "val" })',
        ),
        (
            {"a": Var(_js_expr='state.colors["val"]', _var_type=str).guess_type()},
            '({ ["a"] : state.colors["val"] })',
        ),
        # tricky real-world case from markdown component
        (
            {
                "h1": Var(
                    _js_expr=f"(({{node, ...props}}) => <Heading {{...props}} {''.join(Tag(name='', props=Style({'as_': 'h1'})).format_props())} />)"
                ),
            },
            '({ ["h1"] : (({node, ...props}) => <Heading {...props} as={"h1"} />) })',
        ),
    ],
)
def test_format_prop(prop: Var, formatted: str):
    """Test that the formatted value of an prop is correct.

    Args:
        prop: The prop to test.
        formatted: The expected formatted value.
    """
    assert format.format_prop(LiteralVar.create(prop)) == formatted


@pytest.mark.parametrize(
    "single_props,key_value_props,output",
    [
        (
            [Var(_js_expr="{...props}")],
            {"key": 42},
            ["key={42}", "{...props}"],
        ),
    ],
)
def test_format_props(single_props, key_value_props, output):
    """Test the result of formatting a set of props (both single and keyvalue).

    Args:
        single_props: the list of single props
        key_value_props: the dict of key value props
        output: the expected output
    """
    assert format.format_props(*single_props, **key_value_props) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (EventHandler(fn=mock_event), ("", "mock_event")),
    ],
)
def test_get_handler_parts(input, output):
    assert format.get_event_handler_parts(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (TestState.do_something, f"{TestState.get_full_name()}.do_something"),
        (
            ChildState.change_both,
            f"{ChildState.get_full_name()}.change_both",
        ),
        (
            GrandchildState.do_nothing,
            f"{GrandchildState.get_full_name()}.do_nothing",
        ),
    ],
)
def test_format_event_handler(input, output):
    """Test formatting an event handler.

    Args:
        input: The event handler input.
        output: The expected output.
    """
    assert format.format_event_handler(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (
            EventSpec(handler=EventHandler(fn=mock_event)),
            '(Event("mock_event", ({  }), ({  })))',
        ),
    ],
)
def test_format_event(input, output):
    assert str(LiteralVar.create(input)) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ({"query": {"k1": 1, "k2": 2}}, {"k1": 1, "k2": 2}),
        ({"query": {"k1": 1, "k-2": 2}}, {"k1": 1, "k_2": 2}),
    ],
)
def test_format_query_params(input, output):
    assert format.format_query_params(input) == output


formatted_router = {
    "session": {"client_token": "", "client_ip": "", "session_id": ""},
    "headers": {
        "host": "",
        "origin": "",
        "upgrade": "",
        "connection": "",
        "cookie": "",
        "pragma": "",
        "cache_control": "",
        "user_agent": "",
        "sec_websocket_version": "",
        "sec_websocket_key": "",
        "sec_websocket_extensions": "",
        "accept_encoding": "",
        "accept_language": "",
    },
    "page": {
        "host": "",
        "path": "",
        "raw_path": "",
        "full_path": "",
        "full_raw_path": "",
        "params": {},
    },
}


@pytest.mark.parametrize(
    "input, output",
    [
        (
            TestState(_reflex_internal_init=True).dict(),  # pyright: ignore [reportCallIssue]
            {
                TestState.get_full_name(): {
                    "array": [1, 2, 3.14],
                    "complex": {
                        1: {"prop1": 42, "prop2": "hello"},
                        2: {"prop1": 42, "prop2": "hello"},
                    },
                    "dt": "1989-11-09 18:53:00+01:00",
                    "fig": serialize_figure(go.Figure()),
                    "key": "",
                    "map_key": "a",
                    "mapping": {"a": [1, 2, 3], "b": [4, 5, 6]},
                    "num1": 0,
                    "num2": 3.14,
                    "obj": {"prop1": 42, "prop2": "hello"},
                    "sum": 3.14,
                    "upper": "",
                    "router": formatted_router,
                    "asynctest": 0,
                },
                ChildState.get_full_name(): {
                    "count": 23,
                    "value": "",
                },
                ChildState2.get_full_name(): {"value": ""},
                ChildState3.get_full_name(): {"value": ""},
                GrandchildState.get_full_name(): {"value2": ""},
                GrandchildState2.get_full_name(): {"cached": ""},
                GrandchildState3.get_full_name(): {"computed": ""},
            },
        ),
        (
            DateTimeState(_reflex_internal_init=True).dict(),  # pyright: ignore [reportCallIssue]
            {
                DateTimeState.get_full_name(): {
                    "d": "1989-11-09",
                    "dt": "1989-11-09 18:53:00+01:00",
                    "t": "18:53:00+01:00",
                    "td": "11 days, 0:11:00",
                    "router": formatted_router,
                },
            },
        ),
    ],
)
def test_format_state(input, output):
    """Test that the format state is correct.

    Args:
        input: The state to format.
        output: The expected formatted state.
    """
    assert json.loads(format.json_dumps(input)) == json.loads(format.json_dumps(output))


@pytest.mark.parametrize(
    "input,output",
    [
        ("input1", "ref_input1"),
        ("input 1", "ref_input_1"),
        ("input-1", "ref_input_1"),
        ("input_1", "ref_input_1"),
        ("a long test?1! name", "ref_a_long_test_1_name"),
    ],
)
def test_format_ref(input, output):
    """Test formatting a ref.

    Args:
        input: The name to format.
        output: The expected formatted name.
    """
    assert format.format_ref(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (("my_array", None), "refs_my_array"),
        (("my_array", LiteralVar.create(0)), "refs_my_array[0]"),
        (("my_array", LiteralVar.create(1)), "refs_my_array[1]"),
    ],
)
def test_format_array_ref(input, output):
    assert format.format_array_ref(input[0], input[1]) == output


@pytest.mark.parametrize(
    "input, output",
    [
        ("library@^0.1.2", "library"),
        ("library", "library"),
        ("@library@^0.1.2", "@library"),
        ("@library", "@library"),
    ],
)
def test_format_library_name(input: str, output: str):
    """Test formatting a library name to remove the @version part.

    Args:
        input: the input string.
        output: the output string.
    """
    assert format.format_library_name(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (None, "null"),
        (True, "true"),
        (1, "1"),
        (1.0, "1.0"),
        ([], "[]"),
        ([1, 2, 3], "[1, 2, 3]"),
        ({}, "{}"),
        ({"k1": False, "k2": True}, '{"k1": false, "k2": true}'),
        (
            [datetime.timedelta(1, 1, 1), datetime.timedelta(1, 1, 2)],
            '["1 day, 0:00:01.000001", "1 day, 0:00:01.000002"]',
        ),
        (
            {"key1": datetime.timedelta(1, 1, 1), "key2": datetime.timedelta(1, 1, 2)},
            '{"key1": "1 day, 0:00:01.000001", "key2": "1 day, 0:00:01.000002"}',
        ),
    ],
)
def test_json_dumps(input, output):
    assert format.json_dumps(input) == output
