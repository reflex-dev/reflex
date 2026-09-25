"""Helpers for addressing and diffing workflow rows."""

from __future__ import annotations

import copy
import datetime
import decimal
import math
import uuid
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, NamedTuple

from sqlalchemy.orm import Mapper, class_mapper

from reflex_workflow.model import WORKFLOW_COLUMNS, Workflow

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement


class KeyForm(NamedTuple):
    """How one kind of primary key value crosses into jsonb and back.

    Attributes:
        store: Turns the value into something json holds.
        load: Turns what was stored back into what the column compares against.
    """

    store: Callable[[Any], Any]
    load: Callable[[Any], Any]


# The key types json has no form of. Whatever else a key column holds -- an int,
# a string -- json holds as it stands.
KEY_FORMS: dict[type, KeyForm] = {
    uuid.UUID: KeyForm(str, uuid.UUID),
    datetime.datetime: KeyForm(
        datetime.datetime.isoformat, datetime.datetime.fromisoformat
    ),
    datetime.date: KeyForm(datetime.date.isoformat, datetime.date.fromisoformat),
    datetime.time: KeyForm(datetime.time.isoformat, datetime.time.fromisoformat),
    decimal.Decimal: KeyForm(str, decimal.Decimal),
    bytes: KeyForm(bytes.hex, bytes.fromhex),
}


def mapper(cls: type[Workflow]) -> Mapper[Any]:
    """Return a workflow class's SQLAlchemy mapper.

    Args:
        cls: The workflow class.

    Returns:
        Its mapper.
    """
    return class_mapper(cls)


def pk_keys(cls: type[Workflow]) -> list[str]:
    """Return the attribute names of a workflow's primary key.

    Args:
        cls: The workflow class.

    Returns:
        The primary key attribute names, in key order.
    """
    cls_mapper = mapper(cls)
    return [
        cls_mapper.get_property_by_column(col).key for col in cls_mapper.primary_key
    ]


def pk_of(row: Workflow) -> list[Any]:
    """Return a row's own primary key values, in key order.

    Args:
        row: The row.

    Returns:
        The values.
    """
    return [getattr(row, key) for key in pk_keys(type(row))]


def json_pk(pk: Sequence[Any]) -> list[Any]:
    """Return a primary key in the form the engine's jsonb columns hold it.

    A key is written into a child's parent pointer and into the attempt history,
    both jsonb, so a value json has no form of -- a UUID, a datetime -- is stored
    as the text it reads back from.

    Args:
        pk: The row's primary key values.

    Returns:
        One json-safe value per key column.

    Raises:
        TypeError: If a key column holds a value the engine cannot store.
    """
    stored: list[Any] = []
    for value in pk:
        if isinstance(value, float) and not math.isfinite(value):
            # As in a step's arguments: NaN and infinity are not json, and
            # Postgres refuses them in jsonb.
            msg = (
                f"A workflow's primary key cannot be {value}: the engine records "
                "keys in its history and fan-out columns as json, which has no "
                "form for it."
            )
            raise TypeError(msg)
        if value is None or isinstance(value, (str, int, float)):
            stored.append(value)
            continue
        form = next(
            (KEY_FORMS[kind] for kind in type(value).__mro__ if kind in KEY_FORMS), None
        )
        if form is None:
            msg = (
                f"A workflow's primary key cannot be a {type(value).__name__}: the "
                "engine records keys in its history and fan-out columns as json."
            )
            raise TypeError(msg)
        stored.append(form.store(value))
    return stored


def loaded_key(column: ColumnElement[Any], value: Any) -> Any:
    """Return a stored key value in the form its own column compares against.

    Args:
        column: The key column.
        value: The value, as a pointer stored it or as the database returned it.

    Returns:
        The value to compare the column with.
    """
    try:
        kind = column.type.python_type
    except NotImplementedError:
        # A type that does not say what it holds; it was stored as it stood.
        return value
    if isinstance(value, kind):
        return value
    form = KEY_FORMS.get(kind)
    return form.load(value) if form is not None else value


def pk_filter(cls: type[Workflow], pk: Sequence[Any]) -> list[ColumnElement[bool]]:
    """Build the condition that selects one row by primary key.

    Args:
        cls: The workflow class.
        pk: The row's primary key values, as claimed or as a pointer stored them.

    Returns:
        One equality condition per key column.
    """
    cls_mapper = mapper(cls)
    return [
        getattr(cls, cls_mapper.get_property_by_column(column).key)
        == loaded_key(column, value)
        for column, value in zip(cls_mapper.primary_key, pk, strict=True)
    ]


def user_columns(cls: type[Workflow]) -> list[str]:
    """Return the columns a step may change: everything but the key and the mixin's.

    Args:
        cls: The workflow class.

    Returns:
        The attribute names.
    """
    pk = set(pk_keys(cls))
    return [
        attr.key
        for attr in mapper(cls).column_attrs
        if attr.key not in WORKFLOW_COLUMNS and attr.key not in pk
    ]


def snapshot(row: Workflow, columns: list[str]) -> dict[str, Any]:
    """Copy a row's column values, so later in-place mutations can be detected.

    Args:
        row: The row.
        columns: The attribute names to copy.

    Returns:
        The copied values.
    """
    return {key: copy.deepcopy(getattr(row, key)) for key in columns}
