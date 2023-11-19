from typing import Any, Dict, List, Type

import pytest

import reflex as rx
from reflex.base import Base
from reflex.components.base.bare import Bare
from reflex.components.component import (
    Component,
    CustomComponent,
    StatefulComponent,
    custom_component,
)
from reflex.components.layout.box import Box
from reflex.constants import EventTriggers
from reflex.event import EventChain, EventHandler
from reflex.state import State
from reflex.style import Style
from reflex.utils import imports
from reflex.utils.imports import ImportVar
from reflex.vars import Var, VarData


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
        tag = "RandomComponent"

        _invalid_children: List[str] = ["Text"]

        _valid_children: List[str] = ["Text"]

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
    assert c.text._decode() == text
    assert c.number._decode() == number


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
    assert set(component1().get_event_triggers().keys()) == default_triggers
    assert (
        component2().get_event_triggers().keys()
        == {"on_open", "on_close"} | default_triggers
    )


class C1State(State):
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
        "onFoo={(__e,_alpha,_bravo,_charlie) => addEvents("
        '[Event("c1_state.mock_handler", {_e:__e.target.value,_bravo:_bravo["nested"],_charlie:(_charlie.custom + 42)})], '
        "(__e,_alpha,_bravo,_charlie), {})}"
    )


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
        return rx.box(
            width=width,
            color=color,
        )

    ccomponent = my_component(
        rx.text("child"), width=Var.create(1), color=Var.create("red")
    )
    assert isinstance(ccomponent, CustomComponent)
    assert len(ccomponent.children) == 1
    assert isinstance(ccomponent.children[0], rx.Text)

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
        component2.create(on_open=test_state.do_something)
        component2.create(
            on_open=[test_state.do_something_arg, test_state.do_something]
        )
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
        (rx.text("hi"), "<Text>\n  {`hi`}\n</Text>"),
        (
            rx.box(rx.heading("test", size="md")),
            "<Box>\n  <Heading size={`md`}>\n  {`test`}\n</Heading>\n</Box>",
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


TEST_VAR = Var.create_safe("test")._replace(
    merge_var_data=VarData(
        hooks={"useTest"}, imports={"test": {ImportVar(tag="test")}}, state="Test"
    )
)
FORMATTED_TEST_VAR = Var.create(f"foo{TEST_VAR}bar")
STYLE_VAR = TEST_VAR._replace(_var_name="style", _var_is_local=False)
EVENT_CHAIN_VAR = TEST_VAR._replace(_var_type=EventChain)
ARG_VAR = Var.create("arg")


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
            rx.text(as_=f"foo{TEST_VAR}bar"),
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
            rx.fragment(special_props={TEST_VAR}),
            [TEST_VAR],
            id="direct-special_props",
        ),
        pytest.param(
            rx.fragment(special_props={Var.create(f"foo{TEST_VAR}bar")}),
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
    ),
)
def test_get_vars(component, exp_vars):
    comp_vars = sorted(component._get_vars(), key=lambda v: v._var_name)
    assert len(comp_vars) == len(exp_vars)
    for comp_var, exp_var in zip(
        comp_vars,
        sorted(exp_vars, key=lambda v: v._var_name),
    ):
        assert comp_var.equals(exp_var)
