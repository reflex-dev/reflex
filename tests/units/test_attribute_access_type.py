from __future__ import annotations

from typing import List  # noqa: UP035

import attrs
import pytest

import reflex as rx
from reflex.utils.types import GenericType, get_attribute_access_type

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("pydantic")

import pydantic.v1
import sqlalchemy
import sqlmodel
from sqlalchemy import JSON, TypeDecorator
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)


class SQLAType(TypeDecorator):
    """SQLAlchemy custom dict type."""

    impl = JSON

    @property
    def python_type(self) -> type[dict[str, str]]:
        """Python type.

        Returns:
            Python Type of the column.
        """
        return dict[str, str]


class SQLABase(DeclarativeBase):
    """Base class for bare SQLAlchemy models."""

    type_annotation_map = {
        # do not use lower case dict here!
        # https://github.com/sqlalchemy/sqlalchemy/issues/9902
        dict[str, str]: SQLAType,
    }


class SQLATag(SQLABase):
    """Tag sqlalchemy model."""

    __tablename__: str = "tag"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


class SQLALabel(SQLABase):
    """Label sqlalchemy model."""

    __tablename__: str = "label"
    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey("test.id"))
    test: Mapped[SQLAClass] = relationship(back_populates="labels")
    test_dataclass_id: Mapped[int] = mapped_column(
        sqlalchemy.ForeignKey("test_dataclass.id")
    )
    test_dataclass: Mapped[SQLAClassDataclass] = relationship(back_populates="labels")


class SQLAClass(SQLABase):
    """Test sqlalchemy model."""

    __tablename__: str = "test"
    id: Mapped[int] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column()
    int_list: Mapped[list[int]] = mapped_column(
        sqlalchemy.types.ARRAY(item_type=sqlalchemy.INTEGER)
    )
    str_list: Mapped[list[str]] = mapped_column(
        sqlalchemy.types.ARRAY(item_type=sqlalchemy.String)
    )
    optional_int: Mapped[int | None] = mapped_column(nullable=True)
    sqla_tag_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey(SQLATag.id))
    sqla_tag: Mapped[SQLATag | None] = relationship()
    labels: Mapped[list[SQLALabel]] = relationship(back_populates="test")
    # do not use lower case dict here!
    # https://github.com/sqlalchemy/sqlalchemy/issues/9902
    dict_str_str: Mapped[dict[str, str]] = mapped_column()

    @property
    def str_property(self) -> str:
        """String property.

        Returns:
            Name attribute
        """
        return self.name

    @hybrid_property
    def str_or_int_property(self) -> str | int:
        """String or int property.

        Returns:
            Name attribute
        """
        return self.name

    @hybrid_property
    def first_label(self) -> SQLALabel | None:
        """First label property.

        Returns:
            First label
        """
        return self.labels[0] if self.labels else None


class SQLAClassDataclass(MappedAsDataclass, SQLABase):
    """Test sqlalchemy model."""

    id: Mapped[int] = mapped_column(primary_key=True)
    no_default: Mapped[int] = mapped_column(nullable=True)
    count: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column()
    int_list: Mapped[list[int]] = mapped_column(
        sqlalchemy.types.ARRAY(item_type=sqlalchemy.INTEGER)
    )
    str_list: Mapped[list[str]] = mapped_column(
        sqlalchemy.types.ARRAY(item_type=sqlalchemy.String)
    )
    optional_int: Mapped[int | None] = mapped_column(nullable=True)
    sqla_tag_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey(SQLATag.id))
    sqla_tag: Mapped[SQLATag | None] = relationship()
    labels: Mapped[list[SQLALabel]] = relationship(back_populates="test_dataclass")
    # do not use lower case dict here!
    # https://github.com/sqlalchemy/sqlalchemy/issues/9902
    dict_str_str: Mapped[dict[str, str]] = mapped_column()
    default_factory: Mapped[list[int]] = mapped_column(
        sqlalchemy.types.ARRAY(item_type=sqlalchemy.INTEGER),
        default_factory=list,
    )
    __tablename__: str = "test_dataclass"

    @property
    def str_property(self) -> str:
        """String property.

        Returns:
            Name attribute
        """
        return self.name

    @hybrid_property
    def str_or_int_property(self) -> str | int:
        """String or int property.

        Returns:
            Name attribute
        """
        return self.name

    @hybrid_property
    def first_label(self) -> SQLALabel | None:
        """First label property.

        Returns:
            First label
        """
        return self.labels[0] if self.labels else None


class ModelClass(rx.Model):
    """Test reflex model."""

    no_default: int | None = sqlmodel.Field(nullable=True)
    count: int = 0
    name: str = "test"
    int_list: list[int] = []
    str_list: list[str] = []
    optional_int: int | None = None
    sqla_tag: SQLATag | None = None
    labels: list[SQLALabel] = []
    dict_str_str: dict[str, str] = {}
    default_factory: list[int] = sqlmodel.Field(default_factory=list)

    @property
    def str_property(self) -> str:
        """String property.

        Returns:
            Name attribute
        """
        return self.name

    @property
    def str_or_int_property(self) -> str | int:
        """String or int property.

        Returns:
            Name attribute
        """
        return self.name

    @property
    def first_label(self) -> SQLALabel | None:
        """First label property.

        Returns:
            First label
        """
        return self.labels[0] if self.labels else None


class BaseClass(rx.Base):
    """Test rx.Base class."""

    no_default: int | None = pydantic.v1.Field(required=False)
    count: int = 0
    name: str = "test"
    int_list: list[int] = []
    str_list: list[str] = []
    optional_int: int | None = None
    sqla_tag: SQLATag | None = None
    labels: list[SQLALabel] = []
    dict_str_str: dict[str, str] = {}
    default_factory: list[int] = pydantic.v1.Field(default_factory=list)

    @property
    def str_property(self) -> str:
        """String property.

        Returns:
            Name attribute
        """
        return self.name

    @property
    def str_or_int_property(self) -> str | int:
        """String or int property.

        Returns:
            Name attribute
        """
        return self.name

    @property
    def first_label(self) -> SQLALabel | None:
        """First label property.

        Returns:
            First label
        """
        return self.labels[0] if self.labels else None


class BareClass:
    """Bare python class."""

    count: int = 0
    name: str = "test"
    int_list: list[int] = []
    str_list: list[str] = []
    optional_int: int | None = None
    sqla_tag: SQLATag | None = None
    labels: list[SQLALabel] = []
    dict_str_str: dict[str, str] = {}

    @property
    def str_property(self) -> str:
        """String property.

        Returns:
            Name attribute
        """
        return self.name

    @property
    def str_or_int_property(self) -> str | int:
        """String or int property.

        Returns:
            Name attribute
        """
        return self.name

    @property
    def first_label(self) -> SQLALabel | None:
        """First label property.

        Returns:
            First label
        """
        return self.labels[0] if self.labels else None


@attrs.define
class AttrClass:
    """Test attrs class."""

    count: int = 0
    name: str = "test"
    int_list: list[int] = attrs.field(factory=list)
    str_list: list[str] = attrs.field(factory=list)
    optional_int: int | None = None
    sqla_tag: SQLATag | None = None
    labels: list[SQLALabel] = attrs.field(factory=list)
    dict_str_str: dict[str, str] = attrs.field(factory=dict)
    default_factory: list[int] = attrs.field(factory=list)

    @property
    def str_property(self) -> str:
        """String property.

        Returns:
            Name attribute
        """
        return self.name

    @property
    def str_or_int_property(self) -> str | int:
        """String or int property.

        Returns:
            Name attribute
        """
        return self.name

    @property
    def first_label(self) -> SQLALabel | None:
        """First label property.

        Returns:
            First label
        """
        return self.labels[0] if self.labels else None


@pytest.mark.parametrize(
    "cls",
    [
        SQLAClass,
        SQLAClassDataclass,
        BaseClass,
        BareClass,
        ModelClass,
        AttrClass,
    ],
)
@pytest.mark.parametrize(
    ("attr", "expected"),
    [
        pytest.param("count", int, id="int"),
        pytest.param("name", str, id="str"),
        pytest.param("int_list", (list[int], List[int]), id="list[int]"),  # noqa: UP006
        pytest.param("str_list", (list[str], List[str]), id="list[str]"),  # noqa: UP006
        pytest.param("optional_int", int | None, id="int | None"),
        pytest.param("sqla_tag", SQLATag | None, id="SQLATag | None"),
        pytest.param("labels", list[SQLALabel], id="list[SQLALabel]"),
        pytest.param("dict_str_str", dict[str, str], id="dict[str, str]"),
        pytest.param("str_property", str, id="str_property"),
        pytest.param("str_or_int_property", str | int, id="str_or_int_property"),
        pytest.param("first_label", SQLALabel | None, id="first_label"),
    ],
)
def test_get_attribute_access_type(cls: type, attr: str, expected: GenericType) -> None:
    """Test get_attribute_access_type returns the correct type.

    Args:
        cls: Class to test.
        attr: Attribute to test.
        expected: Expected type.
    """
    if isinstance(expected, tuple):
        assert get_attribute_access_type(cls, attr) in expected
    else:
        assert get_attribute_access_type(cls, attr) == expected


@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        (SQLAClassDataclass, List[int]),  # noqa: UP006
        (BaseClass, list[int]),
        (ModelClass, list[int]),
        (AttrClass, list[int]),
    ],
)
def test_get_attribute_access_type_default_factory(
    cls: type, expected: GenericType
) -> None:
    """Test get_attribute_access_type returns the correct type for default factory fields.

    Args:
        cls: Class to test.
        expected: Expected type.
    """
    assert get_attribute_access_type(cls, "default_factory") == expected


@pytest.mark.parametrize(
    "cls",
    [
        SQLAClassDataclass,
        BaseClass,
        ModelClass,
    ],
)
def test_get_attribute_access_type_no_default(cls: type) -> None:
    """Test get_attribute_access_type returns the correct type for fields with no default which are not required.

    Args:
        cls: Class to test.
    """
    assert get_attribute_access_type(cls, "no_default") == int | None
