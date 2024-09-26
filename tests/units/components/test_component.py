from contextlib import nullcontext
from typing import Any, Dict, List, Optional, Type, Union

import pytest

import reflex as rx
from reflex.base import Base
from reflex.compiler.compiler import compile_components
from reflex.components.base.bare import Bare
from reflex.components.base.fragment import Fragment
from reflex.components.component import (
    Component,
    CustomComponent,
    StatefulComponent,
    custom_component,
)
from reflex.components.radix.themes.layout.box import Box
from reflex.constants import EventTriggers
from reflex.event import EventChain, EventHandler, parse_args_spec
from reflex.state import BaseState
from reflex.style import Style
from reflex.utils import imports
from reflex.utils.exceptions import EventFnArgMismatch, EventHandlerArgMismatch
from reflex.utils.imports import ImportDict, ImportVar, ParsedImportDict, parse_imports
from reflex.vars import VarData
from reflex.vars.base import LiteralVar, Var


@pytest.fixture
def test_state():
    class TestState(BaseState):
        num: int

        def do_something(self):
            pass

        def do_something_arg(self, arg):
            pass

    return TestState


@pytest.fixture
def component1() -> Type[Component]:
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
        text_or_number: Var[Union[int, str]]

        def _get_imports(self) -> ParsedImportDict:
            return {"react": [ImportVar(tag="Component")]}

        def _get_custom_code(self) -> str:
            return "console.log('component1')"

    return TestComponent1


@pytest.fixture
def component2() -> Type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent2(Component):
        # A test list prop.
        arr: Var[List[str]]

        on_prop_event: EventHandler[lambda e0: [e0]]

        def get_event_triggers(self) -> Dict[str, Any]:
            """Test controlled triggers.

            Returns:
                Test controlled triggers.
            """
            return {
                **super().get_event_triggers(),
                "on_open": lambda e0: [e0],
                "on_close": lambda e0: [e0],
            }

        def _get_imports(self) -> ParsedImportDict:
            return {"react-redux": [ImportVar(tag="connect")]}

        def _get_custom_code(self) -> str:
            return "console.log('component2')"

    return TestComponent2


@pytest.fixture
def component3() -> Type[Component]:
    """A test component with hook defined.

    Returns:
        A test component.
    """

    class TestComponent3(Component):
        def _get_hooks(self) -> str:
            return "const a = () => true"

    return TestComponent3


@pytest.fixture
def component4() -> Type[Component]:
    """A test component with hook defined.

    Returns:
        A test component.
    """

    class TestComponent4(Component):
        def _get_hooks(self) -> str:
            return "const b = () => false"

    return TestComponent4


@pytest.fixture
def component5() -> Type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent5(Component):
        tag = "RandomComponent"

        _invalid_children: List[str] = ["Text"]

        _valid_children: List[str] = ["Text"]

        _valid_parents: List[str] = ["Text"]

    return TestComponent5


@pytest.fixture
def component6() -> Type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent6(Component):
        tag = "RandomComponent"

        _invalid_children: List[str] = ["Text"]

    return TestComponent6


@pytest.fixture
def component7() -> Type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent7(Component):
        tag = "RandomComponent"

        _valid_children: List[str] = ["Text"]

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
    component = component1(color="white", text_align="center")
    assert str(component.style["color"]) == '"white"'
    assert str(component.style["textAlign"]) == '"center"'


def test_custom_attrs(component1):
    """Test that custom attributes are set in the dict.

    Args:
        component1: A test component.
    """
    component = component1(custom_attrs={"attr1": "1", "attr2": "attr2"})
    assert component.custom_attrs == {"attr1": "1", "attr2": "attr2"}


def test_create_component(component1):
    """Test that the component is created correctly.

    Args:
        component1: A test component.
    """
    children = [component1() for _ in range(3)]
    attrs = {"color": "white", "text_align": "center"}
    c = component1.create(*children, **attrs)
    assert isinstance(c, component1)
    assert c.children == children
    assert (
        str(LiteralVar.create(c.style))
        == '({ ["color"] : "white", ["textAlign"] : "center" })'
    )


@pytest.mark.parametrize(
    "prop_name,var,expected",
    [
        pytest.param(
            "text",
            LiteralVar.create("hello"),
            None,
            id="text",
        ),
        pytest.param(
            "text",
            Var(_js_expr="hello", _var_type=Optional[str]),
            None,
            id="text-optional",
        ),
        pytest.param(
            "text",
            Var(_js_expr="hello", _var_type=Union[str, None]),
            None,
            id="text-union-str-none",
        ),
        pytest.param(
            "text",
            Var(_js_expr="hello", _var_type=Union[None, str]),
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
            Var(_js_expr="1", _var_type=Optional[int]),
            None,
            id="number-optional",
        ),
        pytest.param(
            "number",
            Var(_js_expr="1", _var_type=Union[int, None]),
            None,
            id="number-union-int-none",
        ),
        pytest.param(
            "number",
            Var(_js_expr="1", _var_type=Union[None, int]),
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
            Var(_js_expr="hello", _var_type=Optional[str]),
            None,
            id="text_or_number-optional-str",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="hello", _var_type=Union[str, None]),
            None,
            id="text_or_number-union-str-none",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="hello", _var_type=Union[None, str]),
            None,
            id="text_or_number-union-none-str",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="1", _var_type=Optional[int]),
            None,
            id="text_or_number-optional-int",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="1", _var_type=Union[int, None]),
            None,
            id="text_or_number-union-int-none",
        ),
        pytest.param(
            "text_or_number",
            Var(_js_expr="1", _var_type=Union[None, int]),
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
            Var(_js_expr="hello", _var_type=Optional[Union[str, int]]),
            None,
            id="text_or_number-optional-union-str-int",
        ),
    ],
)
def test_create_component_prop_validation(
    component1: Type[Component],
    prop_name: str,
    var: Union[Var, str, int],
    expected: Type[Exception],
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
    c1 = component1()._add_style_recursive(style)  # type: ignore
    c2 = component2()._add_style_recursive(style)  # type: ignore
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
    c1 = component1()._add_style_recursive(style)  # type: ignore
    c2 = component2()._add_style_recursive(style)  # type: ignore
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


def test_get_custom_code(component1, component2):
    """Test getting the custom code of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    # Check that the code gets compiled correctly.
    c1 = component1.create()
    c2 = component2.create()
    assert c1._get_all_custom_code() == {"console.log('component1')"}
    assert c2._get_all_custom_code() == {"console.log('component2')"}

    # Check that nesting components compiles both codes.
    c1 = component1.create(c2)
    assert c1._get_all_custom_code() == {
        "console.log('component1')",
        "console.log('component2')",
    }

    # Check that code is not duplicated.
    c1 = component1.create(c2, c2, c1, c1)
    assert c1._get_all_custom_code() == {
        "console.log('component1')",
        "console.log('component2')",
    }


def test_get_props(component1, component2):
    """Test that the props are set correctly.

    Args:
        component1: A test component.
        component2: A test component.
    """
    assert component1.get_props() == {"text", "number", "text_or_number"}
    assert component2.get_props() == {"arr", "on_prop_event"}


@pytest.mark.parametrize(
    "text,number",
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
    "text,number", [("", "bad_string"), (13, 1), ("test", [1, 2, 3])]
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
        EventTriggers.ON_MOUNT,
        EventTriggers.ON_UNMOUNT,
    }
    assert component1().get_event_triggers().keys() == default_triggers
    assert (
        component2().get_event_triggers().keys()
        == {"on_open", "on_close", "on_prop_event"} | default_triggers
    )


@pytest.fixture
def test_component() -> Type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent(Component):
        pass

    return TestComponent


# Write a test case to check if the create method filters out None props
def test_create_filters_none_props(test_component):
    child1 = test_component()
    child2 = test_component()
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
    assert str(component.style["text-align"]) == '"center"'


@pytest.mark.parametrize("children", [((None,),), ("foo", ("bar", (None,)))])
def test_component_create_unallowed_types(children, test_component):
    with pytest.raises(TypeError) as err:
        test_component.create(*children)
    assert (
        err.value.args[0]
        == "Children of Reflex components must be other components, state vars, or primitive Python types. Got child None of type <class 'NoneType'>."
    )


@pytest.mark.parametrize(
    "element, expected",
    [
        (
            (rx.text("first_text"),),
            {
                "name": "Fragment",
                "props": [],
                "contents": "",
                "args": None,
                "special_props": [],
                "children": [
                    {
                        "name": "RadixThemesText",
                        "props": ['as={"p"}'],
                        "contents": "",
                        "args": None,
                        "special_props": [],
                        "children": [
                            {
                                "name": "",
                                "props": [],
                                "contents": '{"first_text"}',
                                "args": None,
                                "special_props": [],
                                "children": [],
                                "autofocus": False,
                            }
                        ],
                        "autofocus": False,
                    }
                ],
                "autofocus": False,
            },
        ),
        (
            (rx.text("first_text"), rx.text("second_text")),
            {
                "args": None,
                "autofocus": False,
                "children": [
                    {
                        "args": None,
                        "autofocus": False,
                        "children": [
                            {
                                "args": None,
                                "autofocus": False,
                                "children": [],
                                "contents": '{"first_text"}',
                                "name": "",
                                "props": [],
                                "special_props": [],
                            }
                        ],
                        "contents": "",
                        "name": "RadixThemesText",
                        "props": ['as={"p"}'],
                        "special_props": [],
                    },
                    {
                        "args": None,
                        "autofocus": False,
                        "children": [
                            {
                                "args": None,
                                "autofocus": False,
                                "children": [],
                                "contents": '{"second_text"}',
                                "name": "",
                                "props": [],
                                "special_props": [],
                            }
                        ],
                        "contents": "",
                        "name": "RadixThemesText",
                        "props": ['as={"p"}'],
                        "special_props": [],
                    },
                ],
                "contents": "",
                "name": "Fragment",
                "props": [],
                "special_props": [],
            },
        ),
        (
            (rx.text("first_text"), rx.box((rx.text("second_text"),))),
            {
                "args": None,
                "autofocus": False,
                "children": [
                    {
                        "args": None,
                        "autofocus": False,
                        "children": [
                            {
                                "args": None,
                                "autofocus": False,
                                "children": [],
                                "contents": '{"first_text"}',
                                "name": "",
                                "props": [],
                                "special_props": [],
                            }
                        ],
                        "contents": "",
                        "name": "RadixThemesText",
                        "props": ['as={"p"}'],
                        "special_props": [],
                    },
                    {
                        "args": None,
                        "autofocus": False,
                        "children": [
                            {
                                "args": None,
                                "autofocus": False,
                                "children": [
                                    {
                                        "args": None,
                                        "autofocus": False,
                                        "children": [
                                            {
                                                "args": None,
                                                "autofocus": False,
                                                "children": [],
                                                "contents": '{"second_text"}',
                                                "name": "",
                                                "props": [],
                                                "special_props": [],
                                            }
                                        ],
                                        "contents": "",
                                        "name": "RadixThemesText",
                                        "props": ['as={"p"}'],
                                        "special_props": [],
                                    }
                                ],
                                "contents": "",
                                "name": "Fragment",
                                "props": [],
                                "special_props": [],
                            }
                        ],
                        "contents": "",
                        "name": "RadixThemesBox",
                        "props": [],
                        "special_props": [],
                    },
                ],
                "contents": "",
                "name": "Fragment",
                "props": [],
                "special_props": [],
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
    assert isinstance((fragment_wrapper := comp.children[0]), Fragment)
    assert fragment_wrapper.render() == expected


class C1State(BaseState):
    """State for testing C1 component."""

    def mock_handler(self, _e, _bravo, _charlie):
        """Mock handler."""
        pass


def test_component_event_trigger_arbitrary_args():
    """Test that we can define arbitrary types for the args of an event trigger."""

    class Obj(Base):
        custom: int = 0

    def on_foo_spec(_e, alpha: str, bravo: Dict[str, Any], charlie: Obj):
        return [_e.target.value, bravo["nested"], charlie.custom + 42]

    class C1(Component):
        library = "/local"
        tag = "C1"

        def get_event_triggers(self) -> Dict[str, Any]:
            return {
                **super().get_event_triggers(),
                "on_foo": on_foo_spec,
            }

    comp = C1.create(on_foo=C1State.mock_handler)

    assert comp.render()["props"][0] == (
        "onFoo={((__e, _alpha, _bravo, _charlie) => ((addEvents("
        f'[(Event("{C1State.get_full_name()}.mock_handler", ({{ ["_e"] : __e["target"]["value"], ["_bravo"] : _bravo["nested"], ["_charlie"] : (_charlie["custom"] + 42) }})))], '
        "[__e, _alpha, _bravo, _charlie], ({  })))))}"
    )


def test_create_custom_component(my_component):
    """Test that we can create a custom component.

    Args:
        my_component: A test custom component.
    """
    component = CustomComponent(component_fn=my_component, prop1="test", prop2=1)
    assert component.tag == "MyComponent"
    assert component.get_props() == set()
    assert component._get_all_custom_components() == {component}


def test_custom_component_hash(my_component):
    """Test that the hash of a custom component is correct.

    Args:
        my_component: A test custom component.
    """
    component1 = CustomComponent(component_fn=my_component, prop1="test", prop2=1)
    component2 = CustomComponent(component_fn=my_component, prop1="test", prop2=2)
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

    component = ccomponent.get_component(ccomponent)
    assert isinstance(component, Box)


def test_invalid_event_handler_args(component2, test_state):
    """Test that an invalid event handler raises an error.

    Args:
        component2: A test component.
        test_state: A test state.
    """
    # EventHandler args must match
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(on_click=test_state.do_something_arg)
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(on_open=test_state.do_something)
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(on_prop_event=test_state.do_something)

    # Multiple EventHandler args: all must match
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(
            on_click=[test_state.do_something_arg, test_state.do_something]
        )
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(
            on_open=[test_state.do_something_arg, test_state.do_something]
        )
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(
            on_prop_event=[test_state.do_something_arg, test_state.do_something]
        )

    # lambda cannot return weird values.
    with pytest.raises(ValueError):
        component2.create(on_click=lambda: 1)
    with pytest.raises(ValueError):
        component2.create(on_click=lambda: [1])
    with pytest.raises(ValueError):
        component2.create(
            on_click=lambda: (test_state.do_something_arg(1), test_state.do_something)
        )

    # lambda signature must match event trigger.
    with pytest.raises(EventFnArgMismatch):
        component2.create(on_click=lambda _: test_state.do_something_arg(1))
    with pytest.raises(EventFnArgMismatch):
        component2.create(on_open=lambda: test_state.do_something)
    with pytest.raises(EventFnArgMismatch):
        component2.create(on_prop_event=lambda: test_state.do_something)

    # lambda returning EventHandler must match spec
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(on_click=lambda: test_state.do_something_arg)
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(on_open=lambda _: test_state.do_something)
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(on_prop_event=lambda _: test_state.do_something)

    # Mixed EventSpec and EventHandler must match spec.
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(
            on_click=lambda: [
                test_state.do_something_arg(1),
                test_state.do_something_arg,
            ]
        )
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(
            on_open=lambda _: [test_state.do_something_arg(1), test_state.do_something]
        )
    with pytest.raises(EventHandlerArgMismatch):
        component2.create(
            on_prop_event=lambda _: [
                test_state.do_something_arg(1),
                test_state.do_something,
            ]
        )


def test_valid_event_handler_args(component2, test_state):
    """Test that an valid event handler args do not raise exception.

    Args:
        component2: A test component.
        test_state: A test state.
    """
    # Uncontrolled event handlers should not take args.
    component2.create(on_click=test_state.do_something)
    component2.create(on_click=test_state.do_something_arg(1))

    # Controlled event handlers should take args.
    component2.create(on_open=test_state.do_something_arg)
    component2.create(on_prop_event=test_state.do_something_arg)

    # Using a partial event spec bypasses arg validation (ignoring the args).
    component2.create(on_open=test_state.do_something())
    component2.create(on_prop_event=test_state.do_something())

    # lambda returning EventHandler is okay if the spec matches.
    component2.create(on_click=lambda: test_state.do_something)
    component2.create(on_open=lambda _: test_state.do_something_arg)
    component2.create(on_prop_event=lambda _: test_state.do_something_arg)

    # lambda can always return an EventSpec.
    component2.create(on_click=lambda: test_state.do_something_arg(1))
    component2.create(on_open=lambda _: test_state.do_something_arg(1))
    component2.create(on_prop_event=lambda _: test_state.do_something_arg(1))

    # Return EventSpec and EventHandler (no arg).
    component2.create(
        on_click=lambda: [test_state.do_something_arg(1), test_state.do_something]
    )
    component2.create(
        on_click=lambda: [test_state.do_something_arg(1), test_state.do_something()]
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
    assert c._get_all_hooks() == component3()._get_all_hooks()


def test_get_hooks_nested2(component3, component4):
    """Test that a component returns both when parent and child have hooks.

    Args:
        component3: component with hooks defined.
        component4: component with different hooks defined.
    """
    exp_hooks = {**component3()._get_all_hooks(), **component4()._get_all_hooks()}
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
    "component,rendered",
    [
        (rx.text("hi"), '<RadixThemesText as={"p"}>\n  {"hi"}\n</RadixThemesText>'),
        (
            rx.box(rx.heading("test", size="3")),
            '<RadixThemesBox>\n  <RadixThemesHeading size={"3"}>\n  {"test"}\n</RadixThemesHeading>\n</RadixThemesBox>',
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
    button_component = rx.button("Click me", on_click=test_state.do_something)
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


TEST_VAR = LiteralVar.create("test")._replace(
    merge_var_data=VarData(
        hooks={"useTest": None},
        imports={"test": [ImportVar(tag="test")]},
        state="Test",
    )
)
FORMATTED_TEST_VAR = LiteralVar.create(f"foo{TEST_VAR}bar")
STYLE_VAR = TEST_VAR._replace(_js_expr="style")
EVENT_CHAIN_VAR = TEST_VAR._replace(_var_type=EventChain)
ARG_VAR = Var(_js_expr="arg")

TEST_VAR_DICT_OF_DICT = LiteralVar.create({"a": {"b": "test"}})._replace(
    merge_var_data=TEST_VAR._var_data
)
FORMATTED_TEST_VAR_DICT_OF_DICT = LiteralVar.create(
    {"a": {"b": f"footestbar"}}
)._replace(merge_var_data=TEST_VAR._var_data)

TEST_VAR_LIST_OF_LIST = LiteralVar.create([["test"]])._replace(
    merge_var_data=TEST_VAR._var_data
)
FORMATTED_TEST_VAR_LIST_OF_LIST = LiteralVar.create([["footestbar"]])._replace(
    merge_var_data=TEST_VAR._var_data
)

TEST_VAR_LIST_OF_LIST_OF_LIST = LiteralVar.create([[["test"]]])._replace(
    merge_var_data=TEST_VAR._var_data
)
FORMATTED_TEST_VAR_LIST_OF_LIST_OF_LIST = LiteralVar.create(
    [[["footestbar"]]]
)._replace(merge_var_data=TEST_VAR._var_data)

TEST_VAR_LIST_OF_DICT = LiteralVar.create([{"a": "test"}])._replace(
    merge_var_data=TEST_VAR._var_data
)
FORMATTED_TEST_VAR_LIST_OF_DICT = LiteralVar.create([{"a": "footestbar"}])._replace(
    merge_var_data=TEST_VAR._var_data
)


class ComponentNestedVar(Component):
    """A component with nested Var types."""

    dict_of_dict: Var[Dict[str, Dict[str, str]]]
    list_of_list: Var[List[List[str]]]
    list_of_list_of_list: Var[List[List[List[str]]]]
    list_of_dict: Var[List[Dict[str, str]]]


class EventState(rx.State):
    """State for testing event handlers with _get_vars."""

    v: int = 42

    def handler(self):
        """A handler that does nothing."""

    def handler2(self, arg):
        """A handler that takes an arg.

        Args:
            arg: An arg.
        """


@pytest.mark.parametrize(
    ("component", "exp_vars"),
    (
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
            [LiteralVar.create([TEST_VAR, "other-class"]).join(" ")],
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
            rx.fragment(style={"background_color": TEST_VAR}),  # type: ignore
            [STYLE_VAR],
            id="direct-style-background_color",
        ),
        pytest.param(
            rx.fragment(style={"background_color": f"foo{TEST_VAR}bar"}),  # type: ignore
            [STYLE_VAR],
            id="fstring-style-background_color",
        ),
        pytest.param(
            rx.fragment(on_click=EVENT_CHAIN_VAR),  # type: ignore
            [EVENT_CHAIN_VAR],
            id="direct-event-chain",
        ),
        pytest.param(
            rx.fragment(on_click=EventState.handler),
            [],
            id="direct-event-handler",
        ),
        pytest.param(
            rx.fragment(on_click=EventState.handler2(TEST_VAR)),  # type: ignore
            [ARG_VAR, TEST_VAR],
            id="direct-event-handler-arg",
        ),
        pytest.param(
            rx.fragment(on_click=EventState.handler2(EventState.v)),  # type: ignore
            [ARG_VAR, EventState.v],
            id="direct-event-handler-arg2",
        ),
        pytest.param(
            rx.fragment(on_click=lambda: EventState.handler2(TEST_VAR)),  # type: ignore
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
    ),
)
def test_get_vars(component, exp_vars):
    comp_vars = sorted(component._get_vars(), key=lambda v: v._js_expr)
    assert len(comp_vars) == len(exp_vars)
    print(comp_vars, exp_vars)
    for comp_var, exp_var in zip(
        comp_vars,
        sorted(exp_vars, key=lambda v: v._js_expr),
    ):
        # print(str(comp_var), str(exp_var))
        # print(comp_var._get_all_var_data(), exp_var._get_all_var_data())
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
    ]:  # type: ignore
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

    ...


class ValidComponent1(Component):
    """Test valid component."""

    _valid_children = ["ValidComponent2"]


class ValidComponent2(Component):
    """Test valid component."""

    ...


class ValidComponent3(Component):
    """Test valid component."""

    _valid_parents = ["ValidComponent2"]


class ValidComponent4(Component):
    """Test valid component."""

    _invalid_children = ["InvalidComponent"]


class InvalidComponent(Component):
    """Test invalid component."""

    ...


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
        rx.cond(  # type: ignore
            True,
            rx.fragment(valid_component2()),
            rx.fragment(
                rx.foreach(LiteralVar.create([1, 2, 3]), lambda x: valid_component2(x))  # type: ignore
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
                rx.match(
                    "nested_condition",
                    ("nested_first", valid_component2()),
                    rx.fragment(valid_component2()),
                ),
                valid_component2(),
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
        rx.cond(  # type: ignore
            True,
            rx.fragment(valid_component3()),
            rx.fragment(
                rx.foreach(
                    LiteralVar.create([1, 2, 3]),  # type: ignore
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
                rx.match(
                    "nested_condition",
                    ("nested_first", valid_component3()),
                    rx.fragment(valid_component3()),
                ),
                valid_component3(),
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
        valid_component2(
            rx.fragment(
                valid_component4(
                    rx.fragment(invalid_component()),
                ),
            ),
        )

    with pytest.raises(ValueError):
        valid_component4(
            rx.cond(  # type: ignore
                True,
                rx.fragment(invalid_component()),
                rx.fragment(
                    rx.foreach(
                        LiteralVar.create([1, 2, 3]), lambda x: invalid_component(x)
                    )  # type: ignore
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
    assert 'renamed_prop1={"prop1_1"}' in rendered_c1["props"]
    assert 'renamed_prop2={"prop2_1"}' in rendered_c1["props"]

    c2 = C2.create(prop1="prop1_2", prop2="prop2_2", prop3="prop3_2")
    rendered_c2 = c2.render()
    assert 'renamed_prop1={"prop1_2"}' in rendered_c2["props"]
    assert 'subclass_prop2={"prop2_2"}' in rendered_c2["props"]
    assert 'renamed_prop3={"prop3_2"}' in rendered_c2["props"]


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

    # The imports are only resolved during compilation.
    _, _, imports_inner = compile_components(custom_comp._get_all_custom_components())
    assert "inner" in imports_inner

    outer_comp = outer(c=wrapper())

    # Libraries are not imported directly, but are imported by the custom component.
    assert "inner" not in outer_comp._get_all_imports()
    assert "other" not in outer_comp._get_all_imports()

    # The imports are only resolved during compilation.
    _, _, imports_outer = compile_components(outer_comp._get_all_custom_components())
    assert "inner" in imports_outer
    assert "other" in imports_outer


def test_custom_component_declare_event_handlers_in_fields():
    class ReferenceComponent(Component):
        def get_event_triggers(self) -> Dict[str, Any]:
            """Test controlled triggers.

            Returns:
                Test controlled triggers.
            """
            return {
                **super().get_event_triggers(),
                "on_a": lambda e0: [e0],
                "on_b": lambda e0: [e0.target.value],
                "on_c": lambda e0: [],
                "on_d": lambda: [],
                "on_e": lambda: [],
                "on_f": lambda a, b, c: [c, b, a],
            }

    class TestComponent(Component):
        on_a: EventHandler[lambda e0: [e0]]
        on_b: EventHandler[lambda e0: [e0.target.value]]
        on_c: EventHandler[lambda e0: []]
        on_d: EventHandler[lambda: []]
        on_e: EventHandler
        on_f: EventHandler[lambda a, b, c: [c, b, a]]

    custom_component = ReferenceComponent.create()
    test_component = TestComponent.create()
    custom_triggers = custom_component.get_event_triggers()
    test_triggers = test_component.get_event_triggers()
    assert custom_triggers.keys() == test_triggers.keys()
    for trigger_name in custom_component.get_event_triggers():
        for v1, v2 in zip(
            parse_args_spec(test_triggers[trigger_name]),
            parse_args_spec(custom_triggers[trigger_name]),
        ):
            assert v1.equals(v2)


def test_invalid_event_trigger():
    class TriggerComponent(Component):
        on_push: Var[bool]

        def get_event_triggers(self) -> Dict[str, Any]:
            """Test controlled triggers.

            Returns:
                Test controlled triggers.
            """
            return {
                **super().get_event_triggers(),
                "on_a": lambda: [],
            }

    trigger_comp = TriggerComponent.create

    # test that these do not throw errors.
    trigger_comp(on_push=True)
    trigger_comp(on_a=rx.console_log("log"))

    with pytest.raises(ValueError):
        trigger_comp(on_b=rx.console_log("log"))


@pytest.mark.parametrize(
    "tags",
    (
        ["Component"],
        ["Component", "useState"],
        [ImportVar(tag="Component")],
        [ImportVar(tag="Component"), ImportVar(tag="useState")],
        ["Component", ImportVar(tag="useState")],
    ),
)
def test_component_add_imports(tags):
    class BaseComponent(Component):
        def _get_imports(self) -> ImportDict:
            return {}

    class Reference(Component):
        def _get_imports(self) -> ParsedImportDict:
            return imports.merge_imports(
                super()._get_imports(),
                parse_imports({"react": tags}),
                {"foo": [ImportVar(tag="bar")]},
            )

    class TestBase(Component):
        def add_imports(
            self,
        ) -> Dict[str, Union[str, ImportVar, List[str], List[ImportVar]]]:
            return {"foo": "bar"}

    class Test(TestBase):
        def add_imports(
            self,
        ) -> Dict[str, Union[str, ImportVar, List[str], List[ImportVar]]]:
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
        def add_hooks(self):
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
        def _get_hooks(self):
            return "const hook5 = 46"

    class GreatGrandchildComponent2(GrandchildComponent2):
        def add_hooks(self):
            return [
                "const hook2 = 43",
                "const hook6 = 47",
            ]

    assert list(BaseComponent()._get_all_hooks()) == ["const hook1 = 42"]
    assert list(ChildComponent1()._get_all_hooks()) == ["const hook1 = 42"]
    assert list(GrandchildComponent1()._get_all_hooks()) == [
        "const hook1 = 42",
        "const hook2 = 43",
        "const hook3 = 44",
    ]
    assert list(GreatGrandchildComponent1()._get_all_hooks()) == [
        "const hook1 = 42",
        "const hook2 = 43",
        "const hook3 = 44",
        "const hook4 = 45",
    ]
    assert list(GrandchildComponent2()._get_all_hooks()) == ["const hook5 = 46"]
    assert list(GreatGrandchildComponent2()._get_all_hooks()) == [
        "const hook5 = 46",
        "const hook2 = 43",
        "const hook6 = 47",
    ]
    assert list(
        BaseComponent.create(
            GrandchildComponent1.create(GreatGrandchildComponent2()),
            GreatGrandchildComponent1(),
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
            GreatGrandchildComponent2(),
            GreatGrandchildComponent1(),
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
        def _get_custom_code(self):
            return "const custom_code5 = 46"

    class GreatGrandchildComponent2(GrandchildComponent2):
        def add_custom_code(self):
            return [
                "const custom_code2 = 43",
                "const custom_code6 = 47",
            ]

    assert BaseComponent()._get_all_custom_code() == {"const custom_code1 = 42"}
    assert ChildComponent1()._get_all_custom_code() == {"const custom_code1 = 42"}
    assert GrandchildComponent1()._get_all_custom_code() == {
        "const custom_code1 = 42",
        "const custom_code2 = 43",
        "const custom_code3 = 44",
    }
    assert GreatGrandchildComponent1()._get_all_custom_code() == {
        "const custom_code1 = 42",
        "const custom_code2 = 43",
        "const custom_code3 = 44",
        "const custom_code4 = 45",
    }
    assert GrandchildComponent2()._get_all_custom_code() == {"const custom_code5 = 46"}
    assert GreatGrandchildComponent2()._get_all_custom_code() == {
        "const custom_code2 = 43",
        "const custom_code5 = 46",
        "const custom_code6 = 47",
    }
    assert BaseComponent.create(
        GrandchildComponent1.create(GreatGrandchildComponent2()),
        GreatGrandchildComponent1(),
    )._get_all_custom_code() == {
        "const custom_code1 = 42",
        "const custom_code2 = 43",
        "const custom_code3 = 44",
        "const custom_code4 = 45",
        "const custom_code5 = 46",
        "const custom_code6 = 47",
    }
    assert Fragment.create(
        GreatGrandchildComponent2(),
        GreatGrandchildComponent1(),
    )._get_all_custom_code() == {
        "const custom_code1 = 42",
        "const custom_code2 = 43",
        "const custom_code3 = 44",
        "const custom_code4 = 45",
        "const custom_code5 = 46",
        "const custom_code6 = 47",
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

    assert list(HookComponent()._get_all_hooks()) == [
        "const hook3 = useRef(null)",
        "const hook1 = 42",
        "const hook2 = 43",
        "useEffect(() => () => {}, [])",
    ]
    imports = HookComponent()._get_all_imports()
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
        merge_var_data=VarData(hooks={"useParent": None}),  # type: ignore
    )
    v1 = rx.color("plum", 10)
    v2 = LiteralVar.create("text")._replace(
        merge_var_data=VarData(hooks={"useText": None}),  # type: ignore
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

        def add_style(self):
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
    assert (
        str(page).count(
            f'css={{({{ ["fakeParent"] : "parent", ["color"] : "var(--plum-10)", ["fake"] : "text", ["margin"] : ({test_state.get_name()}.num+"%") }})}}'
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
    assert 'css={({ ["color"] : "red" })}' in str(page.children[0].children[0])

    # Expect only one instance of this CSS dict in the rendered page
    assert str(page).count('css={({ ["color"] : "red" })}') == 1


class TriggerState(rx.State):
    """Test state with event handlers."""

    def do_something(self):
        """Sample event handler."""
        pass


@pytest.mark.parametrize(
    "component, output",
    [
        (rx.box(rx.text("random text")), False),
        (
            rx.box(rx.text("random text", on_click=rx.console_log("log"))),
            False,
        ),
        (
            rx.box(
                rx.text("random text", on_click=TriggerState.do_something),
                rx.text(
                    "random text",
                    on_click=Var(_js_expr="toggleColorMode", _var_type=EventChain),
                ),
            ),
            True,
        ),
        (
            rx.box(
                rx.text("random text", on_click=rx.console_log("log")),
                rx.text(
                    "random text",
                    on_click=Var(_js_expr="toggleColorMode", _var_type=EventChain),
                ),
            ),
            False,
        ),
        (
            rx.box(rx.text("random text", on_click=TriggerState.do_something)),
            True,
        ),
        (
            rx.box(
                rx.text(
                    "random text",
                    on_click=[rx.console_log("log"), rx.window_alert("alert")],
                ),
            ),
            False,
        ),
        (
            rx.box(
                rx.text(
                    "random text",
                    on_click=[rx.console_log("log"), TriggerState.do_something],
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
