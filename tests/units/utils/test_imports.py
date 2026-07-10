import pytest
from reflex_base.utils.imports import (
    ImportDict,
    ImportVar,
    ParsedImportDict,
    merge_imports,
    merge_parsed_imports,
    parse_imports,
)


@pytest.mark.parametrize(
    ("import_var", "expected_name"),
    [
        (
            ImportVar(tag="BaseTag"),
            "BaseTag",
        ),
        (
            ImportVar(tag="BaseTag", alias="AliasTag"),
            "BaseTag as AliasTag",
        ),
        (
            ImportVar(tag="BaseTag", is_default=True),
            "BaseTag",
        ),
        (
            ImportVar(tag="BaseTag", is_default=True, alias="AliasTag"),
            "AliasTag",
        ),
        (
            ImportVar(tag="BaseTag", is_default=False),
            "BaseTag",
        ),
        (
            ImportVar(tag="BaseTag", is_default=False, alias="AliasTag"),
            "BaseTag as AliasTag",
        ),
        (
            ImportVar(tag="*", alias="AliasTag"),
            "* as AliasTag",
        ),
    ],
)
def test_import_var(import_var: ImportVar, expected_name: str):
    """Test that the import var name is computed correctly.

    Args:
        import_var: The import var.
        expected_name: The expected name.
    """
    assert import_var.name == expected_name


@pytest.mark.parametrize(
    ("input_1", "input_2", "output"),
    [
        (
            {"react": {"Component"}},
            {"react": {"Component"}, "react-dom": {"render"}},
            {"react": {ImportVar("Component")}, "react-dom": {ImportVar("render")}},
        ),
        (
            {"react": {"Component"}, "next/image": {"Image"}},
            {"react": {"Component"}, "react-dom": {"render"}},
            {
                "react": {ImportVar("Component")},
                "react-dom": {ImportVar("render")},
                "next/image": {ImportVar("Image")},
            },
        ),
        (
            {"react": {"Component"}},
            {"": {"some/custom.css"}},
            {"react": {ImportVar("Component")}, "": {ImportVar("some/custom.css")}},
        ),
    ],
)
def test_merge_imports(input_1, input_2, output):
    """Test that imports are merged correctly.

    Args:
        input_1: The first dict to merge.
        input_2: The second dict to merge.
        output: The expected output dict after merging.

    """
    res = merge_imports(input_1, input_2)
    assert res.keys() == output.keys()

    for key in output:
        assert set(res[key]) == set(output[key])


def test_merge_imports_dedups_duplicates():
    """Duplicate ImportVars collapse to one entry, preserving first-seen order.

    Regression: without dedup, chained var operations (which merge the same
    operand imports via both ``_args`` and ``_return``) doubled the entry
    count per nesting level.
    """
    merged = merge_imports(
        {"react": ["useEffect", "useState", "useEffect"]},
        {"react": ["useState", "useMemo"]},
    )
    assert merged["react"] == [
        ImportVar(tag="useEffect"),
        ImportVar(tag="useState"),
        ImportVar(tag="useMemo"),
    ]


def test_merge_imports_keeps_distinct_fields():
    """Entries differing in any field (e.g. alias) are not collapsed."""
    parsed = {"react": [ImportVar(tag="useEffect"), ImportVar(tag="useState")]}
    aliased = {"react": [ImportVar(tag="useEffect", alias="effectAlias")]}
    merged = merge_imports(parsed, aliased)
    assert merged["react"] == [
        ImportVar(tag="useEffect"),
        ImportVar(tag="useState"),
        ImportVar(tag="useEffect", alias="effectAlias"),
    ]


def test_merge_parsed_imports_concatenates():
    """The component-tree fold concatenates without dedup (collapsed later)."""
    parsed = {"react": [ImportVar(tag="useEffect")]}
    merged = merge_parsed_imports(parsed, parsed)
    assert merged["react"] == [ImportVar(tag="useEffect"), ImportVar(tag="useEffect")]


@pytest.mark.parametrize(
    ("input", "output"),
    [
        ({}, {}),
        (
            {"react": "Component"},
            {"react": [ImportVar(tag="Component")]},
        ),
        (
            {"react": ["Component"]},
            {"react": [ImportVar(tag="Component")]},
        ),
        (
            {"react": ["Component", ImportVar(tag="useState")]},
            {"react": [ImportVar(tag="Component"), ImportVar(tag="useState")]},
        ),
        (
            {"react": ["Component"], "foo": "anotherFunction"},
            {
                "react": [ImportVar(tag="Component")],
                "foo": [ImportVar(tag="anotherFunction")],
            },
        ),
    ],
)
def test_parse_imports(input: ImportDict, output: ParsedImportDict):
    assert parse_imports(input) == output
