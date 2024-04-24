from __future__ import annotations

from typing import List, Optional

import pytest
import sqlalchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

import reflex as rx
from reflex.utils.types import GenericType, get_attribute_access_type


class SQLABase(DeclarativeBase):
    pass


class SQLATag(SQLABase):
    __tablename__: str = "tag"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


class SQLALabel(SQLABase):
    __tablename__: str = "label"
    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey("test.id"))
    test: Mapped[SQLAClass] = relationship(back_populates="labels")


class SQLAClass(SQLABase):
    __tablename__: str = "test"
    id: Mapped[int] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column()
    int_list: Mapped[List[int]] = mapped_column(
        sqlalchemy.types.ARRAY(item_type=sqlalchemy.INTEGER)
    )
    str_list: Mapped[List[str]] = mapped_column(
        sqlalchemy.types.ARRAY(item_type=sqlalchemy.String)
    )
    optional_int: Mapped[Optional[int]] = mapped_column(nullable=True)
    sqla_tag_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey(SQLATag.id))
    sqla_tag: Mapped[Optional[SQLATag]] = relationship()
    labels: Mapped[List[SQLALabel]] = relationship(back_populates="test")

    @property
    def str_property(self) -> str:
        return self.name


class ModelClass(rx.Model):
    count: int = 0
    name: str = "test"
    int_list: List[int] = []
    str_list: List[str] = []
    optional_int: Optional[int] = None
    sqla_tag: Optional[SQLATag] = None
    labels: List[SQLALabel] = []

    @property
    def str_property(self) -> str:
        return self.name

class BaseClass(rx.Base):
    count: int = 0
    name: str = "test"
    int_list: List[int] = []
    str_list: List[str] = []
    optional_int: Optional[int] = None
    sqla_tag: Optional[SQLATag] = None
    labels: List[SQLALabel] = []

    @property
    def str_property(self) -> str:
        return self.name


class BareClass:
    count: int = 0
    name: str = "test"
    int_list: List[int] = []
    str_list: List[str] = []
    optional_int: Optional[int] = None
    sqla_tag: Optional[SQLATag] = None
    labels: List[SQLALabel] = []

    @property
    def str_property(self) -> str:
        return self.name


@pytest.fixture(params=[SQLAClass, BaseClass, BareClass, ModelClass])
def cls(request: pytest.FixtureRequest) -> type:
    return request.param


@pytest.mark.parametrize(
    "attr, expected",
    [
        pytest.param("count", int, id="int"),
        pytest.param("name", str, id="str"),
        pytest.param("int_list", List[int], id="List[int]"),
        pytest.param("str_list", List[str], id="List[str]"),
        pytest.param("optional_int", Optional[int], id="Optional[int]"),
        pytest.param("sqla_tag", Optional[SQLATag], id="Optional[SQLATag]"),
        pytest.param("labels", List[SQLALabel], id="List[SQLALabel]"),
        pytest.param("str_property", str, id="str_property"),
    ],
)
def test_get_attribute_access_type(cls: type, attr: str, expected: GenericType):
    assert get_attribute_access_type(cls, attr) == expected
