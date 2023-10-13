from typing import Any

import pytest

from reflex.components.tags.tag import Tag
from reflex.event import EventChain, EventHandler, EventSpec
from reflex.style import Style
from reflex.utils import format
from reflex.vars import BaseVar, Var
from tests.test_state import ChildState, DateTimeState, GrandchildState, TestState


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
    "text,indent_level,expected",
    [
        ("", 2, ""),
        ("hello", 2, "hello"),
        ("hello\nworld", 2, "  hello\n  world\n"),
        ("hello\nworld", 4, "    hello\n    world\n"),
        ("  hello\n  world", 2, "    hello\n    world\n"),
    ],
)
def test_indent(text: str, indent_level: int, expected: str, windows_platform: bool):
    """Test indenting a string.

    Args:
        text: The text to indent.
        indent_level: The number of spaces to indent by.
        expected: The expected output string.
        windows_platform: Whether the system is windows.
    """
    assert format.indent(text, indent_level) == (
        expected.replace("\n", "\r\n") if windows_platform else expected
    )


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
        ("", "{``}"),
        ("hello", "{`hello`}"),
        ("hello world", "{`hello world`}"),
        ("hello=`world`", "{`hello=\\`world\\``}"),
    ],
)
def test_format_string(input: str, output: str):
    """Test formating the input as JS string literal.

    Args:
        input: the input string.
        output: the output string.
    """
    assert format.format_string(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (Var.create(value="test"), "{`test`}"),
        (Var.create(value="test", _var_is_local=True), "{`test`}"),
        (Var.create(value="test", _var_is_local=False), "{test}"),
        (Var.create(value="test", _var_is_string=True), "{`test`}"),
        (Var.create(value="test", _var_is_string=False), "{`test`}"),
        (Var.create(value="test", _var_is_local=False, _var_is_string=False), "{test}"),
    ],
)
def test_format_var(input: Var, output: str):
    assert format.format_var(input) == output


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
    "condition,true_value,false_value,expected",
    [
        ("cond", "<C1>", '""', '{isTrue(cond) ? <C1> : ""}'),
        ("cond", "<C1>", "<C2>", "{isTrue(cond) ? <C1> : <C2>}"),
    ],
)
def test_format_cond(condition: str, true_value: str, false_value: str, expected: str):
    """Test formatting a cond.

    Args:
        condition: The condition to check.
        true_value: The value to return if the condition is true.
        false_value: The value to return if the condition is false.
        expected: The expected output string.
    """
    assert format.format_cond(condition, true_value, false_value) == expected


@pytest.mark.parametrize(
    "prop,formatted",
    [
        ("string", '"string"'),
        ("{wrapped_string}", "{wrapped_string}"),
        (True, "{true}"),
        (False, "{false}"),
        (123, "{123}"),
        (3.14, "{3.14}"),
        ([1, 2, 3], "{[1, 2, 3]}"),
        (["a", "b", "c"], '{["a", "b", "c"]}'),
        ({"a": 1, "b": 2, "c": 3}, '{{"a": 1, "b": 2, "c": 3}}'),
        ({"a": 'foo "bar" baz'}, r'{{"a": "foo \"bar\" baz"}}'),
        (
            {
                "a": 'foo "{ "bar" }" baz',
                "b": BaseVar(_var_name="val", _var_type="str"),
            },
            r'{{"a": "foo \"{ \"bar\" }\" baz", "b": val}}',
        ),
        ({"a": "red", "b": "blue"}, '{{"a": "red", "b": "blue"}}'),
        (BaseVar(_var_name="var", _var_type="int"), "{var}"),
        (
            BaseVar(
                _var_name="_",
                _var_type=Any,
                _var_state="",
                _var_is_local=True,
                _var_is_string=False,
            ),
            "{_}",
        ),
        (
            BaseVar(_var_name='state.colors["a"]', _var_type="str"),
            '{state.colors["a"]}',
        ),
        ({"a": BaseVar(_var_name="val", _var_type="str")}, '{{"a": val}}'),
        ({"a": BaseVar(_var_name='"val"', _var_type="str")}, '{{"a": "val"}}'),
        (
            {"a": BaseVar(_var_name='state.colors["val"]', _var_type="str")},
            '{{"a": state.colors["val"]}}',
        ),
        # tricky real-world case from markdown component
        (
            {
                "h1": f"{{({{node, ...props}}) => <Heading {{...props}} {''.join(Tag(name='', props=Style({'as_': 'h1'})).format_props())} />}}"
            },
            '{{"h1": ({node, ...props}) => <Heading {...props} as={`h1`} />}}',
        ),
    ],
)
def test_format_prop(prop: Var, formatted: str):
    """Test that the formatted value of an prop is correct.

    Args:
        prop: The prop to test.
        formatted: The expected formatted value.
    """
    assert format.format_prop(prop) == formatted


@pytest.mark.parametrize(
    "single_props,key_value_props,output",
    [
        (["string"], {"key": 42}, ["key={42}", "string"]),
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
        (TestState.do_something, "test_state.do_something"),
        (ChildState.change_both, "test_state.child_state.change_both"),
        (
            GrandchildState.do_nothing,
            "test_state.child_state.grandchild_state.do_nothing",
        ),
    ],
)
def test_format_event_handler(input, output):
    """Test formatting an event handler.

    Args:
        input: The event handler input.
        output: The expected output.
    """
    assert format.format_event_handler(input) == output  # type: ignore


@pytest.mark.parametrize(
    "input,output",
    [
        (EventSpec(handler=EventHandler(fn=mock_event)), 'Event("mock_event", {})'),
    ],
)
def test_format_event(input, output):
    assert format.format_event(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (
            EventChain(
                events=[
                    EventSpec(handler=EventHandler(fn=mock_event)),
                    EventSpec(handler=EventHandler(fn=mock_event)),
                ],
                args_spec=None,
            ),
            'addEvents([Event("mock_event", {}),Event("mock_event", {})])',
        ),
        (
            EventChain(
                events=[
                    EventSpec(handler=EventHandler(fn=mock_event)),
                    EventSpec(handler=EventHandler(fn=mock_event)),
                ],
                args_spec=lambda e0: [e0],
            ),
            'addEvents([Event("mock_event", {}),Event("mock_event", {})])',
        ),
    ],
)
def test_format_event_chain(input, output):
    assert format.format_event_chain(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ({"query": {"k1": 1, "k2": 2}}, {"k1": 1, "k2": 2}),
        ({"query": {"k1": 1, "k-2": 2}}, {"k1": 1, "k_2": 2}),
    ],
)
def test_format_query_params(input, output):
    assert format.format_query_params(input) == output


@pytest.mark.parametrize(
    "input, output",
    [
        (
            TestState().dict(),  # type: ignore
            {
                "array": [1, 2, 3.14],
                "child_state": {
                    "count": 23,
                    "grandchild_state": {"value2": ""},
                    "value": "",
                },
                "child_state2": {"value": ""},
                "complex": {
                    1: {"prop1": 42, "prop2": "hello"},
                    2: {"prop1": 42, "prop2": "hello"},
                },
                "dt": "1989-11-09 18:53:00+01:00",
                "fig": [],
                "is_hydrated": False,
                "key": "",
                "map_key": "a",
                "mapping": {"a": [1, 2, 3], "b": [4, 5, 6]},
                "num1": 0,
                "num2": 3.14,
                "obj": {"prop1": 42, "prop2": "hello"},
                "sum": 3.14,
                "upper": "",
            },
        ),
        (
            DateTimeState().dict(),
            {
                "d": "1989-11-09",
                "dt": "1989-11-09 18:53:00+01:00",
                "is_hydrated": False,
                "t": "18:53:00+01:00",
                "td": "11 days, 0:11:00",
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
    assert format.format_state(input) == output


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
        (("my_array", Var.create(0)), "refs_my_array[0]"),
        (("my_array", Var.create(1)), "refs_my_array[1]"),
    ],
)
def test_format_array_ref(input, output):
    assert format.format_array_ref(input[0], input[1]) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("/foo", [("foo", "/foo")]),
        ("/foo/bar", [("foo", "/foo"), ("bar", "/foo/bar")]),
        (
            "/foo/bar/baz",
            [("foo", "/foo"), ("bar", "/foo/bar"), ("baz", "/foo/bar/baz")],
        ),
    ],
)
def test_format_breadcrumbs(input, output):
    assert format.format_breadcrumbs(input) == output


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
    """Test formating a library name to remove the @version part.

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
    ],
)
def test_json_dumps(input, output):
    assert format.json_dumps(input) == output
