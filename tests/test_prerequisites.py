from unittest.mock import mock_open

import pytest

from reflex import constants
from reflex.config import Config
from reflex.utils.prerequisites import _update_next_config, initialize_requirements_txt


@pytest.mark.parametrize(
    "input, config, export, expected_output",
    [
        (
            """
                module.exports = {
                    basePath: "",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
                    output: "",
                };
            """,
            Config(
                app_name="test",
            ),
            False,
            """
                module.exports = {
                    basePath: "",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
                    output: "",
                };
            """,
        ),
        (
            """
                module.exports = {
                    basePath: "",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
                    output: "",
                };
            """,
            Config(
                app_name="test",
                next_compression=False,
            ),
            False,
            """
                module.exports = {
                    basePath: "",
                    compress: false,
                    reactStrictMode: true,
                    trailingSlash: true,
                    output: "",
                };
            """,
        ),
        (
            """
                module.exports = {
                    basePath: "",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
                    output: "",
                };
            """,
            Config(
                app_name="test",
                frontend_path="/test",
            ),
            False,
            """
                module.exports = {
                    basePath: "/test",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
                    output: "",
                };
            """,
        ),
        (
            """
                module.exports = {
                    basePath: "",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
                    output: "",
                };
            """,
            Config(
                app_name="test",
                frontend_path="/test",
                next_compression=False,
            ),
            False,
            """
                module.exports = {
                    basePath: "/test",
                    compress: false,
                    reactStrictMode: true,
                    trailingSlash: true,
                    output: "",
                };
            """,
        ),
        (
            """
                module.exports = {
                    basePath: "",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
                    output: "",
                };
            """,
            Config(
                app_name="test",
            ),
            True,
            """
                module.exports = {
                    basePath: "",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
                    output: "export",
                };
            """,
        ),
    ],
)
def test_update_next_config(input, config, export, expected_output):
    output = _update_next_config(input, config, export=export)
    assert output == expected_output

    if export:
        assert _update_next_config(output, config) == input


def test_initialize_requirements_txt(mocker):
    # File exists, reflex is included, do nothing
    mocker.patch("os.path.exists", return_value=True)
    open_mock = mock_open(read_data="reflex==0.2.9")
    mocker.patch("builtins.open", open_mock)
    initialize_requirements_txt()
    assert open_mock.call_count == 1
    assert open_mock().write.call_count == 0


def test_initialize_requirements_txt_missing_reflex(mocker):
    # File exists, reflex is not included, add reflex
    open_mock = mock_open(read_data="random-package=1.2.3")
    mocker.patch("builtins.open", open_mock)
    initialize_requirements_txt()
    # Currently open for read, then open for append
    assert open_mock.call_count == 2
    assert open_mock().write.call_count == 1
    assert (
        open_mock().write.call_args[0][0]
        == f"\n{constants.RequirementsTxt.DEFAULTS_STUB}{constants.Reflex.VERSION}\n"
    )


def test_initialize_requirements_txt_not_exist(mocker):
    # File does not exist, create file with reflex
    mocker.patch("os.path.exists", return_value=False)
    open_mock = mock_open()
    mocker.patch("builtins.open", open_mock)
    initialize_requirements_txt()
    assert open_mock.call_count == 2
    assert open_mock().write.call_count == 1
    assert (
        open_mock().write.call_args[0][0]
        == f"\n{constants.RequirementsTxt.DEFAULTS_STUB}{constants.Reflex.VERSION}\n"
    )
