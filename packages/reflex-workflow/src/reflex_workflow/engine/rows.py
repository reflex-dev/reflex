"""Helpers for addressing and diffing workflow rows."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Mapper, class_mapper

from reflex_workflow.model import WORKFLOW_COLUMNS, Workflow

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement


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


def pk_filter(cls: type[Workflow], pk: Sequence[Any]) -> list[ColumnElement[bool]]:
    """Build the condition that selects one row by primary key.

    Args:
        cls: The workflow class.
        pk: The row's primary key values.

    Returns:
        One equality condition per key column.
    """
    return [
        getattr(cls, key) == value for key, value in zip(pk_keys(cls), pk, strict=True)
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
