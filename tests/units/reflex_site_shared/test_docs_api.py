"""Tests for shared documentation API tables."""

import pytest
from reflex_site_shared.components.docs_api import (
    callable_api_reference,
    docs_api_cell,
    docs_api_row,
    docs_api_table,
)

import reflex as rx


def documented_factory(
    value: str,
    *,
    count: int = 3,
) -> dict[str, object]:
    """Build a documented value.

    Args:
        value: Required source value.
        count: Number of copies to produce.

    Returns:
        Generated value mapping.
    """
    return {"value": value, "count": count}


def variadic_factory(*children: object, **tokens: object) -> None:
    """Accept extensible component inputs."""


_OPAQUE_DEFAULT = object()


def opaque_default_factory(value: object = _OPAQUE_DEFAULT) -> None:
    """Accept a value with an implementation-owned default."""


def undocumented_required_factory(value: object) -> None:
    """Accept a required value without an Args section."""


def test_callable_api_reference_uses_signature_and_docstring() -> None:
    """Generate table rows from the callable's source-of-truth metadata."""
    rendered = str(
        callable_api_reference(
            documented_factory,
            display_name="api.factory",
            exclude_parameters=("count",),
        )
    )

    assert "api.factory" in rendered
    assert "value" in rendered
    assert "Required source value." in rendered
    assert "Number of copies to produce." not in rendered


def test_callable_api_reference_describes_variadics_and_slugs_heading_id() -> None:
    """Avoid marking variadic extension points required and emit safe anchors."""
    rendered = str(
        callable_api_reference(
            variadic_factory,
            display_name="Shared chart props",
        )
    )

    assert "Additional positional arguments." in rendered
    assert "Additional keyword arguments." in rendered
    assert "Required." not in rendered
    assert 'id:"shared-chart-props"' in rendered


def test_callable_api_reference_does_not_mark_opaque_defaults_required() -> None:
    """Keep optional parameters optional when their default repr is unstable."""
    rendered = str(callable_api_reference(opaque_default_factory))

    assert "Optional." in rendered
    assert "Required." not in rendered


def test_callable_api_reference_still_marks_missing_defaults_required() -> None:
    """Preserve required labels for parameters without a default."""
    rendered = str(callable_api_reference(undocumented_required_factory))

    assert "Required." in rendered


def test_docs_api_table_rejects_mismatched_columns() -> None:
    """Reject malformed table configurations before rendering."""
    with pytest.raises(ValueError, match="matching lengths"):
        docs_api_table(headers=("Only",), widths=("w-1", "w-2"))


def test_docs_api_table_preserves_official_table_styles() -> None:
    """Keep the shared shell pixel-compatible with the official props table."""
    rendered = str(
        docs_api_table(
            docs_api_row(docs_api_cell(rx.text("value"), "w-[20%]")),
        )
    )

    assert "border-b border-secondary-4 bg-secondary-2" in rendered
    assert "px-4 py-3 text-left text-xs font-semibold text-secondary-11" in rendered
    assert "min-w-0 px-4 py-3 align-top w-[20%]" in rendered
    assert "w-[20%]" in rendered
    assert "w-[25%]" in rendered
    assert "w-[55%]" in rendered
    assert (
        "rounded-xl border border-secondary-4 bg-secondary-1 shadow-small" in rendered
    )
