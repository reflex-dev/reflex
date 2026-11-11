from __future__ import annotations

import sys
import types
from collections.abc import Generator
from datetime import datetime
from decimal import Decimal
from typing import Any, List, NotRequired, TypedDict  # noqa: UP035

import attrs
import pytest
from reflex_base.utils import types as types_module
from reflex_base.utils.exceptions import VarAttributeError
from reflex_base.utils.types import GenericType, get_attribute_access_type

import reflex as rx

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("pydantic")

import pydantic
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
    synonym,
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


class BaseClass(pydantic.BaseModel):
    """Test pydantic BaseModel class."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    no_default: int | None = pydantic.Field(default=None)
    count: int = pydantic.Field(default=0)
    name: str = pydantic.Field(default="test")
    int_list: list[int] = pydantic.Field(default_factory=list)
    str_list: list[str] = pydantic.Field(default_factory=list)
    optional_int: int | None = pydantic.Field(default=None)
    sqla_tag: SQLATag | None = pydantic.Field(default=None)
    labels: list[SQLALabel] = pydantic.Field(default_factory=list)
    dict_str_str: dict[str, str] = pydantic.Field(default_factory=dict)
    default_factory: list[int] = pydantic.Field(default_factory=list)

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


def test_get_attribute_access_type_sqlalchemy_synonyms() -> None:
    """A synonym has the type of its annotated getter, else of its target attribute."""

    def status_length(member) -> int:
        return len(member.raw_status)

    class SynonymBase(DeclarativeBase):
        pass

    class SynonymWriter(SynonymBase):
        __tablename__ = "synonym_type_writer"
        id: Mapped[int] = mapped_column(primary_key=True)

    class SynonymMember(SynonymBase):
        __tablename__ = "synonym_type_member"
        id: Mapped[int] = mapped_column(primary_key=True)
        raw_status: Mapped[str] = mapped_column("status")
        note: Mapped[str | None]
        writer_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey(SynonymWriter.id))
        writer: Mapped[SynonymWriter] = relationship()
        status = synonym("raw_status")
        nick: Mapped[str] = synonym("raw_status")
        remark = synonym("note")
        alias = synonym("nick")
        author = synonym("writer")
        status_size = synonym("raw_status", descriptor=property(status_length))
        shout = synonym(
            "raw_status", descriptor=property(lambda self: self.raw_status.upper())
        )

    assert get_attribute_access_type(SynonymMember, "status") is str
    assert get_attribute_access_type(SynonymMember, "nick") is str
    assert get_attribute_access_type(SynonymMember, "remark") == str | None
    assert get_attribute_access_type(SynonymMember, "alias") is str
    assert get_attribute_access_type(SynonymMember, "author") == SynonymWriter | None
    assert get_attribute_access_type(SynonymMember, "status_size") is int
    assert get_attribute_access_type(SynonymMember, "shout") is str


class UnresolvableRefClass:
    """Class with an unresolvable forward-ref annotation."""

    broken: UndefinedElsewhere  # noqa: F821 # pyright: ignore[reportUndefinedVariable]
    count: int = 0


def test_get_attribute_access_type_unannotated_name_skips_hint_resolution(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unannotated name resolves to None without ForwardRef warnings."""
    assert get_attribute_access_type(UnresolvableRefClass, "_is_coroutine_marker") is (
        None
    )
    assert not [
        r for r in caplog.records if "Failed to resolve ForwardRefs" in r.message
    ]


def test_get_attribute_access_type_unresolvable_annotation_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An annotated name whose hints cannot be resolved still warns and returns None."""
    assert get_attribute_access_type(UnresolvableRefClass, "broken") is None
    assert [r for r in caplog.records if "Failed to resolve ForwardRefs" in r.message]


@pytest.mark.skipif(
    sys.version_info < (3, 14), reason="PEP 649 lazy annotations require 3.14+"
)
def test_get_attribute_access_type_probe_on_lazy_annotations(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Probing a class with lazy (PEP 649) annotations must not raise.

    Compiled with ``dont_inherit=True``: ``exec`` inherits this module's
    ``from __future__ import annotations`` flag by default, which would
    stringify the annotations instead of leaving them lazily evaluated.
    """
    code = compile(
        "class Lazy:\n    broken: UndefinedElsewhere\n    count: int = 0",
        "<lazy>",
        "exec",
        dont_inherit=True,
    )
    ns: dict[str, object] = {}
    exec(code, ns)
    lazy_cls = ns["Lazy"]
    assert isinstance(lazy_cls, type)
    with pytest.raises(NameError):
        lazy_cls.__annotations__  # prove annotations are genuinely lazy
    assert get_attribute_access_type(lazy_cls, "_is_coroutine_marker") is None
    assert not [
        r for r in caplog.records if "Failed to resolve ForwardRefs" in r.message
    ]


_DECLARATIVE_MODELS_SOURCE = """
import datetime
import decimal
import enum
from collections.abc import Sequence
from typing import Annotated, Any, Optional, TypedDict

import sqlalchemy
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    column_property,
    mapped_column,
)


class Color(enum.Enum):
    RED = "red"


class Level(enum.IntEnum):
    LOW = 1


class Tag(enum.StrEnum):
    A = "a"


class Prefs(TypedDict):
    theme: str


class Opaque(sqlalchemy.types.UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "OPAQUE"

    @property
    def python_type(self):
        # The default of SQLAlchemy < 2.1 and of many third-party types.
        raise NotImplementedError


class DictType(sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.JSON
    cache_ok = True

    @property
    def python_type(self):
        return dict


class ListType(sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.JSON
    cache_ok = True

    @property
    def python_type(self):
        return list


nullable_str = Annotated[str, mapped_column(nullable=True)]


class Base(DeclarativeBase):
    pass


class DataclassBase(MappedAsDataclass, DeclarativeBase):
    pass


class StampMixin:
    stamp: Mapped[datetime.datetime | None] = mapped_column()


class Plain(StampMixin, Base):
    __tablename__ = "plain"
{body}

class Dataclass(DataclassBase):
    __tablename__ = "dataclass"
{body}

class Imperative(Base):
    __tablename__ = "imperative"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    doc = sqlalchemy.Column(sqlalchemy.JSON)
    count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    docs = sqlalchemy.Column(sqlalchemy.ARRAY(sqlalchemy.JSON))
"""

_DECLARATIVE_MODEL_BODY = """
    id: Mapped[int] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column()
    note: Mapped[str | None] = mapped_column()
    annotated_note: Mapped[nullable_str]
    forced_nullable: Mapped[int] = mapped_column(nullable=True)
    forced_not_null: Mapped[str | None] = mapped_column(nullable=False)
    json_forced_not_null: Mapped[dict | None] = mapped_column(
        sqlalchemy.JSON, nullable=False
    )
    json_dict: Mapped[dict] = mapped_column(sqlalchemy.JSON)
    json_dict_any: Mapped[dict[str, Any]] = mapped_column(sqlalchemy.JSON)
    json_dict_none: Mapped[dict | None] = mapped_column(sqlalchemy.JSON)
    json_dict_optional: Mapped[Optional[dict]] = mapped_column(sqlalchemy.JSON)
    json_dict_str_none: Mapped[dict[str, str] | None] = mapped_column(
        sqlalchemy.JSON
    )
    json_list: Mapped[list[str]] = mapped_column(sqlalchemy.JSON)
    jsonb_list: Mapped[list[str]] = mapped_column(postgresql.JSONB)
    array_list: Mapped[list[str]] = mapped_column(sqlalchemy.ARRAY(sqlalchemy.String))
    array_sequence: Mapped[Sequence[str]] = mapped_column(
        sqlalchemy.ARRAY(sqlalchemy.String)
    )
    array_json: Mapped[list[dict]] = mapped_column(sqlalchemy.ARRAY(sqlalchemy.JSON))
    array_json_none: Mapped[list[dict[str, int]] | None] = mapped_column(
        sqlalchemy.ARRAY(sqlalchemy.JSON)
    )
    pickled: Mapped[dict | None] = mapped_column(sqlalchemy.PickleType)
    refined_dict: Mapped[dict[str, int]] = mapped_column(DictType())
    refined_list_none: Mapped[list[str] | None] = mapped_column(ListType())
    renamed: Mapped[dict] = mapped_column("payload", sqlalchemy.JSON)
    opaque: Mapped[dict] = mapped_column(Opaque())
    any_int: Mapped[Any] = mapped_column(sqlalchemy.Integer)
    object_int: Mapped[object] = mapped_column(sqlalchemy.Integer)
    color: Mapped[Color] = mapped_column(sqlalchemy.Enum(Color))
    color_as_str: Mapped[str] = mapped_column(sqlalchemy.Enum(Color))
    bool_int: Mapped[bool] = mapped_column(sqlalchemy.Integer)
    int_enum_int: Mapped[Level] = mapped_column(sqlalchemy.Integer)
    str_enum_str: Mapped[Tag] = mapped_column(sqlalchemy.String)
    typed_dict: Mapped[Prefs] = mapped_column(DictType())
    price: Mapped[decimal.Decimal] = mapped_column(sqlalchemy.Numeric)
    float_price: Mapped[float] = mapped_column(sqlalchemy.Numeric)
    at: Mapped[datetime.datetime] = mapped_column()
    total: Mapped[int] = column_property(count + 1)
"""


@pytest.fixture(scope="module", params=["future", "eager_or_lazy"])
def declarative_models(
    request: pytest.FixtureRequest,
) -> Generator[types.ModuleType, None, None]:
    """Build the declarative models module with and without string annotations.

    Args:
        request: The fixture request; its param selects the annotation mode.

    Yields:
        The module defining the models.
    """
    source = _DECLARATIVE_MODELS_SOURCE.format(body=_DECLARATIVE_MODEL_BODY)
    if request.param == "future":
        source = "from __future__ import annotations\n" + source
    name = f"_declarative_models_{request.param}"
    module = types.ModuleType(name)
    sys.modules[name] = module
    # dont_inherit: this test module's `from __future__ import annotations` must
    # not stringify the annotations of the "eager_or_lazy" variant.
    exec(compile(source, name, "exec", dont_inherit=True), module.__dict__)
    yield module
    del sys.modules[name]


@pytest.mark.parametrize("model", ["Plain", "Dataclass"])
@pytest.mark.parametrize(
    ("attr", "expected"),
    [
        pytest.param("id", int, id="int-pk"),
        pytest.param("count", int, id="int"),
        pytest.param("name", str, id="str"),
        pytest.param("note", str | None, id="str-none"),
        pytest.param("annotated_note", str | None, id="annotated-str-nullable"),
        pytest.param("forced_nullable", int | None, id="nullable-column"),
        pytest.param("forced_not_null", str, id="not-null-column"),
        pytest.param("json_forced_not_null", dict, id="json-not-null-column"),
        pytest.param("json_dict", dict, id="json-dict"),
        pytest.param("json_dict_any", dict[str, Any], id="json-dict-str-any"),
        pytest.param("json_dict_none", dict | None, id="json-dict-none"),
        pytest.param("json_dict_optional", dict | None, id="json-optional-dict"),
        pytest.param(
            "json_dict_str_none", dict[str, str] | None, id="json-dict-str-str-none"
        ),
        pytest.param("json_list", list[str], id="json-list-str"),
        pytest.param("jsonb_list", list[str], id="jsonb-list-str"),
        pytest.param("array_list", List[str], id="array-list-str"),  # noqa: UP006
        pytest.param(
            "array_sequence",
            List[str],  # noqa: UP006
            id="array-python-type-over-coarser-annotation",
        ),
        pytest.param("array_json", list[dict], id="array-opaque-item-annotation"),
        pytest.param(
            "array_json_none",
            list[dict[str, int]] | None,
            id="array-opaque-item-annotation-none",
        ),
        pytest.param("pickled", dict | None, id="pickle-dict-none"),
        pytest.param("refined_dict", dict[str, int], id="annotation-refines-dict"),
        pytest.param(
            "refined_list_none", list[str] | None, id="annotation-refines-list"
        ),
        pytest.param("renamed", dict, id="json-renamed-column"),
        pytest.param("opaque", dict, id="python-type-not-implemented"),
        pytest.param("any_int", int, id="any-annotation-uses-python-type"),
        pytest.param("object_int", int, id="object-annotation-uses-python-type"),
        pytest.param("color", "Color", id="enum"),
        pytest.param("color_as_str", "Color", id="enum-python-type-over-str"),
        pytest.param("bool_int", int, id="python-type-over-bool-subclass"),
        pytest.param("int_enum_int", int, id="python-type-over-int-enum-subclass"),
        pytest.param("str_enum_str", str, id="python-type-over-str-enum-subclass"),
        pytest.param("typed_dict", "Prefs", id="typed-dict-refines-dict"),
        pytest.param("price", Decimal, id="decimal"),
        pytest.param("float_price", Decimal, id="decimal-python-type-over-float"),
        pytest.param("at", datetime, id="datetime"),
        pytest.param("total", int, id="column-property"),
    ],
)
def test_get_attribute_access_type_declarative_column(
    declarative_models: types.ModuleType, model: str, attr: str, expected: Any
) -> None:
    """A mapped column has its python type, or its ``Mapped[...]`` type if better.

    Args:
        declarative_models: The module defining the models.
        model: The name of the model class.
        attr: The column attribute.
        expected: The expected type, or the name of a class of the models module.
    """
    if isinstance(expected, str):
        expected = getattr(declarative_models, expected)
    cls = getattr(declarative_models, model)
    assert get_attribute_access_type(cls, attr) == expected


def test_get_attribute_access_type_declarative_mixin_column(
    declarative_models: types.ModuleType,
) -> None:
    """A column declared by a mixin has the type of the mixin's annotation.

    Args:
        declarative_models: The module defining the models.
    """
    assert (
        get_attribute_access_type(declarative_models.Plain, "stamp") == datetime | None
    )


def test_get_attribute_access_type_declarative_imperative_column(
    declarative_models: types.ModuleType,
) -> None:
    """A column without an annotation has the type of the column's ``python_type``.

    Args:
        declarative_models: The module defining the models.
    """
    imperative = declarative_models.Imperative
    assert get_attribute_access_type(imperative, "doc") == object | None
    assert get_attribute_access_type(imperative, "count") is int
    assert get_attribute_access_type(imperative, "docs") == list | None


class Prefs(TypedDict):
    """The JSON document of a TypedDict-typed column."""

    theme: str
    size: int
    tags: NotRequired[list[str]]


class TypedDictJsonModel(SQLABase):
    """A declarative model with JSON columns typed by a TypedDict."""

    __tablename__ = "typed_dict_json"

    id: Mapped[int] = mapped_column(primary_key=True)
    prefs: Mapped[Prefs] = mapped_column(sqlalchemy.JSON)
    maybe_prefs: Mapped[Prefs | None] = mapped_column(sqlalchemy.JSON, nullable=True)


@pytest.mark.parametrize("column", ["prefs", "maybe_prefs"])
def test_declarative_typed_dict_json_column_key_access(column: str) -> None:
    """Keys of a JSON column annotated with a TypedDict have the TypedDict's types.

    Args:
        column: The JSON column, non-nullable or nullable.
    """
    prefs = getattr(rx.Var(_js_expr="model").to(TypedDictJsonModel), column)
    assert prefs["theme"]._var_type is str
    assert prefs["size"]._var_type is int
    assert prefs["tags"]._var_type == list[str]
    with pytest.raises(VarAttributeError, match="has no attribute 'missing'"):
        prefs["missing"]


class JsonModelClass(rx.Model):
    """Reflex model with a JSON column."""

    profile: dict = sqlmodel.Field(
        default_factory=dict, sa_column=sqlalchemy.Column(JSON)
    )


def test_get_attribute_access_type_rx_model_json_column() -> None:
    """A JSON column of an rx.Model has the type of its sqlmodel annotation."""
    assert get_attribute_access_type(JsonModelClass, "profile") is dict


def test_get_attribute_access_type_rx_model_skips_declarative_column_typing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The DeclarativeBase column typing is unreachable for an rx.Model.

    Args:
        monkeypatch: Fixture to make the DeclarativeBase column typing raise.
    """

    def unreachable(*args: object) -> None:
        msg = "rx.Model columns are not typed by the DeclarativeBase branch"
        raise AssertionError(msg)

    monkeypatch.setattr(types_module, "_get_column_access_type", unreachable)
    assert not issubclass(JsonModelClass, DeclarativeBase)
    assert get_attribute_access_type(JsonModelClass, "profile") is dict
