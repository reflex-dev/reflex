from contextlib import nullcontext
from typing import Any, ClassVar

import pytest

import reflex as rx
from reflex.base import Base
from reflex.compiler.utils import compile_custom_component
from reflex.components.base.bare import Bare
from reflex.components.base.fragment import Fragment
from reflex.components.component import (
    CUSTOM_COMPONENTS,
    Component,
    CustomComponent,
    StatefulComponent,
    custom_component,
)
from reflex.components.radix.themes.layout.box import Box
from reflex.constants import EventTriggers
from reflex.constants.state import FIELD_MARKER
from reflex.event import (
    EventChain,
    EventHandler,
    JavascriptInputEvent,
    input_event,
    no_args_event_spec,
    parse_args_spec,
    passthrough_event_spec,
)
from reflex.state import BaseState
from reflex.style import Style
from reflex.utils import imports
from reflex.utils.exceptions import (
    ChildrenTypeError,
    EventFnArgMismatchError,
    EventHandlerArgTypeMismatchError,
)
from reflex.utils.imports import ImportDict, ImportVar, ParsedImportDict, parse_imports
from reflex.vars import VarData
from reflex.vars.base import LiteralVar, Var
from reflex.vars.object import ObjectVar


@pytest.fixture
def test_state():
    class TestState(BaseState):
        num: int

        def do_something(self):
            pass

        def do_something_arg(self, arg):
            pass

        def do_something_with_bool(self, arg: bool):
            pass

        def do_something_with_int(self, arg: int):
            pass

        def do_something_with_list_int(self, arg: list[int]):
            pass

        def do_something_with_list_str(self, arg: list[str]):
            pass

        def do_something_required_optional(
            self, required_arg: int, optional_arg: int | None = None
        ):
            pass

    return TestState


@pytest.fixture
def component1() -> type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent1(Component):
        # A test string prop.
        text: Var[str]

        # A test number prop.
        number: Var[int]

        # A test string/number prop.
        text_or_number: Var[int | str]

        def _get_imports(self) -> ParsedImportDict:
            return {"react": [ImportVar(tag="Component")]}

        def _get_custom_code(self) -> str:
            return "console.log('component1')"

    return TestComponent1


@pytest.fixture
def component2() -> type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    def on_prop_event_spec(e0: Any):
        return [e0]

    class TestComponent2(Component):
        # A test list prop.
        arr: Var[list[str]]

        on_prop_event: EventHandler[on_prop_event_spec]

        @classmethod
        def get_event_triggers(cls) -> dict[str, Any]:
            """Test controlled triggers.

            Returns:
                Test controlled triggers.
            """
            return {
                **super().get_event_triggers(),
                "on_open": passthrough_event_spec(bool),
                "on_close": passthrough_event_spec(bool),
                "on_user_visited_count_changed": passthrough_event_spec(int),
                "on_two_args": passthrough_event_spec(int, int),
                "on_user_list_changed": passthrough_event_spec(list[str]),
            }

        def _get_imports(self) -> ParsedImportDict:
            return {"react-redux": [ImportVar(tag="connect")]}

        def _get_custom_code(self) -> str:
            return "console.log('component2')"

    return TestComponent2


@pytest.fixture
def component3() -> type[Component]:
    """A test component with hook defined.

    Returns:
        A test component.
    """

    class TestComponent3(Component):
        def _get_hooks(self) -> str:
            return "const a = () => true"

    return TestComponent3


@pytest.fixture
def component4() -> type[Component]:
    """A test component with hook defined.

    Returns:
        A test component.
    """

    class TestComponent4(Component):
        def _get_hooks(self) -> str:
            return "const b = () => false"

    return TestComponent4


@pytest.fixture
def component5() -> type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent5(Component):
        tag = "RandomComponent"

        _invalid_children: ClassVar[list[str]] = ["Text"]

        _valid_children: ClassVar[list[str]] = ["Text"]

        _valid_parents: ClassVar[list[str]] = ["Text"]

    return TestComponent5


@pytest.fixture
def component6() -> type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent6(Component):
        tag = "RandomComponent"

        _invalid_children: ClassVar[list[str]] = ["Text"]

    return TestComponent6


@pytest.fixture
def component7() -> type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent7(Component):
        tag = "RandomComponent"

        _valid_children: ClassVar[list[str]] = ["Text"]

    return TestComponent7


@pytest.fixture
def on_click1() -> EventHandler:
    """A sample on click function.

    Returns:
        A sample on click function.
    """

    def on_click1():
        pass

    return EventHandler(fn=on_click1)


@pytest.fixture
def on_click2() -> EventHandler:
    """A sample on click function.

    Returns:
        A sample on click function.
    """

    def on_click2():
        pass

    return EventHandler(fn=on_click2)


@pytest.fixture
def my_component():
    """A test component function.

    Returns:
        A test component function.
    """

    def my_component(prop1: Var[str], prop2: Var[int]):
        return Box.create(prop1, prop2)

    return my_component


def test_set_style_attrs(component1):
    """Test that style attributes are set in the dict.

    Args:
        component1: A test component.
    """
    component = component1.create(color="white", text_align="center")
    assert str(component.style["color"]) == '"white"'
    assert str(component.style["textAlign"]) == '"center"'


def test_custom_attrs(component1):
    """Test that custom attributes are set in the dict.

    Args:
        component1: A test component.
    """
    component = component1.create(custom_attrs={"attr1": "1", "attr2": "attr2"})
    assert component.custom_attrs == {"attr1": "1", "attr2": "attr2"}


def test_create_component(component1):
    """Test that the component is created correctly.

    Args:
        component1: A test component.
    """
    children = [component1.create() for _ in range(3)]
    attrs = {"color": "white", "text_align": "center"}
    c = component1.create(*children, **attrs)
    assert isinstance(c, component1)
    assert c.children == children
    assert (
        str(LiteralVar.create(c.style))
        == '({ ["color"] : "white", ["textAlign"] : "center" })'
    )


@pytest.mark.parametrize(
    ("prop_name", "var", "expected"),
    [
        pytest.param(
            "text",
            LiteralVar.create("hello"),
            None,
            id="text",
        ),
        pytest.param(
            "text",
            Var(_js_expr="hello", _var_type=str | None),
            None,
            id="text-optional",
        ),
        pytest.param(
            "text",
            Var(_js_expr="hello", _var_type=str | None),
            None,
            id="text-union-str-none",
        ),
        pytest.param(
            "text",
            Var(_js_expr="hello", _var_type=None | str),
            None,
            id="text-union-none-str",
        ),
        pytest.param(
            "text",
            LiteralVar.create(1),
            TypeError,
            id="text-int",
        ),
        pytest.param(
            "number",
            LiteralVar.create(1),
            None,
            id="number",
        ),
        pytest.param(
            "number",
            Var(_js_expr="1", _var_type=int | None),
            None,
            id="number-optional",
        ),
        pytest.param(
            "number",
            Var(_js_expr="1", _var_type=int | None),
            None,
            id="number-union-int-none",
        ),
        pytest.param(
            "number",
            Var(_js_expr="1", _var_type=None | int),
            None,
            id="number-union-none-int",
        ),
        pytest.param(
            "number",
            LiteralVar.create("1"),
            TypeError,
            id="number-str",
        ),
        pytest.param(
            "text_or_number",
            LiteralVar.create("hello"),
            None,
            id="text_or_number-str",
        ),
        pytest.param(
            "text_or_number",
            LiteralVar.create(1),
            None,
            id="text_or_number-int",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="hello", _var_type=str | None),
            None,
            id="text_or_number-optional-str",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="hello", _var_type=str | None),
            None,
            id="text_or_number-union-str-none",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="hello", _var_type=None | str),
            None,
            id="text_or_number-union-none-str",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="1", _var_type=int | None),
            None,
            id="text_or_number-optional-int",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="1", _var_type=int | None),
            None,
            id="text_or_number-union-int-none",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="1", _var_type=None | int),
            None,
            id="text_or_number-union-none-int",
        ),
        pytest.param(
            "text_or_number",
            LiteralVar.create(1.0),
            TypeError,
            id="text_or_number-float",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="hello", _var_type=str | int | None),
            None,
            id="text_or_number-optional-union-str-int",
        ),
    ],
)
def test_create_component_prop_validation(
    component1: type[Component],
    prop_name: str,
    var: Var | str | int,
    expected: type[Exception],
):
    """Test that component props are validated correctly.

    Args:
        component1: A test component.
        prop_name: The name of the prop.
        var: The value of the prop.
        expected: The expected exception.
    """
    ctx = pytest.raises(expected) if expected else nullcontext()
    kwargs = {prop_name: var}
    with ctx:
        c = component1.create(**kwargs)
        assert isinstance(c, component1)
        assert c.children == []
        assert c.style == {}


def test_add_style(component1, component2):
    """Test adding a style to a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    style = {
        component1: Style({"color": "white"}),
        component2: Style({"color": "black"}),
    }
    c1 = component1.create()._add_style_recursive(style)
    c2 = component2.create()._add_style_recursive(style)
    assert str(c1.style["color"]) == '"white"'
    assert str(c2.style["color"]) == '"black"'


def test_add_style_create(component1, component2):
    """Test that adding style works with the create method.

    Args:
        component1: A test component.
        component2: A test component.
    """
    style = {
        component1.create: Style({"color": "white"}),
        component2.create: Style({"color": "black"}),
    }
    c1 = component1.create()._add_style_recursive(style)
    c2 = component2.create()._add_style_recursive(style)
    assert str(c1.style["color"]) == '"white"'
    assert str(c2.style["color"]) == '"black"'


def test_get_imports(component1, component2):
    """Test getting the imports of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    c1 = component1.create()
    c2 = component2.create(c1)
    assert c1._get_all_imports() == {"react": [ImportVar(tag="Component")]}
    assert c2._get_all_imports() == {
        "react-redux": [ImportVar(tag="connect")],
        "react": [ImportVar(tag="Component")],
    }


def test_get_custom_code(component1: Component, component2: Component):
    """Test getting the custom code of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    # Check that the code gets compiled correctly.
    c1 = component1.create()
    c2 = component2.create()
    assert c1._get_all_custom_code() == {"console.log('component1')": None}
    assert c2._get_all_custom_code() == {"console.log('component2')": None}

    # Check that nesting components compiles both codes.
    c1 = component1.create(c2)
    assert c1._get_all_custom_code() == {
        "console.log('component1')": None,
        "console.log('component2')": None,
    }

    # Check that code is not duplicated.
    c1 = component1.create(c2, c2, c1, c1)
    assert c1._get_all_custom_code() == {
        "console.log('component1')": None,
        "console.log('component2')": None,
    }


def test_get_props(component1, component2):
    """Test that the props are set correctly.

    Args:
        component1: A test component.
        component2: A test component.
    """
    assert set(component1.get_props()) == {"text", "number", "text_or_number"}
    assert set(component2.get_props()) == {"arr", "on_prop_event"}


@pytest.mark.parametrize(
    ("text", "number"),
    [
        ("", 0),
        ("test", 1),
        ("hi", -13),
    ],
)
def test_valid_props(component1, text: str, number: int):
    """Test that we can construct a component with valid props.

    Args:
        component1: A test component.
        text: A test string.
        number: A test number.
    """
    c = component1.create(text=text, number=number)
    assert c.text._decode() == text
    assert c.number._decode() == number


@pytest.mark.parametrize(
    ("text", "number"), [("", "bad_string"), (13, 1), ("test", [1, 2, 3])]
)
def test_invalid_prop_type(component1, text: str, number: int):
    """Test that an invalid prop type raises an error.

    Args:
        component1: A test component.
        text: A test string.
        number: A test number.
    """
    # Check that
    with pytest.raises(TypeError):
        component1.create(text=text, number=number)


def test_var_props(component1, test_state):
    """Test that we can set a Var prop.

    Args:
        component1: A test component.
        test_state: A test state.
    """
    c1 = component1.create(text="hello", number=test_state.num)
    assert c1.number.equals(test_state.num)


def test_get_event_triggers(component1, component2):
    """Test that we can get the triggers of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    default_triggers = {
        EventTriggers.ON_FOCUS,
        EventTriggers.ON_BLUR,
        EventTriggers.ON_CLICK,
        EventTriggers.ON_CONTEXT_MENU,
        EventTriggers.ON_DOUBLE_CLICK,
        EventTriggers.ON_MOUSE_DOWN,
        EventTriggers.ON_MOUSE_ENTER,
        EventTriggers.ON_MOUSE_LEAVE,
        EventTriggers.ON_MOUSE_MOVE,
        EventTriggers.ON_MOUSE_OUT,
        EventTriggers.ON_MOUSE_OVER,
        EventTriggers.ON_MOUSE_UP,
        EventTriggers.ON_SCROLL,
        EventTriggers.ON_SCROLL_END,
        EventTriggers.ON_MOUNT,
        EventTriggers.ON_UNMOUNT,
    }
    assert component1.create().get_event_triggers().keys() == default_triggers
    assert (
        component2.create().get_event_triggers().keys()
        == {
            "on_open",
            "on_close",
            "on_prop_event",
            "on_user_visited_count_changed",
            "on_two_args",
            "on_user_list_changed",
        }
        | default_triggers
    )


@pytest.fixture
def test_component() -> type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent(Component):
        pass

    return TestComponent


# Write a test case to check if the create method filters out None props
def test_create_filters_none_props(test_component):
    child1 = test_component.create()
    child2 = test_component.create()
    props = {
        "prop1": "value1",
        "prop2": None,
        "prop3": "value3",
        "prop4": None,
        "style": {"color": "white", "text-align": "center"},  # Adding a style prop
    }

    component = test_component.create(child1, child2, **props)

    # Assert that None props are not present in the component's props
    assert "prop2" not in component.get_props()
    assert "prop4" not in component.get_props()

    # Assert that the style prop is present in the component's props
    assert str(component.style["color"]) == '"white"'
    assert str(component.style["textAlign"]) == '"center"'


@pytest.mark.parametrize(
    "children",
    [
        ({"foo": "bar"},),
    ],
)
def test_component_create_unallowed_types(children, test_component):
    with pytest.raises(ChildrenTypeError):
        test_component.create(*children)


@pytest.mark.parametrize(
    ("element", "expected"),
    [
        (
            (rx.text("first_text"),),
            {
                "name": "Fragment",
                "props": [],
                "children": [
                    {
                        "name": "RadixThemesText",
                        "props": ['as:"p"'],
                        "children": [
                            {
                                "contents": '"first_text"',
                            }
                        ],
                    }
                ],
            },
        ),
        (
            (rx.text("first_text"), rx.text("second_text")),
            {
                "children": [
                    {
                        "children": [
                            {
                                "contents": '"first_text"',
                            }
                        ],
                        "name": "RadixThemesText",
                        "props": ['as:"p"'],
                    },
                    {
                        "children": [
                            {
                                "contents": '"second_text"',
                            }
                        ],
                        "name": "RadixThemesText",
                        "props": ['as:"p"'],
                    },
                ],
                "name": "Fragment",
                "props": [],
            },
        ),
        (
            (rx.text("first_text"), rx.box((rx.text("second_text"),))),
            {
                "children": [
                    {
                        "children": [
                            {
                                "contents": '"first_text"',
                            }
                        ],
                        "name": "RadixThemesText",
                        "props": ['as:"p"'],
                    },
                    {
                        "children": [
                            {
                                "children": [
                                    {
                                        "children": [
                                            {
                                                "contents": '"second_text"',
                                            }
                                        ],
                                        "name": "RadixThemesText",
                                        "props": ['as:"p"'],
                                    }
                                ],
                                "name": "Fragment",
                                "props": [],
                            }
                        ],
                        "name": "RadixThemesBox",
                        "props": [],
                    },
                ],
                "name": "Fragment",
                "props": [],
            },
        ),
    ],
)
def test_component_create_unpack_tuple_child(test_component, element, expected):
    """Test that component in tuples are unwrapped into an rx.Fragment.

    Args:
        test_component: Component fixture.
        element: The children to pass to the component.
        expected: The expected render dict.
    """
    comp = test_component.create(element)

    assert len(comp.children) == 1
    fragment_wrapper = comp.children[0]
    assert isinstance(fragment_wrapper, Fragment)
    assert fragment_wrapper.render() == expected


class _Obj(Base):
    custom: int = 0


class C1State(BaseState):
    """State for testing C1 component."""

    def mock_handler(self, _e: JavascriptInputEvent, _bravo: dict, _charlie: _Obj):
        """Mock handler."""


def test_component_event_trigger_arbitrary_args():
    """Test that we can define arbitrary types for the args of an event trigger."""

    def on_foo_spec(
        _e: ObjectVar[JavascriptInputEvent],
        alpha: Var[str],
        bravo: dict[str, Any],
        charlie: ObjectVar[_Obj],
    ):
        return [_e.target.value, bravo["nested"], charlie.custom.to(int) + 42]

    class C1(Component):
        library = "/local"
        tag = "C1"

        @classmethod
        def get_event_triggers(cls) -> dict[str, Any]:
            return {
                **super().get_event_triggers(),
                "on_foo": on_foo_spec,
            }

    C1.create(on_foo=C1State.mock_handler)


def test_create_custom_component(my_component):
    """Test that we can create a custom component.

    Args:
        my_component: A test custom component.
    """
    component = rx.memo(my_component)(prop1="test", prop2=1)
    assert component.tag == "MyComponent"
    assert set(component.get_props()) == {"prop1", "prop2"}
    assert component.tag in CUSTOM_COMPONENTS


def test_custom_component_hash(my_component):
    """Test that the hash of a custom component is correct.

    Args:
        my_component: A test custom component.
    """
    component1 = rx.memo(my_component)(prop1="test", prop2=1)
    component2 = rx.memo(my_component)(prop1="test", prop2=2)
    assert {component1, component2} == {component1}


def test_custom_component_wrapper():
    """Test that the wrapper of a custom component is correct."""

    @custom_component
    def my_component(width: Var[int], color: Var[str]):
        return rx.box(
            width=width,
            color=color,
        )

    from reflex.components.radix.themes.typography.text import Text

    ccomponent = my_component(
        rx.text("child"), width=LiteralVar.create(1), color=LiteralVar.create("red")
    )
    assert isinstance(ccomponent, CustomComponent)
    assert len(ccomponent.children) == 1
    assert isinstance(ccomponent.children[0], Text)

    component = ccomponent.get_component()
    assert isinstance(component, Box)


def test_invalid_event_handler_args(component2, test_state):
    """Test that an invalid event handler raises an error.

    Args:
        component2: A test component.
        test_state: A test state.
    """
    # EventHandler args must match
    with pytest.raises(EventFnArgMismatchError):
        component2.create(on_blur=test_state.do_something_arg)

    # EventHandler args must have at least as many default args as the spec.
    with pytest.raises(EventFnArgMismatchError):
        component2.create(on_blur=test_state.do_something_required_optional)

    # Multiple EventHandler args: all must match
    with pytest.raises(EventFnArgMismatchError):
        component2.create(
            on_blur=[test_state.do_something_arg, test_state.do_something]
        )

    # # Event Handler types must match
    with pytest.raises(EventHandlerArgTypeMismatchError):
        component2.create(
            on_user_visited_count_changed=test_state.do_something_with_bool
        )
    with pytest.raises(EventHandlerArgTypeMismatchError):
        component2.create(on_user_list_changed=test_state.do_something_with_int)
    with pytest.raises(EventHandlerArgTypeMismatchError):
        component2.create(on_user_list_changed=test_state.do_something_with_list_int)
    with pytest.raises(EventHandlerArgTypeMismatchError):
        component2.create(
            on_user_visited_count_changed=test_state.do_something_with_bool()
        )
    with pytest.raises(EventHandlerArgTypeMismatchError):
        component2.create(on_user_list_changed=test_state.do_something_with_int())
    with pytest.raises(EventHandlerArgTypeMismatchError):
        component2.create(on_user_list_changed=test_state.do_something_with_list_int())

    component2.create(
        on_user_visited_count_changed=test_state.do_something_with_bool(False)
    )
    component2.create(on_user_list_changed=test_state.do_something_with_int(23))
    component2.create(
        on_user_list_changed=test_state.do_something_with_list_int([2321, 321])
    )

    component2.create(on_open=test_state.do_something_with_int)
    component2.create(on_open=test_state.do_something_with_bool)
    component2.create(on_user_visited_count_changed=test_state.do_something_with_int)
    component2.create(on_user_list_changed=test_state.do_something_with_list_str)

    # lambda cannot return weird values.
    with pytest.raises(ValueError):
        component2.create(on_blur=lambda: 1)
    with pytest.raises(ValueError):
        component2.create(on_blur=lambda: [1])
    with pytest.raises(ValueError):
        component2.create(
            on_blur=lambda: (test_state.do_something_arg(1), test_state.do_something)
        )

    # lambda signature must match event trigger.
    with pytest.raises(EventFnArgMismatchError):
        component2.create(on_blur=lambda _: test_state.do_something_arg(1))

    # lambda returning EventHandler must match spec
    with pytest.raises(EventFnArgMismatchError):
        component2.create(on_blur=lambda: test_state.do_something_arg)

    # Mixed EventSpec and EventHandler must match spec.
    with pytest.raises(EventFnArgMismatchError):
        component2.create(
            on_blur=lambda: [
                test_state.do_something_arg(1),
                test_state.do_something_arg,
            ]
        )


def test_valid_event_handler_args(component2, test_state):
    """Test that an valid event handler args do not raise exception.

    Args:
        component2: A test component.
        test_state: A test state.
    """
    # Uncontrolled event handlers should not take args.
    component2.create(on_blur=test_state.do_something)
    component2.create(on_blur=test_state.do_something_arg(1))

    # Does not raise because event handlers are allowed to have less args than the spec.
    component2.create(on_open=test_state.do_something)
    component2.create(on_prop_event=test_state.do_something)

    # Does not raise because event handlers can have optional args.
    component2.create(
        on_user_visited_count_changed=test_state.do_something_required_optional
    )
    component2.create(on_two_args=test_state.do_something_required_optional)

    # Controlled event handlers should take args.
    component2.create(on_open=test_state.do_something_arg)
    component2.create(on_prop_event=test_state.do_something_arg)

    # Using a partial event spec bypasses arg validation (ignoring the args).
    component2.create(on_open=test_state.do_something())
    component2.create(on_prop_event=test_state.do_something())

    # Multiple EventHandler args: all must match
    component2.create(on_open=[test_state.do_something_arg, test_state.do_something])
    component2.create(
        on_prop_event=[test_state.do_something_arg, test_state.do_something]
    )

    # lambda returning EventHandler is okay if the spec matches.
    component2.create(on_blur=lambda: test_state.do_something)
    component2.create(on_open=lambda _: test_state.do_something_arg)
    component2.create(on_prop_event=lambda _: test_state.do_something_arg)
    component2.create(on_open=lambda: test_state.do_something)
    component2.create(on_prop_event=lambda: test_state.do_something)
    component2.create(on_open=lambda _: test_state.do_something)
    component2.create(on_prop_event=lambda _: test_state.do_something)

    # lambda can always return an EventSpec.
    component2.create(on_blur=lambda: test_state.do_something_arg(1))
    component2.create(on_open=lambda _: test_state.do_something_arg(1))
    component2.create(on_prop_event=lambda _: test_state.do_something_arg(1))

    # Return EventSpec and EventHandler (no arg).
    component2.create(
        on_blur=lambda: [test_state.do_something_arg(1), test_state.do_something]
    )
    component2.create(
        on_blur=lambda: [test_state.do_something_arg(1), test_state.do_something()]
    )

    # Return 2 EventSpec.
    component2.create(
        on_open=lambda _: [test_state.do_something_arg(1), test_state.do_something()]
    )
    component2.create(
        on_prop_event=lambda _: [
            test_state.do_something_arg(1),
            test_state.do_something(),
        ]
    )

    # Return EventHandler (1 arg) and EventSpec.
    component2.create(
        on_open=lambda _: [test_state.do_something_arg, test_state.do_something()]
    )
    component2.create(
        on_prop_event=lambda _: [test_state.do_something_arg, test_state.do_something()]
    )
    component2.create(
        on_open=lambda _: [test_state.do_something_arg(1), test_state.do_something]
    )
    component2.create(
        on_prop_event=lambda _: [
            test_state.do_something_arg(1),
            test_state.do_something,
        ]
    )


def test_get_hooks_nested(component1, component2, component3):
    """Test that a component returns hooks from child components.

    Args:
        component1: test component.
        component2: another component.
        component3: component with hooks defined.
    """
    c = component1.create(
        component2.create(arr=[]),
        component3.create(),
        component3.create(),
        component3.create(),
        text="a",
        number=1,
    )
    assert c._get_all_hooks() == component3.create()._get_all_hooks()


def test_get_hooks_nested2(component3, component4):
    """Test that a component returns both when parent and child have hooks.

    Args:
        component3: component with hooks defined.
        component4: component with different hooks defined.
    """
    exp_hooks = {
        **component3.create()._get_all_hooks(),
        **component4.create()._get_all_hooks(),
    }
    assert component3.create(component4.create())._get_all_hooks() == exp_hooks
    assert component4.create(component3.create())._get_all_hooks() == exp_hooks
    assert (
        component4.create(
            component3.create(),
            component4.create(),
            component3.create(),
        )._get_all_hooks()
        == exp_hooks
    )


@pytest.mark.parametrize("fixture", ["component5", "component6"])
def test_unsupported_child_components(fixture, request):
    """Test that a value error is raised when an unsupported component (a child component found in the
    component's invalid children list) is provided as a child.

    Args:
        fixture: the test component as a fixture.
        request: Pytest request.
    """
    component = request.getfixturevalue(fixture)
    with pytest.raises(ValueError) as err:
        comp = component.create(rx.text("testing component"))
        comp.render()
    assert (
        err.value.args[0]
        == f"The component `{component.__name__}` cannot have `Text` as a child component"
    )


def test_unsupported_parent_components(component5):
    """Test that a value error is raised when an component is not in _valid_parents of one of its children.

    Args:
        component5: component with valid parent of "Text" only
    """
    with pytest.raises(ValueError) as err:
        rx.box(component5.create())
    assert (
        err.value.args[0]
        == f"The component `{component5.__name__}` can only be a child of the components: `{component5._valid_parents[0]}`. Got `Box` instead."
    )


@pytest.mark.parametrize("fixture", ["component5", "component7"])
def test_component_with_only_valid_children(fixture, request):
    """Test that a value error is raised when an unsupported component (a child component not found in the
    component's valid children list) is provided as a child.

    Args:
        fixture: the test component as a fixture.
        request: Pytest request.
    """
    component = request.getfixturevalue(fixture)
    with pytest.raises(ValueError) as err:
        comp = component.create(rx.box("testing component"))
        comp.render()
    assert (
        err.value.args[0]
        == f"The component `{component.__name__}` only allows the components: `Text` as children. "
        f"Got `Box` instead."
    )


@pytest.mark.parametrize(
    ("component", "rendered"),
    [
        (rx.text("hi"), 'jsx(RadixThemesText,{as:"p"},"hi")'),
        (
            rx.box(rx.heading("test", size="3")),
            'jsx(RadixThemesBox,{},jsx(RadixThemesHeading,{size:"3"},"test"))',
        ),
    ],
)
def test_format_component(component, rendered):
    """Test that a component is formatted correctly.

    Args:
        component: The component to format.
        rendered: The expected rendered component.
    """
    assert str(component) == rendered


def test_stateful_component(test_state):
    """Test that a stateful component is created correctly.

    Args:
        test_state: A test state.
    """
    text_component = rx.text(test_state.num)
    stateful_component = StatefulComponent.compile_from(text_component)
    assert isinstance(stateful_component, StatefulComponent)
    assert stateful_component.tag is not None
    assert stateful_component.tag.startswith("Text_")
    assert stateful_component.references == 1
    sc2 = StatefulComponent.compile_from(rx.text(test_state.num))
    assert isinstance(sc2, StatefulComponent)
    assert stateful_component.references == 2
    assert sc2.references == 2


def test_stateful_component_memoize_event_trigger(test_state):
    """Test that a stateful component is created correctly with events.

    Args:
        test_state: A test state.
    """
    button_component = rx.button("Click me", on_blur=test_state.do_something)
    stateful_component = StatefulComponent.compile_from(button_component)
    assert isinstance(stateful_component, StatefulComponent)

    # No event trigger? No StatefulComponent
    assert not isinstance(
        StatefulComponent.compile_from(rx.button("Click me")), StatefulComponent
    )


def test_stateful_banner():
    """Test that a stateful component is created correctly with events."""
    connection_modal_component = rx.connection_modal()
    stateful_component = StatefulComponent.compile_from(connection_modal_component)
    assert isinstance(stateful_component, StatefulComponent)


TEST_VAR = LiteralVar.create("p")._replace(
    merge_var_data=VarData(
        hooks={"useTest": None},
        imports={"test": [ImportVar(tag="p")]},
        state="Test",
    )
)
FORMATTED_TEST_VAR = LiteralVar.create(f"foo{TEST_VAR}bar")
STYLE_VAR = TEST_VAR._replace(_js_expr="style")
EVENT_CHAIN_VAR = TEST_VAR.to(EventChain)
ARG_VAR = Var(_js_expr="arg")

TEST_VAR_DICT_OF_DICT = LiteralVar.create({"a": {"b": "p"}})._replace(
    merge_var_data=TEST_VAR._var_data
)
FORMATTED_TEST_VAR_DICT_OF_DICT = LiteralVar.create({"a": {"b": "foopbar"}})._replace(
    merge_var_data=TEST_VAR._var_data
)

TEST_VAR_LIST_OF_LIST = LiteralVar.create([["p"]])._replace(
    merge_var_data=TEST_VAR._var_data
)
FORMATTED_TEST_VAR_LIST_OF_LIST = LiteralVar.create([["foopbar"]])._replace(
    merge_var_data=TEST_VAR._var_data
)

TEST_VAR_LIST_OF_LIST_OF_LIST = LiteralVar.create([[["p"]]])._replace(
    merge_var_data=TEST_VAR._var_data
)
FORMATTED_TEST_VAR_LIST_OF_LIST_OF_LIST = LiteralVar.create([[["foopbar"]]])._replace(
    merge_var_data=TEST_VAR._var_data
)

TEST_VAR_LIST_OF_DICT = LiteralVar.create([{"a": "p"}])._replace(
    merge_var_data=TEST_VAR._var_data
)
FORMATTED_TEST_VAR_LIST_OF_DICT = LiteralVar.create([{"a": "foopbar"}])._replace(
    merge_var_data=TEST_VAR._var_data
)


class ComponentNestedVar(Component):
    """A component with nested Var types."""

    dict_of_dict: Var[dict[str, dict[str, str]]]
    list_of_list: Var[list[list[str]]]
    list_of_list_of_list: Var[list[list[list[str]]]]
    list_of_dict: Var[list[dict[str, str]]]


class EventState(rx.State):
    """State for testing event handlers with _get_vars."""

    v: int = 42

    @rx.event
    def handler(self):
        """A handler that does nothing."""

    def handler2(self, arg):
        """A handler that takes an arg.

        Args:
            arg: An arg.
        """


@pytest.mark.parametrize(
    ("component", "exp_vars"),
    [
        pytest.param(
            Bare.create(TEST_VAR),
            [TEST_VAR],
            id="direct-bare",
        ),
        pytest.param(
            Bare.create(f"foo{TEST_VAR}bar"),
            [FORMATTED_TEST_VAR],
            id="fstring-bare",
        ),
        pytest.param(
            rx.text(as_=TEST_VAR),
            [TEST_VAR],
            id="direct-prop",
        ),
        pytest.param(
            rx.heading(as_=f"foo{TEST_VAR}bar"),
            [FORMATTED_TEST_VAR],
            id="fstring-prop",
        ),
        pytest.param(
            rx.fragment(id=TEST_VAR),
            [TEST_VAR],
            id="direct-id",
        ),
        pytest.param(
            rx.fragment(id=f"foo{TEST_VAR}bar"),
            [FORMATTED_TEST_VAR],
            id="fstring-id",
        ),
        pytest.param(
            rx.fragment(key=TEST_VAR),
            [TEST_VAR],
            id="direct-key",
        ),
        pytest.param(
            rx.fragment(key=f"foo{TEST_VAR}bar"),
            [FORMATTED_TEST_VAR],
            id="fstring-key",
        ),
        pytest.param(
            rx.fragment(class_name=TEST_VAR),
            [TEST_VAR],
            id="direct-class_name",
        ),
        pytest.param(
            rx.fragment(class_name=f"foo{TEST_VAR}bar"),
            [FORMATTED_TEST_VAR],
            id="fstring-class_name",
        ),
        pytest.param(
            rx.fragment(class_name=f"foo{TEST_VAR}bar other-class"),
            [LiteralVar.create(f"{FORMATTED_TEST_VAR} other-class")],
            id="fstring-dual-class_name",
        ),
        pytest.param(
            rx.fragment(class_name=[TEST_VAR, "other-class"]),
            [Var.create([TEST_VAR, "other-class"]).join(" ")],
            id="fstring-dual-class_name",
        ),
        pytest.param(
            rx.fragment(special_props=[TEST_VAR]),
            [TEST_VAR],
            id="direct-special_props",
        ),
        pytest.param(
            rx.fragment(special_props=[LiteralVar.create(f"foo{TEST_VAR}bar")]),
            [FORMATTED_TEST_VAR],
            id="fstring-special_props",
        ),
        pytest.param(
            # custom_attrs cannot accept a Var directly as a value
            rx.fragment(custom_attrs={"href": f"{TEST_VAR}"}),
            [TEST_VAR],
            id="fstring-custom_attrs-nofmt",
        ),
        pytest.param(
            rx.fragment(custom_attrs={"href": f"foo{TEST_VAR}bar"}),
            [FORMATTED_TEST_VAR],
            id="fstring-custom_attrs",
        ),
        pytest.param(
            rx.fragment(background_color=TEST_VAR),
            [STYLE_VAR],
            id="direct-background_color",
        ),
        pytest.param(
            rx.fragment(background_color=f"foo{TEST_VAR}bar"),
            [STYLE_VAR],
            id="fstring-background_color",
        ),
        pytest.param(
            rx.fragment(style={"background_color": TEST_VAR}),
            [STYLE_VAR],
            id="direct-style-background_color",
        ),
        pytest.param(
            rx.fragment(style={"background_color": f"foo{TEST_VAR}bar"}),
            [STYLE_VAR],
            id="fstring-style-background_color",
        ),
        pytest.param(
            rx.fragment(on_blur=EVENT_CHAIN_VAR),
            [EVENT_CHAIN_VAR],
            id="direct-event-chain",
        ),
        pytest.param(
            rx.fragment(on_blur=EventState.handler),
            [],
            id="direct-event-handler",
        ),
        pytest.param(
            rx.fragment(on_blur=EventState.handler2(TEST_VAR)),  # pyright: ignore [reportCallIssue]
            [ARG_VAR, TEST_VAR],
            id="direct-event-handler-arg",
        ),
        pytest.param(
            rx.fragment(on_blur=EventState.handler2(EventState.v)),  # pyright: ignore [reportCallIssue]
            [ARG_VAR, EventState.v],
            id="direct-event-handler-arg2",
        ),
        pytest.param(
            rx.fragment(on_blur=lambda: EventState.handler2(TEST_VAR)),  # pyright: ignore [reportCallIssue]
            [ARG_VAR, TEST_VAR],
            id="direct-event-handler-lambda",
        ),
        pytest.param(
            ComponentNestedVar.create(dict_of_dict={"a": {"b": TEST_VAR}}),
            [TEST_VAR_DICT_OF_DICT],
            id="direct-dict_of_dict",
        ),
        pytest.param(
            ComponentNestedVar.create(dict_of_dict={"a": {"b": f"foo{TEST_VAR}bar"}}),
            [FORMATTED_TEST_VAR_DICT_OF_DICT],
            id="fstring-dict_of_dict",
        ),
        pytest.param(
            ComponentNestedVar.create(list_of_list=[[TEST_VAR]]),
            [TEST_VAR_LIST_OF_LIST],
            id="direct-list_of_list",
        ),
        pytest.param(
            ComponentNestedVar.create(list_of_list=[[f"foo{TEST_VAR}bar"]]),
            [FORMATTED_TEST_VAR_LIST_OF_LIST],
            id="fstring-list_of_list",
        ),
        pytest.param(
            ComponentNestedVar.create(list_of_list_of_list=[[[TEST_VAR]]]),
            [TEST_VAR_LIST_OF_LIST_OF_LIST],
            id="direct-list_of_list_of_list",
        ),
        pytest.param(
            ComponentNestedVar.create(list_of_list_of_list=[[[f"foo{TEST_VAR}bar"]]]),
            [FORMATTED_TEST_VAR_LIST_OF_LIST_OF_LIST],
            id="fstring-list_of_list_of_list",
        ),
        pytest.param(
            ComponentNestedVar.create(list_of_dict=[{"a": TEST_VAR}]),
            [TEST_VAR_LIST_OF_DICT],
            id="direct-list_of_dict",
        ),
        pytest.param(
            ComponentNestedVar.create(list_of_dict=[{"a": f"foo{TEST_VAR}bar"}]),
            [FORMATTED_TEST_VAR_LIST_OF_DICT],
            id="fstring-list_of_dict",
        ),
    ],
)
def test_get_vars(component, exp_vars):
    comp_vars = sorted(component._get_vars(), key=lambda v: v._js_expr)
    assert len(comp_vars) == len(exp_vars)
    print(comp_vars, exp_vars)
    for comp_var, exp_var in zip(
        comp_vars,
        sorted(exp_vars, key=lambda v: v._js_expr),
        strict=True,
    ):
        assert comp_var.equals(exp_var)


def test_instantiate_all_components():
    """Test that all components can be instantiated."""
    # These components all have required arguments and cannot be trivially instantiated.
    untested_components = {
        "Card",
        "Cond",
        "DebounceInput",
        "Foreach",
        "FormControl",
        "Html",
        "Icon",
        "Match",
        "Markdown",
        "MultiSelect",
        "Option",
        "Popover",
        "Radio",
        "Script",
        "Tag",
        "Tfoot",
        "Thead",
    }
    component_nested_list = [
        *rx.RADIX_MAPPING.values(),
        *rx.COMPONENTS_BASE_MAPPING.values(),
        *rx.COMPONENTS_CORE_MAPPING.values(),
    ]
    for component_name in [
        comp_name
        for submodule_list in component_nested_list
        for comp_name in submodule_list
    ]:
        if component_name in untested_components:
            continue
        component = getattr(
            rx,
            (
                component_name
                if not isinstance(component_name, tuple)
                else component_name[1]
            ),
        )
        if isinstance(component, type) and issubclass(component, Component):
            component.create()


class InvalidParentComponent(Component):
    """Invalid Parent Component."""


class ValidComponent1(Component):
    """Test valid component."""

    _valid_children = ["ValidComponent2"]


class ValidComponent2(Component):
    """Test valid component."""


class ValidComponent3(Component):
    """Test valid component."""

    _valid_parents = ["ValidComponent2"]


class ValidComponent4(Component):
    """Test valid component."""

    _invalid_children = ["InvalidComponent"]


class InvalidComponent(Component):
    """Test invalid component."""


valid_component1 = ValidComponent1.create
valid_component2 = ValidComponent2.create
invalid_component = InvalidComponent.create
valid_component3 = ValidComponent3.create
invalid_parent = InvalidParentComponent.create
valid_component4 = ValidComponent4.create


def test_validate_valid_children():
    valid_component1(valid_component2())
    valid_component1(
        rx.fragment(valid_component2()),
    )
    valid_component1(
        rx.fragment(
            rx.fragment(
                rx.fragment(valid_component2()),
            ),
        ),
    )

    valid_component1(
        rx.cond(
            True,
            rx.fragment(valid_component2()),
            rx.fragment(
                rx.foreach(LiteralVar.create([1, 2, 3]), lambda x: valid_component2(x))
            ),
        )
    )

    valid_component1(
        rx.cond(
            True,
            valid_component2(),
            rx.fragment(
                rx.match(
                    "condition",
                    ("first", valid_component2()),
                    rx.fragment(valid_component2(rx.text("default"))),
                )
            ),
        )
    )

    valid_component1(
        rx.match(
            "condition",
            ("first", valid_component2()),
            ("second", "third", rx.fragment(valid_component2())),
            (
                "fourth",
                rx.cond(True, valid_component2(), rx.fragment(valid_component2())),
            ),
            (
                "fifth",
                "sixth",
                rx.match(
                    "nested_condition",
                    ("nested_first", valid_component2()),
                    rx.fragment(valid_component2()),
                ),
            ),
        )
    )


def test_validate_valid_parents():
    valid_component2(valid_component3())
    valid_component2(
        rx.fragment(valid_component3()),
    )
    valid_component1(
        rx.fragment(
            valid_component2(
                rx.fragment(valid_component3()),
            ),
        ),
    )

    valid_component2(
        rx.cond(
            True,
            rx.fragment(valid_component3()),
            rx.fragment(
                rx.foreach(
                    LiteralVar.create([1, 2, 3]),
                    lambda x: valid_component2(valid_component3(x)),
                )
            ),
        )
    )

    valid_component2(
        rx.cond(
            True,
            valid_component3(),
            rx.fragment(
                rx.match(
                    "condition",
                    ("first", valid_component3()),
                    rx.fragment(valid_component3(rx.text("default"))),
                )
            ),
        )
    )

    valid_component2(
        rx.match(
            "condition",
            ("first", valid_component3()),
            ("second", "third", rx.fragment(valid_component3())),
            (
                "fourth",
                rx.cond(True, valid_component3(), rx.fragment(valid_component3())),
            ),
            (
                "fifth",
                "sixth",
                rx.match(
                    "nested_condition",
                    ("nested_first", valid_component3()),
                    rx.fragment(valid_component3()),
                ),
            ),
        )
    )


def test_validate_invalid_children():
    with pytest.raises(ValueError):
        valid_component4(invalid_component())

    with pytest.raises(ValueError):
        valid_component4(
            rx.fragment(invalid_component()),
        )

    with pytest.raises(ValueError):
        rx.el.p(rx.el.p("what"))

    with pytest.raises(ValueError):
        rx.el.p(rx.el.div("what"))

    with pytest.raises(ValueError):
        rx.el.button(rx.el.button("what"))

    with pytest.raises(ValueError):
        rx.el.p(rx.el.ol(rx.el.li("what")))

    with pytest.raises(ValueError):
        rx.el.p(rx.el.ul(rx.el.li("what")))

    with pytest.raises(ValueError):
        rx.el.a(rx.el.a("what"))

    with pytest.raises(ValueError):
        valid_component2(
            rx.fragment(
                valid_component4(
                    rx.fragment(invalid_component()),
                ),
            ),
        )

    with pytest.raises(ValueError):
        valid_component4(
            rx.cond(
                True,
                rx.fragment(invalid_component()),
                rx.fragment(
                    rx.foreach(
                        LiteralVar.create([1, 2, 3]), lambda x: invalid_component(x)
                    )
                ),
            )
        )

    with pytest.raises(ValueError):
        valid_component4(
            rx.cond(
                True,
                invalid_component(),
                rx.fragment(
                    rx.match(
                        "condition",
                        ("first", invalid_component()),
                        rx.fragment(invalid_component(rx.text("default"))),
                    )
                ),
            )
        )

    with pytest.raises(ValueError):
        valid_component4(
            rx.match(
                "condition",
                ("first", invalid_component()),
                ("second", "third", rx.fragment(invalid_component())),
                (
                    "fourth",
                    rx.cond(True, invalid_component(), rx.fragment(valid_component2())),
                ),
                (
                    "fifth",
                    rx.match(
                        "nested_condition",
                        ("nested_first", invalid_component()),
                        rx.fragment(invalid_component()),
                    ),
                    invalid_component(),
                ),
            )
        )


def test_rename_props():
    """Test that _rename_props works and is inherited."""

    class C1(Component):
        tag = "C1"

        prop1: Var[str]
        prop2: Var[str]

        _rename_props = {"prop1": "renamed_prop1", "prop2": "renamed_prop2"}

    class C2(C1):
        tag = "C2"

        prop3: Var[str]

        _rename_props = {"prop2": "subclass_prop2", "prop3": "renamed_prop3"}

    c1 = C1.create(prop1="prop1_1", prop2="prop2_1")
    rendered_c1 = c1.render()
    assert 'renamed_prop1:"prop1_1"' in rendered_c1["props"]
    assert 'renamed_prop2:"prop2_1"' in rendered_c1["props"]

    c2 = C2.create(prop1="prop1_2", prop2="prop2_2", prop3="prop3_2")
    rendered_c2 = c2.render()
    assert 'renamed_prop1:"prop1_2"' in rendered_c2["props"]
    assert 'subclass_prop2:"prop2_2"' in rendered_c2["props"]
    assert 'renamed_prop3:"prop3_2"' in rendered_c2["props"]


def test_custom_component_get_imports():
    class Inner(Component):
        tag = "Inner"
        library = "inner"

    class Other(Component):
        tag = "Other"
        library = "other"

    @rx.memo
    def wrapper():
        return Inner.create()

    @rx.memo
    def outer(c: Component):
        return Other.create(c)

    custom_comp = wrapper()

    # Inner is not imported directly, but it is imported by the custom component.
    assert "inner" not in custom_comp._get_all_imports()
    assert "outer" not in custom_comp._get_all_imports()

    # The imports are only resolved during compilation.
    custom_comp.get_component()
    _, imports_inner = compile_custom_component(custom_comp)
    assert "inner" in imports_inner
    assert "outer" not in imports_inner

    outer_comp = outer(c=wrapper())

    # Libraries are not imported directly, but are imported by the custom component.
    assert "inner" not in outer_comp._get_all_imports()
    assert "other" not in outer_comp._get_all_imports()

    # The imports are only resolved during compilation.
    _, imports_outer = compile_custom_component(outer_comp)
    assert "inner" not in imports_outer
    assert "other" in imports_outer


def test_custom_component_declare_event_handlers_in_fields():
    class ReferenceComponent(Component):
        @classmethod
        def get_event_triggers(cls) -> dict[str, Any]:
            """Test controlled triggers.

            Returns:
                Test controlled triggers.
            """
            return {
                **super().get_event_triggers(),
                "on_b": input_event,
                "on_d": no_args_event_spec,
                "on_e": no_args_event_spec,
            }

    class TestComponent(Component):
        on_b: EventHandler[input_event]
        on_d: EventHandler[no_args_event_spec]
        on_e: EventHandler

    custom_component = ReferenceComponent.create()
    test_component = TestComponent.create()
    custom_triggers = custom_component.get_event_triggers()
    test_triggers = test_component.get_event_triggers()
    assert custom_triggers.keys() == test_triggers.keys()
    for trigger_name in custom_component.get_event_triggers():
        for v1, v2 in zip(
            parse_args_spec(test_triggers[trigger_name])[0],
            parse_args_spec(custom_triggers[trigger_name])[0],
            strict=True,
        ):
            assert v1.equals(v2)


def test_invalid_event_trigger():
    class TriggerComponent(Component):
        on_push: Var[bool]

        @classmethod
        def get_event_triggers(cls) -> dict[str, Any]:
            """Test controlled triggers.

            Returns:
                Test controlled triggers.
            """
            return {
                **super().get_event_triggers(),
                "on_a": no_args_event_spec,
            }

    trigger_comp = TriggerComponent.create

    # test that these do not throw errors.
    trigger_comp(on_push=True)
    trigger_comp(on_a=rx.console_log("log"))

    with pytest.raises(ValueError):
        trigger_comp(on_b=rx.console_log("log"))


@pytest.mark.parametrize(
    "tags",
    [
        ["Component"],
        ["Component", "useState"],
        [ImportVar(tag="Component")],
        [ImportVar(tag="Component"), ImportVar(tag="useState")],
        ["Component", ImportVar(tag="useState")],
    ],
)
def test_component_add_imports(tags):
    class BaseComponent(Component):
        def _get_imports(self) -> ImportDict:  # pyright: ignore [reportIncompatibleMethodOverride]
            return {}

    class Reference(Component):
        def _get_imports(self) -> ParsedImportDict:
            return imports.merge_imports(
                super()._get_imports(),
                parse_imports({"react": tags}),
                {"foo": [ImportVar(tag="bar")]},
            )

    class TestBase(Component):
        def add_imports(  # pyright: ignore [reportIncompatibleMethodOverride]
            self,
        ) -> dict[str, str | ImportVar | list[str] | list[ImportVar]]:
            return {"foo": "bar"}

    class Test(TestBase):
        def add_imports(
            self,
        ) -> dict[str, str | ImportVar | list[str] | list[ImportVar]]:
            return {"react": (tags[0] if len(tags) == 1 else tags)}

    baseline = Reference.create()
    test = Test.create()

    assert baseline._get_all_imports() == parse_imports(
        {
            "react": tags,
            "foo": [ImportVar(tag="bar")],
        }
    )
    assert test._get_all_imports() == baseline._get_all_imports()


def test_component_add_hooks():
    class BaseComponent(Component):
        def _get_hooks(self):
            return "const hook1 = 42"

    class ChildComponent1(BaseComponent):
        pass

    class GrandchildComponent1(ChildComponent1):
        def add_hooks(self):  # pyright: ignore [reportIncompatibleMethodOverride]
            return [
                "const hook2 = 43",
                "const hook3 = 44",
            ]

    class GreatGrandchildComponent1(GrandchildComponent1):
        def add_hooks(self):
            return [
                "const hook4 = 45",
            ]

    class GrandchildComponent2(ChildComponent1):
        def _get_hooks(self):  # pyright: ignore [reportIncompatibleMethodOverride]
            return "const hook5 = 46"

    class GreatGrandchildComponent2(GrandchildComponent2):
        def add_hooks(self):  # pyright: ignore [reportIncompatibleMethodOverride]
            return [
                "const hook2 = 43",
                "const hook6 = 47",
            ]

    assert list(BaseComponent.create()._get_all_hooks()) == ["const hook1 = 42"]
    assert list(ChildComponent1.create()._get_all_hooks()) == ["const hook1 = 42"]
    assert list(GrandchildComponent1.create()._get_all_hooks()) == [
        "const hook1 = 42",
        "const hook2 = 43",
        "const hook3 = 44",
    ]
    assert list(GreatGrandchildComponent1.create()._get_all_hooks()) == [
        "const hook1 = 42",
        "const hook2 = 43",
        "const hook3 = 44",
        "const hook4 = 45",
    ]
    assert list(GrandchildComponent2.create()._get_all_hooks()) == ["const hook5 = 46"]
    assert list(GreatGrandchildComponent2.create()._get_all_hooks()) == [
        "const hook5 = 46",
        "const hook2 = 43",
        "const hook6 = 47",
    ]
    assert list(
        BaseComponent.create(
            GrandchildComponent1.create(GreatGrandchildComponent2.create()),
            GreatGrandchildComponent1.create(),
        )._get_all_hooks(),
    ) == [
        "const hook1 = 42",
        "const hook2 = 43",
        "const hook3 = 44",
        "const hook5 = 46",
        "const hook6 = 47",
        "const hook4 = 45",
    ]
    assert list(
        Fragment.create(
            GreatGrandchildComponent2.create(),
            GreatGrandchildComponent1.create(),
        )._get_all_hooks()
    ) == [
        "const hook5 = 46",
        "const hook2 = 43",
        "const hook6 = 47",
        "const hook1 = 42",
        "const hook3 = 44",
        "const hook4 = 45",
    ]


def test_component_add_custom_code():
    class BaseComponent(Component):
        def _get_custom_code(self):
            return "const custom_code1 = 42"

    class ChildComponent1(BaseComponent):
        pass

    class GrandchildComponent1(ChildComponent1):
        def add_custom_code(self):
            return [
                "const custom_code2 = 43",
                "const custom_code3 = 44",
            ]

    class GreatGrandchildComponent1(GrandchildComponent1):
        def add_custom_code(self):
            return [
                "const custom_code4 = 45",
            ]

    class GrandchildComponent2(ChildComponent1):
        def _get_custom_code(self):  # pyright: ignore [reportIncompatibleMethodOverride]
            return "const custom_code5 = 46"

    class GreatGrandchildComponent2(GrandchildComponent2):
        def add_custom_code(self):
            return [
                "const custom_code2 = 43",
                "const custom_code6 = 47",
            ]

    assert BaseComponent.create()._get_all_custom_code() == {
        "const custom_code1 = 42": None
    }
    assert ChildComponent1.create()._get_all_custom_code() == {
        "const custom_code1 = 42": None
    }
    assert GrandchildComponent1.create()._get_all_custom_code() == {
        "const custom_code1 = 42": None,
        "const custom_code2 = 43": None,
        "const custom_code3 = 44": None,
    }
    assert GreatGrandchildComponent1.create()._get_all_custom_code() == {
        "const custom_code1 = 42": None,
        "const custom_code2 = 43": None,
        "const custom_code3 = 44": None,
        "const custom_code4 = 45": None,
    }
    assert GrandchildComponent2.create()._get_all_custom_code() == {
        "const custom_code5 = 46": None
    }
    assert GreatGrandchildComponent2.create()._get_all_custom_code() == {
        "const custom_code2 = 43": None,
        "const custom_code5 = 46": None,
        "const custom_code6 = 47": None,
    }
    assert BaseComponent.create(
        GrandchildComponent1.create(GreatGrandchildComponent2.create()),
        GreatGrandchildComponent1.create(),
    )._get_all_custom_code() == {
        "const custom_code1 = 42": None,
        "const custom_code2 = 43": None,
        "const custom_code3 = 44": None,
        "const custom_code4 = 45": None,
        "const custom_code5 = 46": None,
        "const custom_code6 = 47": None,
    }
    assert Fragment.create(
        GreatGrandchildComponent2.create(),
        GreatGrandchildComponent1.create(),
    )._get_all_custom_code() == {
        "const custom_code1 = 42": None,
        "const custom_code2 = 43": None,
        "const custom_code3 = 44": None,
        "const custom_code4 = 45": None,
        "const custom_code5 = 46": None,
        "const custom_code6 = 47": None,
    }


def test_component_add_hooks_var():
    class HookComponent(Component):
        def add_hooks(self):
            return [
                "const hook3 = useRef(null)",
                "const hook1 = 42",
                Var(
                    _js_expr="useEffect(() => () => {}, [])",
                    _var_data=VarData(
                        hooks={
                            "const hook2 = 43": None,
                            "const hook3 = useRef(null)": None,
                        },
                        imports={"react": [ImportVar(tag="useEffect")]},
                    ),
                ),
                Var(
                    _js_expr="const hook3 = useRef(null)",
                    _var_data=VarData(imports={"react": [ImportVar(tag="useRef")]}),
                ),
            ]

    assert list(HookComponent.create()._get_all_hooks()) == [
        "const hook3 = useRef(null)",
        "const hook1 = 42",
        "const hook2 = 43",
        "useEffect(() => () => {}, [])",
    ]
    imports = HookComponent.create()._get_all_imports()
    assert len(imports) == 1
    assert "react" in imports
    assert len(imports["react"]) == 2
    assert ImportVar(tag="useRef") in imports["react"]
    assert ImportVar(tag="useEffect") in imports["react"]


def test_add_style_embedded_vars(test_state: BaseState):
    """Test that add_style works with embedded vars when returning a plain dict.

    Args:
        test_state: A test state.
    """
    v0 = LiteralVar.create("parent")._replace(
        merge_var_data=VarData(hooks={"useParent": None}),
    )
    v1 = rx.color("plum", 10)
    v2 = LiteralVar.create("text")._replace(
        merge_var_data=VarData(hooks={"useText": None}),
    )

    class ParentComponent(Component):
        def add_style(self):
            return Style(
                {
                    "fake_parent": v0,
                }
            )

    class StyledComponent(ParentComponent):
        tag = "StyledComponent"

        def add_style(self):  # pyright: ignore [reportIncompatibleMethodOverride]
            return {
                "color": v1,
                "fake": v2,
                "margin": f"{test_state.num}%",
            }

    page = rx.vstack(StyledComponent.create())
    page._add_style_recursive(Style())

    assert (
        f"const {test_state.get_name()} = useContext(StateContexts.{test_state.get_name()})"
        in page._get_all_hooks_internal()
    )
    assert "useText" in page._get_all_hooks_internal()
    assert "useParent" in page._get_all_hooks_internal()
    str_page = str(page)
    assert (
        str_page.count(
            f'css:({{ ["fakeParent"] : "parent", ["color"] : (((__to_string) => __to_string.toString())(Object.assign(new String("var(--plum-10)"), ({{ ["color"] : "plum", ["alpha"] : false, ["shade"] : 10 }})))), ["fake"] : "text", ["margin"] : ({test_state.get_name()}.num{FIELD_MARKER}+"%") }})'
        )
        == 1
    )


def test_add_style_foreach():
    class StyledComponent(Component):
        tag = "StyledComponent"
        ix: Var[int]

        def add_style(self):
            return Style({"color": "red"})

    page = rx.vstack(rx.foreach(Var.range(3), lambda i: StyledComponent.create(i)))
    page._add_style_recursive(Style())

    # Expect only a single child of the foreach on the python side
    assert len(page.children[0].children) == 1

    # Expect the style to be added to the child of the foreach
    assert 'css:({ ["color"] : "red" })' in str(page.children[0].children[0])

    # Expect only one instance of this CSS dict in the rendered page
    assert str(page).count('css:({ ["color"] : "red" })') == 1


class TriggerState(rx.State):
    """Test state with event handlers."""

    @rx.event
    def do_something(self):
        """Sample event handler."""


@pytest.mark.parametrize(
    ("component", "output"),
    [
        (rx.box(rx.text("random text")), False),
        (
            rx.box(rx.text("random text", on_blur=rx.console_log("log"))),
            False,
        ),
        (
            rx.box(
                rx.text("random text", on_blur=TriggerState.do_something),
                rx.text(
                    "random text",
                    on_blur=Var(_js_expr="toggleColorMode").to(EventChain),
                ),
            ),
            True,
        ),
        (
            rx.box(
                rx.text("random text", on_blur=rx.console_log("log")),
                rx.text(
                    "random text",
                    on_blur=Var(_js_expr="toggleColorMode").to(EventChain),
                ),
            ),
            False,
        ),
        (
            rx.box(rx.text("random text", on_blur=TriggerState.do_something)),
            True,
        ),
        (
            rx.box(
                rx.text(
                    "random text",
                    on_blur=[rx.console_log("log"), rx.window_alert("alert")],
                ),
            ),
            False,
        ),
        (
            rx.box(
                rx.text(
                    "random text",
                    on_blur=[rx.console_log("log"), TriggerState.do_something],
                ),
            ),
            True,
        ),
        (
            rx.box(
                rx.text(
                    "random text",
                    on_blur=lambda: TriggerState.do_something,
                ),
            ),
            True,
        ),
    ],
)
def test_has_state_event_triggers(component, output):
    assert component._has_stateful_event_triggers() == output


class SpecialComponent(Box):
    """A special component with custom attributes."""

    data_prop: Var[str]
    aria_prop: Var[str]


@pytest.mark.parametrize(
    ("component_kwargs", "exp_custom_attrs", "exp_style"),
    [
        (
            {"data_test": "test", "aria_test": "test"},
            {"data-test": "test", "aria-test": "test"},
            {},
        ),
        (
            {"data-test": "test", "aria-test": "test"},
            {"data-test": "test", "aria-test": "test"},
            {},
        ),
        (
            {"custom_attrs": {"data-existing": "test"}, "data_new": "test"},
            {"data-existing": "test", "data-new": "test"},
            {},
        ),
        (
            {"data_test": "test", "data_prop": "prop"},
            {"data-test": "test"},
            {},
        ),
        (
            {"aria_test": "test", "aria_prop": "prop"},
            {"aria-test": "test"},
            {},
        ),
    ],
)
def test_special_props(component_kwargs, exp_custom_attrs, exp_style):
    """Test that data_ and aria_ special props are correctly added to the component.

    Args:
        component_kwargs: The component kwargs.
        exp_custom_attrs: The expected custom attributes.
        exp_style: The expected style.
    """
    component = SpecialComponent.create(**component_kwargs)
    assert component.custom_attrs == exp_custom_attrs
    assert component.style == exp_style
    for prop in SpecialComponent.get_props():
        if prop in component_kwargs:
            assert getattr(component, prop)._var_value == component_kwargs[prop]


def test_ref():
    """Test that the ref prop is correctly added to the component."""
    custom_ref = Var("custom_ref")
    ref_component = rx.box(ref=custom_ref)
    assert ref_component._render().props["ref"].equals(custom_ref)

    id_component = rx.box(id="custom_id")
    assert id_component._render().props["ref"].equals(Var("ref_custom_id"))

    assert "ref" not in rx.box()._render().props
