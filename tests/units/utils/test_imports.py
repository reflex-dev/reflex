from typing import cast

import pytest
from reflex_base.utils.imports import (
    ImmutableImportDict,
    ImportDict,
    ImportVar,
    ParsedImportDict,
    _sort_key,
    collapse_imports,
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


def test_merge_imports_deduplicates():
    """A tag merged from many subtrees is carried once, not once per subtree.

    `_get_all_imports` merges every descendant's imports on the way up, so
    without this a node's list grows with the size of its subtree rather than
    with the number of distinct imports it has.
    """
    one: ImportDict = {"react": ["Component"]}
    merged = merge_imports(*([one] * 50))

    assert merged["react"] == [ImportVar("Component")]


def test_merge_parsed_imports_deduplicates():
    one: ParsedImportDict = {"react": [ImportVar("Component"), ImportVar("useState")]}
    merged = merge_parsed_imports(*([one] * 50))

    assert merged["react"] == [ImportVar("Component"), ImportVar("useState")]


def test_merge_imports_keeps_first_seen_order():
    merged = merge_imports(
        {"react": ["useMemo", "Component"]},
        {"react": ["useState", "Component"]},
    )

    assert merged["react"] == [
        ImportVar("useMemo"),
        ImportVar("Component"),
        ImportVar("useState"),
    ]


def test_collapse_imports_is_order_preserving():
    """Collapsing must not depend on PYTHONHASHSEED.

    `list(set(...))` made import order vary per process, and memo names are
    hashed from that order, so two compiles of identical source disagreed.
    """
    tags = [f"Tag{i:02d}" for i in range(30)]
    collapsed = collapse_imports({"react": [ImportVar(tag) for tag in tags] * 3})

    assert collapsed["react"] == [ImportVar(tag) for tag in tags]


def test_merge_deduplicates_within_a_single_batch():
    """A library carried by one dict only is still deduplicated against itself.

    The accumulator skips the lookup set for a library's first batch, since
    there is nothing accumulated to collide with. That batch can still repeat a
    tag internally, and on a real app 465 of 966,807 first batches did.
    """
    merged = merge_imports({"react": ["Component", "useState", "Component"]})
    assert merged["react"] == [ImportVar("Component"), ImportVar("useState")]

    parsed = merge_parsed_imports({
        "react": [ImportVar("Component"), ImportVar("useState"), ImportVar("Component")]
    })
    assert parsed["react"] == [ImportVar("Component"), ImportVar("useState")]


def test_a_set_of_imports_is_given_a_deterministic_order():
    """A `set` iterates by PYTHONHASHSEED, and the merge preserves what it gets.

    Both entry points accept one -- `merge_imports` by an isinstance check and
    `parse_imports` by iterating whatever it is handed -- so a set left
    untouched would put the hash seed back into the emitted imports and into
    every component hash derived from them.
    """
    tags = {f"Tag{i:02d}" for i in range(20)}
    ordered = [ImportVar(tag) for tag in sorted(tags)]
    # Cast because a set is not in `ImportTypes`, yet both functions accept one
    # at runtime and untyped callers do pass them.
    batch = {"react": tags}

    assert merge_imports(cast("ImportDict", batch))["react"] == ordered
    assert parse_imports(cast("ImmutableImportDict", batch))["react"] == ordered


def test_the_sort_key_separates_every_distinct_import_var():
    """A collision would leave that pair in whatever order the set produced.

    Sorting is stable, so two vars sharing a key keep their input order, and for
    a set that order is the hash seed's. Stringifying the fields collided
    `tag=None` with `tag="None"`, and `install=None` with `install=False`.
    """
    variants = {
        ImportVar(tag=None),
        ImportVar(tag="None"),
        ImportVar(tag=""),
        ImportVar(tag="x", alias=None),
        ImportVar(tag="x", alias="None"),
        ImportVar(tag="x", is_default=None),
        ImportVar(tag="x", is_default=False),
        ImportVar(tag="x", is_default=True),
        ImportVar(tag="x", install=None),
        ImportVar(tag="x", install=False),
        ImportVar(tag="x", render=None),
        ImportVar(tag="x", render=False),
        ImportVar(tag="x", package_path="/other"),
    }

    assert len({_sort_key(var) for var in variants}) == len(variants)


def test_collapse_imports_preserves_order():
    """Deduplication must preserve first-occurrence order.

    Compiled JSX import order follows this ordering; a hash-seed-dependent
    order rewrites every page/memo file on each dev reload and breaks
    granular HMR.
    """
    import_vars = [
        ImportVar(tag=f"Icon{i}", is_default=True, package_path=f"/Icon{i}")
        for i in range(32)
    ]
    duplicated = [*import_vars, *import_vars[:5], import_vars[0]]
    collapsed = collapse_imports({"@hugeicons/core-free-icons": duplicated})
    assert collapsed == {"@hugeicons/core-free-icons": import_vars}
    # Tuple-valued entries (already-immutable parsed imports) keep order too.
    collapsed_tuple = collapse_imports((
        ("@hugeicons/core-free-icons", tuple(duplicated)),
    ))
    assert collapsed_tuple == {"@hugeicons/core-free-icons": import_vars}
