from unittest.mock import mock_open

import pytest

from reflex import constants
from reflex.config import Config
from reflex.utils.prerequisites import (
    initialize_requirements_txt,
    install_node,
    update_next_config,
)


@pytest.mark.parametrize(
    "template_next_config, reflex_config, expected_next_config",
    [
        (
            """
                module.exports = {
                    basePath: "",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
                };
            """,
            Config(
                app_name="test",
            ),
            """
                module.exports = {
                    basePath: "",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
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
                };
            """,
            Config(
                app_name="test",
                next_compression=False,
            ),
            """
                module.exports = {
                    basePath: "",
                    compress: false,
                    reactStrictMode: true,
                    trailingSlash: true,
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
                };
            """,
            Config(
                app_name="test",
                frontend_path="/test",
            ),
            """
                module.exports = {
                    basePath: "/test",
                    compress: true,
                    reactStrictMode: true,
                    trailingSlash: true,
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
                };
            """,
            Config(
                app_name="test",
                frontend_path="/test",
                next_compression=False,
            ),
            """
                module.exports = {
                    basePath: "/test",
                    compress: false,
                    reactStrictMode: true,
                    trailingSlash: true,
                };
            """,
        ),
    ],
)
def test_update_next_config(template_next_config, reflex_config, expected_next_config):
    assert (
        update_next_config(template_next_config, reflex_config) == expected_next_config
    )


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


@pytest.mark.parametrize(
    "is_windows, is_linux, release, expected",
    [
        (True, False, "10.0.20348", True),
        (False, True, "6.2.0-1015-azure", False),
        (False, True, "4.4.0-17763-Microsoft", True),
        (False, False, "21.6.0", False),
    ],
)
def test_install_node(is_windows, is_linux, release, expected, mocker):
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", is_windows)
    mocker.patch("reflex.utils.prerequisites.constants.IS_LINUX", is_linux)
    mocker.patch("reflex.utils.prerequisites.platform.release", return_value=release)
    mocker.patch("reflex.utils.prerequisites.download_and_extract_fnm_zip")
    mocker.patch("reflex.utils.prerequisites.processes.new_process")
    mocker.patch("reflex.utils.prerequisites.processes.show_status")
    mocker.patch("reflex.utils.prerequisites.os.chmod")

    path_ops = mocker.patch("reflex.utils.prerequisites.path_ops.mkdir")
    install_node()
    if expected:
        path_ops.assert_called_once()
    else:
        path_ops.assert_not_called()
