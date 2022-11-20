from typing import Type

import pytest

from pynecone.components.component import Component, ImportDict
from pynecone.event import EventHandler
from pynecone.state import State
from pynecone.style import Style


@pytest.fixture
def component1() -> Type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent1(Component):
        def _get_imports(self) -> ImportDict:
            return {"react": {"Component"}}

    return TestComponent1


@pytest.fixture
def component2() -> Type[Component]:
    """A test component.

    Returns:
        A test component.
    """

    class TestComponent2(Component):
        def _get_imports(self) -> ImportDict:
            return {"react-redux": {"connect"}}

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


def test_set_style_attrs(component1: Type[Component]):
    """Test that style attributes are set in the dict.

    Args:
        component1: A test component.
    """
    component = component1(color="white", text_align="center")
    assert component.style["color"] == "white"
    assert component.style["textAlign"] == "center"


def test_create_component(component1: Type[Component]):
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


def test_add_style(component1: Type[Component], component2: Type[Component]):
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


def test_get_imports(component1: Type[Component], component2: Type[Component]):
    """Test getting the imports of a component.

    Args:
        component1: A test component.
        component2: A test component.
    """
    c1 = component1.create()
    c2 = component2.create(c1)
    assert c1.get_imports() == {"react": {"Component"}}
    assert c2.get_imports() == {"react-redux": {"connect"}, "react": {"Component"}}
