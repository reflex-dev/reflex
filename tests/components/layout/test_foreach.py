import pytest
import pytest_mock

from pynecone.components.layout import foreach
from pynecone.components.typography import text

MOCKED_VAR_NAME = "abc"


@pytest.mark.parametrize(
    "_render_kwargs, expected_render",
    [
        pytest.param(
            {"wrapped_with_bracket": True},
            f'{{["Tommy", "coding", "at", "home"].map(({MOCKED_VAR_NAME}, i) => <Text key={{i}}>{{{MOCKED_VAR_NAME}}}</Text>)}}',
            id="wrapped_with_bracket True",
        ),
        pytest.param(
            {"wrapped_with_bracket": False},
            f'["Tommy", "coding", "at", "home"].map(({MOCKED_VAR_NAME}, i) => <Text key={{i}}>{{{MOCKED_VAR_NAME}}}</Text>)',
            id="wrapped_with_bracket False",
        ),
        pytest.param(
            {},
            f'{{["Tommy", "coding", "at", "home"].map(({MOCKED_VAR_NAME}, i) => <Text key={{i}}>{{{MOCKED_VAR_NAME}}}</Text>)}}',
            id="no kwargs",
        ),
    ],
)
def test_foreach_render(
    mocker: pytest_mock.MockFixture, _render_kwargs: dict, expected_render: str
):
    mocker.patch(
        "pynecone.utils.get_unique_variable_name",
        return_value=MOCKED_VAR_NAME,
    )

    foreach_component = foreach.Foreach.create(
        ["Tommy", "coding", "at", "home"],  # pyright: reportGeneralTypeIssues=false
        lambda x: text.Text.create(x),
    )

    assert foreach_component.render(**_render_kwargs) == expected_render
