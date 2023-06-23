import pytest
import sqlmodel

from reflex.model import Model


@pytest.fixture
def model_default_primary() -> Model:
    """Returns a model object with no defined primary key.

    Returns:
        Model: Model object.
    """

    class ChildModel(Model):
        name: str

    return ChildModel(name="name")  # type: ignore


@pytest.fixture
def model_custom_primary() -> Model:
    """Returns a model object with a custom primary key.

    Returns:
        Model: Model object.
    """

    class ChildModel(Model):
        custom_id: int = sqlmodel.Field(default=None, primary_key=True)
        name: str

    return ChildModel(name="name")  # type: ignore


def test_default_primary_key(model_default_primary):
    """Test that if a primary key is not defined a default is added.

    Args:
        model_default_primary: Fixture.
    """
    assert "id" in model_default_primary.__class__.__fields__


def test_custom_primary_key(model_custom_primary):
    """Test that if a primary key is defined no default key is added.

    Args:
        model_custom_primary: Fixture.
    """
    assert "id" not in model_custom_primary.__class__.__fields__
