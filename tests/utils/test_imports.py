import pytest

from reflex.utils.imports import ImportVar, merge_imports


@pytest.mark.parametrize(
    "import_var, expected_name",
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
    ],
)
def test_import_var(import_var, expected_name):
    """Test that the import var name is computed correctly.

    Args:
        import_var: The import var.
        expected_name: The expected name.
    """
    assert import_var.name == expected_name


@pytest.mark.parametrize(
    "input_1, input_2, output",
    [
        (
            {"react": {"Component"}},
            {"react": {"Component"}, "react-dom": {"render"}},
            {"react": {"Component"}, "react-dom": {"render"}},
        ),
        (
            {"react": {"Component"}, "next/image": {"Image"}},
            {"react": {"Component"}, "react-dom": {"render"}},
            {"react": {"Component"}, "react-dom": {"render"}, "next/image": {"Image"}},
        ),
        (
            {"react": {"Component"}},
            {"": {"some/custom.css"}},
            {"react": {"Component"}, "": {"some/custom.css"}},
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
    assert set(res.keys()) == set(output.keys())

    for key in output:
        assert set(res[key]) == set(output[key])
