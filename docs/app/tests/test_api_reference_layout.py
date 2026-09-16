"""Tests for the shared API reference layout."""

import pytest
import reflex as rx
from reflex_docgen import MethodDocumentation, generate_class_documentation

from reflex_docs.pages.docs.api_reference_layout import (
    generate_class_reference,
    method_details,
    multiline_signature,
)


def test_long_signature_wraps_parameters_without_splitting_nested_types():
    """Commas inside type arguments and string defaults remain intact."""
    method = MethodDocumentation(
        name="example",
        signature="(values: dict[str, tuple[int, str]], callback: Callable[[int, str], None], label: str = 'one,two') -> None",
        description="",
    )
    rendered = multiline_signature(method)
    assert "    values: dict[str, tuple[int, str]],\n" in rendered
    assert "    callback: Callable[[int, str], None],\n" in rendered
    assert "    label: str = 'one,two',\n) -> None" in rendered


@pytest.mark.parametrize(
    "cls", [rx.App, rx.Component, rx.ComponentState, rx.Config, rx.State, rx.Var]
)
def test_reference_navigation_has_matching_member_anchors(cls):
    """Every generated field and method can be linked directly."""
    toc, content = generate_class_reference(cls)
    rendered = str(content)
    doc = generate_class_documentation(cls)
    assert [title for level, title in toc if level == 3] == [
        *(field.name for field in doc.class_fields),
        *(field.name for field in doc.fields),
        *(method.name for method in doc.methods),
    ]
    for level, title in toc:
        if level == 3:
            assert f'id:"{title.lower()}"' in rendered
            assert f'to:"#{title.lower()}"' in rendered


def test_method_details_preserve_parameter_and_return_documentation():
    """Keep source sections omitted by the old summary table."""
    methods = {
        method.name: method for method in generate_class_documentation(rx.App).methods
    }
    add_page = str(method_details(rx.App, methods["add_page"]))
    assert "Parameters" in add_page
    assert "The component to display at the page." in add_page
    assert "Raises" in add_page
    assert "RouteValueError" in add_page
    contexts = str(method_details(rx.App, methods["set_contexts"]))
    assert "Returns" in contexts
    assert (
        "A context manager that resets any contexts that were set on exit." in contexts
    )


def test_config_preserves_environment_variable_metadata():
    """Config rows retain their generated environment variable names."""
    _, component = generate_class_reference(rx.Config, env_var_prefix="REFLEX_")
    assert "REFLEX_FRONTEND_PORT" in str(component)


def test_methods_only_reference_has_no_empty_fields_section():
    """Do not add empty section headings when a class has only methods."""
    toc, _ = generate_class_reference(rx.Var)
    assert (2, "Fields") not in toc
    assert (2, "Methods") in toc


def test_environment_variables_use_shared_fields_and_member_navigation():
    """Environment references preserve names, defaults, and deep links."""
    from reflex_docs.pages.docs.env_vars import EnvVarDocs, env_vars_page

    fields = EnvVarDocs.get_documented_fields()
    toc, page = env_vars_page()
    rendered = str(page)
    assert fields
    for field in fields:
        assert (3, field.name) in toc
        assert f'id:"{field.name.lower()}"' in rendered
    assert "Default: " in rendered
