import pytest

from pynecone.base import Base


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
