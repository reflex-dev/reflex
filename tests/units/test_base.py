import pytest

from reflex.base import Base


@pytest.fixture
def child() -> Base:
    """A child class.

    Returns:
        A child class.
    """

    class Child(Base):
        num: float
        key: str

    return Child(num=3.14, key="pi")


def test_get_fields(child):
    """Test that the fields are set correctly.

    Args:
        child: A child class.
    """
    assert child.get_fields().keys() == {"num", "key"}


def test_set(child):
    """Test setting fields.

    Args:
        child: A child class.
    """
    child.set(num=1, key="a")
    assert child.num == 1
    assert child.key == "a"


def test_json(child):
    """Test converting to json.

    Args:
        child: A child class.
    """
    assert child.json().replace(" ", "") == '{"num":3.14,"key":"pi"}'


@pytest.fixture
def complex_child() -> Base:
    """A child class.

    Returns:
        A child class.
    """

    class Child(Base):
        num: float
        key: str
        name: str
        age: int
        active: bool

    return Child(num=3.14, key="pi", name="John Doe", age=30, active=True)


def test_complex_get_fields(complex_child):
    """Test that the fields are set correctly.

    Args:
        complex_child: A child class.
    """
    assert complex_child.get_fields().keys() == {"num", "key", "name", "age", "active"}


def test_complex_set(complex_child):
    """Test setting fields.

    Args:
        complex_child: A child class.
    """
    complex_child.set(num=1, key="a", name="Jane Doe", age=28, active=False)
    assert complex_child.num == 1
    assert complex_child.key == "a"
    assert complex_child.name == "Jane Doe"
    assert complex_child.age == 28
    assert complex_child.active is False


def test_complex_json(complex_child):
    """Test converting to json.

    Args:
        complex_child: A child class.
    """
    assert (
        complex_child.json().replace(" ", "")
        == '{"num":3.14,"key":"pi","name":"JohnDoe","age":30,"active":true}'
    )
