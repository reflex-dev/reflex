import pytest
from reflex_base.utils.serializers import serializer

from reflex.istate.proxy import MutableProxy

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("alembic")
pytest.importorskip("pydantic")

# Import SQLAlchemy classes for mutable tests
from sqlalchemy import ARRAY, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tests.units.states.mutation import MutableTestState


class MutableSQLABase(DeclarativeBase):
    """SQLAlchemy base model for mutable vars."""


class MutableSQLAModel(MutableSQLABase):
    """SQLAlchemy model for mutable vars."""

    __tablename__: str = "mutable_test_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strlist: Mapped[list[str]] = mapped_column(ARRAY(String))
    hashmap: Mapped[dict[str, str]] = mapped_column(JSON)
    test_set: Mapped[set[str]] = mapped_column(ARRAY(String))


@serializer
def serialize_mutable_sqla_model(
    model: MutableSQLAModel,
) -> dict[str, list[str] | dict[str, str]]:
    """Serialize the MutableSQLAModel.

    Args:
        model: The MutableSQLAModel instance to serialize.

    Returns:
        The serialized model.
    """
    return {"strlist": model.strlist, "hashmap": model.hashmap}


class MutableTestStateWithSQLAlchemy(MutableTestState):
    """A test state."""

    sqla_model: MutableSQLAModel = MutableSQLAModel(
        strlist=["a", "b", "c"],
        hashmap={"key": "value"},
        test_set={"one", "two", "three"},
    )

    def reassign_mutables(self):
        """Assign mutable fields to different values."""
        super().reassign_mutables()
        self.sqla_model = MutableSQLAModel(
            strlist=["d", "e", "f"],
            hashmap={"key": "value"},
            test_set={"one", "two", "three"},
        )


@pytest.fixture
def mutable_state() -> MutableTestStateWithSQLAlchemy:
    """Create a Test state containing mutable types.

    Returns:
        A state object.
    """
    return MutableTestStateWithSQLAlchemy()


def test_setattr_of_mutable_types(mutable_state: MutableTestStateWithSQLAlchemy):
    """Test that mutable types are converted to corresponding Reflex wrappers.

    Args:
        mutable_state: A test state.
    """
    sqla_model = mutable_state.sqla_model

    assert isinstance(sqla_model, MutableProxy)
    assert isinstance(sqla_model, MutableSQLAModel)
    assert isinstance(sqla_model.strlist, MutableProxy)
    assert isinstance(sqla_model.strlist, list)
    assert isinstance(sqla_model.hashmap, MutableProxy)
    assert isinstance(sqla_model.hashmap, dict)
    assert isinstance(sqla_model.test_set, MutableProxy)
    assert isinstance(sqla_model.test_set, set)

    mutable_state.reassign_mutables()

    sqla_model = mutable_state.sqla_model

    assert isinstance(sqla_model, MutableProxy)
    assert isinstance(sqla_model, MutableSQLAModel)
    assert isinstance(sqla_model.strlist, MutableProxy)
    assert isinstance(sqla_model.strlist, list)
    assert isinstance(sqla_model.hashmap, MutableProxy)
    assert isinstance(sqla_model.hashmap, dict)
    assert isinstance(sqla_model.test_set, MutableProxy)
    assert isinstance(sqla_model.test_set, set)


def test_mutable_sqla_model(mutable_state: MutableTestStateWithSQLAlchemy):
    """Test that mutable SQLA models are tracked correctly.

    Args:
        mutable_state: A test state.
    """
    assert not mutable_state.dirty_vars

    def assert_sqla_model_dirty():
        assert mutable_state.dirty_vars == {"sqla_model"}
        mutable_state._clean()
        assert not mutable_state.dirty_vars

    mutable_state.sqla_model.strlist.append("foo")
    assert_sqla_model_dirty()
    mutable_state.sqla_model.hashmap["key"] = "value"
    assert_sqla_model_dirty()
    mutable_state.sqla_model.test_set.add("bar")
    assert_sqla_model_dirty()
