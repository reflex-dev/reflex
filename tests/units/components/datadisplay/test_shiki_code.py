import pytest
from reflex_base.style import Style
from reflex_base.vars import Var
from reflex_base.vars.base import LiteralVar
from reflex_components_code.shiki_code_block import (
    ShikiBaseTransformers,
    ShikiCodeBlock,
    ShikiHighLevelCodeBlock,
    ShikiJsTransformer,
)
from reflex_components_core.el.elements.forms import Button
from reflex_components_lucide.icon import Icon
from reflex_components_radix.themes.layout.box import Box


@pytest.mark.parametrize(
    ("library", "fns", "expected_output", "raises_exception"),
    [
        ("some_library", ["function_one"], ["function_one"], False),
        ("some_library", [123], None, True),
        ("some_library", [], [], False),
        (
            "some_library",
            ["function_one", "function_two"],
            ["function_one", "function_two"],
            False,
        ),
        ("", ["function_one"], ["function_one"], False),
        ("some_library", ["function_one", 789], None, True),
        ("", [], [], False),
    ],
)
def test_create_transformer(library, fns, expected_output, raises_exception):
    if raises_exception:
        # Ensure ValueError is raised for invalid cases
        with pytest.raises(ValueError):
            ShikiCodeBlock.create_transformer(library, fns)
    else:
        transformer = ShikiCodeBlock.create_transformer(library, fns)
        assert isinstance(transformer, ShikiBaseTransformers)
        assert transformer.library == library

        # Verify that the functions are correctly wrapped in FunctionStringVar
        function_names = [str(fn) for fn in transformer.fns]
        assert function_names == expected_output


@pytest.mark.parametrize(
    ("code_block", "children", "props", "expected_first_child", "expected_styles"),
    [
        ("print('Hello')", ["print('Hello')"], {}, "print('Hello')", {}),
        (
            "print('Hello')",
            ["print('Hello')", "More content"],
            {},
            "print('Hello')",
            {},
        ),
        (
            "print('Hello')",
            ["print('Hello')"],
            {
                "transformers": [
                    ShikiBaseTransformers(
                        library="lib", fns=[], style=Style({"color": "red"})
                    )
                ]
            },
            "print('Hello')",
            {"color": "red"},
        ),
        (
            "print('Hello')",
            ["print('Hello')"],
            {
                "transformers": [
                    ShikiBaseTransformers(
                        library="lib", fns=[], style=Style({"color": "red"})
                    )
                ],
                "style": {"background": "blue"},
            },
            "print('Hello')",
            {"color": "red", "background": "blue"},
        ),
    ],
)
def test_create_shiki_code_block(
    code_block, children, props, expected_first_child, expected_styles
):
    component = ShikiCodeBlock.create(code_block, *children, **props)

    # Test that the created component is a Box
    assert isinstance(component, Box)

    # Test that the first child is the code
    code_block_component = component.children[0]
    assert code_block_component.code._var_value == expected_first_child  # ty:ignore[unresolved-attribute]

    applied_styles = component.style
    for key, value in expected_styles.items():
        var = Var.create(applied_styles[key])
        assert isinstance(var, LiteralVar)
        assert var._var_value == value


@pytest.mark.parametrize(
    ("children", "props", "expected_transformers", "expected_button_type"),
    [
        (["print('Hello')"], {"use_transformers": True}, [ShikiJsTransformer], None),
        (["print('Hello')"], {"can_copy": True}, None, Button),
        (
            ["print('Hello')"],
            {
                "can_copy": True,
                "copy_button": Button.create(Icon.create(tag="a_arrow_down")),
            },
            None,
            Button,
        ),
    ],
)
def test_create_shiki_high_level_code_block(
    children, props, expected_transformers, expected_button_type
):
    component = ShikiHighLevelCodeBlock.create(*children, **props)

    # Test that the created component is a Box
    assert isinstance(component, Box)

    # Test that the first child is the code block component
    code_block_component = component.children[0]
    assert code_block_component.code._var_value == children[0]  # ty:ignore[unresolved-attribute]

    # Check if the transformer is set correctly if expected
    if expected_transformers:
        exp_trans_names = [t.__name__ for t in expected_transformers]
        for transformer in code_block_component.transformers._var_value:  # ty:ignore[unresolved-attribute]
            assert type(transformer).__name__ in exp_trans_names

    # Check if the second child is the copy button if can_copy is True
    if props.get("can_copy", False):
        if props.get("copy_button"):
            assert isinstance(component.children[1], expected_button_type)
            assert component.children[1] == props["copy_button"]
        else:
            assert isinstance(component.children[1], expected_button_type)
    else:
        assert len(component.children) == 1


@pytest.mark.parametrize(
    ("children", "props"),
    [
        (["print('Hello')"], {"theme": "dark"}),
        (["print('Hello')"], {"language": "javascript"}),
    ],
)
def test_shiki_high_level_code_block_theme_language_mapping(children, props):
    component = ShikiHighLevelCodeBlock.create(*children, **props)

    # Test that the theme is mapped correctly
    if "theme" in props:
        assert component.children[
            0
        ].theme._var_value == ShikiHighLevelCodeBlock._map_themes(props["theme"])  # ty:ignore[unresolved-attribute]

    # Test that the language is mapped correctly
    if "language" in props:
        assert component.children[
            0
        ].language._var_value == ShikiHighLevelCodeBlock._map_languages(  # ty:ignore[unresolved-attribute]
            props["language"]
        )
