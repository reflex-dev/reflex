from typing import List, Set, Type

import pytest

from pynecone.components.component import Component, CustomComponent, ImportDict
from pynecone.components.layout.box import Box
from pynecone.event import EVENT_TRIGGERS, EventHandler
from pynecone.state import State
from pynecone.style import Style
from pynecone.var import Var


@pytest.fixture
def TestState():
    class TestState(State):
        num: int

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

        def _get_imports(self) -> ImportDict:
            return {"react": {"Component"}}

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

        @classmethod
        def get_controlled_triggers(cls) -> Set[str]:
            """Test controlled triggers.

            Returns:
                Test controlled triggers.
            """
            return {"on_open", "on_close"}

        def _get_imports(self) -> ImportDict:
            return {"react-redux": {"connect"}}

        def _get_custom_code(self) -> str:
            return "console.log('component2')"

    return TestComponent2


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

    def my_component(prop1: str, prop2: int):
        return Box.create(prop1, prop2)

    return my_component


def test_set_style_attrs(component1):
    """Test that style attributes are set in the dict.

    Args:
        component1: A test component.
    """
    component = component1(color="white", text_align="center")
    assert component.style["color"] == "white"
    assert component.style["textAlign"] == "center"


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
    assert c.style == {"color": "white", "textAlign": "center"}


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
    c1 = component1().add_style(style)  # type: ignore
    c2 = component2().add_style(style)  # type: ignore
    assert c1.style["color"] == "white"
    assert c2.style["color"] == "black"


def test_get_imports(component1, component2):
    """Test getting the imports of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    c1 = component1.create()
    c2 = component2.create(c1)
    assert c1.get_imports() == {"react": {"Component"}}
    assert c2.get_imports() == {"react-redux": {"connect"}, "react": {"Component"}}


def test_get_custom_code(component1, component2):
    """Test getting the custom code of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    # Check that the code gets compiled correctly.
    c1 = component1.create()
    c2 = component2.create()
    assert c1.get_custom_code() == {"console.log('component1')"}
    assert c2.get_custom_code() == {"console.log('component2')"}

    # Check that nesting components compiles both codes.
    c1 = component1.create(c2)
    assert c1.get_custom_code() == {
        "console.log('component1')",
        "console.log('component2')",
    }

    # Check that code is not duplicated.
    c1 = component1.create(c2, c2, c1, c1)
    assert c1.get_custom_code() == {
        "console.log('component1')",
        "console.log('component2')",
    }


def test_get_props(component1, component2):
    """Test that the props are set correctly.

    Args:
        component1: A test component.
        component2: A test component.
    """
    assert component1.get_props() == {"text", "number"}
    assert component2.get_props() == {"arr"}


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
    assert c.text == text
    assert c.number == number


@pytest.mark.parametrize(
    "text,number", [("", "bad_string"), (13, 1), (None, 1), ("test", [1, 2, 3])]
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


def test_var_props(component1, TestState):
    """Test that we can set a Var prop.

    Args:
        component1: A test component.
        TestState: A test state.
    """
    c1 = component1.create(text="hello", number=TestState.num)
    assert c1.number == TestState.num


def test_get_controlled_triggers(component1, component2):
    """Test that we can get the controlled triggers of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    assert component1.get_controlled_triggers() == set()
    assert component2.get_controlled_triggers() == {"on_open", "on_close"}


def test_get_triggers(component1, component2):
    """Test that we can get the triggers of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    assert component1.get_triggers() == EVENT_TRIGGERS
    assert component2.get_triggers() == {"on_open", "on_close"} | EVENT_TRIGGERS


def test_create_custom_component(my_component):
    """Test that we can create a custom component.

    Args:
        my_component: A test custom component.
    """
    component = CustomComponent(component_fn=my_component)
    assert component.tag == "MyComponent"
    assert component.get_props() == set()
    assert component.get_custom_components() == {component}


def test_custom_component_hash(my_component):
    """Test that the hash of a custom component is correct.

    Args:
        my_component: A test custom component.
    """
    component1 = CustomComponent(component_fn=my_component)
    component2 = CustomComponent(component_fn=my_component)
    assert set([component1, component2]) == {component1}
