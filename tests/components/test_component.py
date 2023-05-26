from typing import Dict, List, Type

import pytest

import pynecone as pc
from pynecone.components.component import Component, CustomComponent, custom_component
from pynecone.components.layout.box import Box
from pynecone.event import EVENT_ARG, EVENT_TRIGGERS, EventHandler
from pynecone.state import State
from pynecone.style import Style
from pynecone.utils import imports
from pynecone.vars import ImportVar, Var


@pytest.fixture
def test_state():
    class TestState(State):
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

        def _get_imports(self) -> imports.ImportDict:
            return {"react": {ImportVar(tag="Component")}}

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

        def get_controlled_triggers(self) -> Dict[str, Var]:
            """Test controlled triggers.

            Returns:
                Test controlled triggers.
            """
            return {
                "on_open": EVENT_ARG,
                "on_close": EVENT_ARG,
            }

        def _get_imports(self) -> imports.ImportDict:
            return {"react-redux": {ImportVar(tag="connect")}}

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
        tag = "Tag"

        invalid_children: List[str] = ["Text"]

    return TestComponent5


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
    assert component.style["color"] == "white"
    assert component.style["textAlign"] == "center"


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
    assert c1.get_imports() == {"react": {ImportVar(tag="Component")}}
    assert c2.get_imports() == {
        "react-redux": {ImportVar(tag="connect")},
        "react": {ImportVar(tag="Component")},
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


def test_var_props(component1, test_state):
    """Test that we can set a Var prop.

    Args:
        component1: A test component.
        test_state: A test state.
    """
    c1 = component1.create(text="hello", number=test_state.num)
    assert c1.number == test_state.num


def test_get_controlled_triggers(component1, component2):
    """Test that we can get the controlled triggers of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    assert component1().get_controlled_triggers() == dict()
    assert set(component2().get_controlled_triggers()) == {"on_open", "on_close"}


def test_get_triggers(component1, component2):
    """Test that we can get the triggers of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    assert component1().get_triggers() == EVENT_TRIGGERS
    assert component2().get_triggers() == {"on_open", "on_close"} | EVENT_TRIGGERS


def test_create_custom_component(my_component):
    """Test that we can create a custom component.

    Args:
        my_component: A test custom component.
    """
    component = CustomComponent(component_fn=my_component, prop1="test", prop2=1)
    assert component.tag == "MyComponent"
    assert component.get_props() == set()
    assert component.get_custom_components() == {component}


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
        return pc.box(
            width=width,
            color=color,
        )

    ccomponent = my_component(
        pc.text("child"), width=Var.create(1), color=Var.create("red")
    )
    assert isinstance(ccomponent, CustomComponent)
    assert len(ccomponent.children) == 1
    assert isinstance(ccomponent.children[0], pc.Text)

    component = ccomponent.get_component()
    assert isinstance(component, Box)


def test_invalid_event_handler_args(component2, test_state):
    """Test that an invalid event handler raises an error.

    Args:
        component2: A test component.
        test_state: A test state.
    """
    # Uncontrolled event handlers should not take args.
    # This is okay.
    component2.create(on_click=test_state.do_something)
    # This is not okay.
    with pytest.raises(ValueError):
        component2.create(on_click=test_state.do_something_arg)
    # However lambdas are okay.
    component2.create(on_click=lambda: test_state.do_something_arg(1))
    component2.create(
        on_click=lambda: [test_state.do_something_arg(1), test_state.do_something]
    )
    component2.create(
        on_click=lambda: [test_state.do_something_arg(1), test_state.do_something()]
    )

    # Controlled event handlers should take args.
    # This is okay.
    component2.create(on_open=test_state.do_something_arg)

    # do_something is allowed and will simply run while ignoring the arg
    component2.create(on_open=test_state.do_something)
    component2.create(on_open=[test_state.do_something_arg, test_state.do_something])


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
    assert c.get_hooks() == component3().get_hooks()


def test_get_hooks_nested2(component3, component4):
    """Test that a component returns both when parent and child have hooks.

    Args:
        component3: component with hooks defined.
        component4: component with different hooks defined.
    """
    exp_hooks = component3().get_hooks().union(component4().get_hooks())
    assert component3.create(component4.create()).get_hooks() == exp_hooks
    assert component4.create(component3.create()).get_hooks() == exp_hooks
    assert (
        component4.create(
            component3.create(),
            component4.create(),
            component3.create(),
        ).get_hooks()
        == exp_hooks
    )


def test_unsupported_child_components(component5):
    """Test that a value error is raised when an unsupported component is provided as a child.

    Args:
        component5: the test component
    """
    with pytest.raises(ValueError) as err:
        comp = component5.create(pc.text("testing component"))
        comp.render()
    assert (
        err.value.args[0]
        == f"The component `tag` cannot have `text` as a child component"
    )
