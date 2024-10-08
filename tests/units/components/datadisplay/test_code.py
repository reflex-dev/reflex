import pytest

from reflex.components.datadisplay.code import CodeBlock, Theme


@pytest.mark.parametrize(
    "theme, expected",
    [(Theme.one_light, "oneLight"), (Theme.one_dark, "oneDark")],
)
def test_code_light_dark_theme(theme, expected):
    code_block = CodeBlock.create(theme=theme)

    assert code_block.theme._js_expr == expected  # type: ignore


def generate_custom_code(language, expected_case):
    return f"SyntaxHighlighter.registerLanguage('{language}', {expected_case})"


@pytest.mark.parametrize(
    "language, expected_case",
    [
        ("python", "python"),
        ("firestore-security-rules", "firestoreSecurityRules"),
        ("typescript", "typescript"),
    ],
)
def test_get_custom_code(language, expected_case):
    code_block = CodeBlock.create(language=language)
    assert code_block._get_custom_code() == generate_custom_code(
        language, expected_case
    )
