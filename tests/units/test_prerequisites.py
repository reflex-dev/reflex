import json
import re
import tempfile
from unittest.mock import Mock, mock_open

import pytest

from reflex import constants
from reflex.config import Config
from reflex.utils.prerequisites import (
    CpuInfo,
    _update_next_config,
    cached_procedure,
    get_cpu_info,
    initialize_requirements_txt,
)


@pytest.mark.parametrize(
    "config, export, expected_output",
    [
        (
            Config(
                app_name="test",
            ),
            False,
            'module.exports = {basePath: "", compress: true, reactStrictMode: true, trailingSlash: true};',
        ),
        (
            Config(
                app_name="test",
                next_compression=False,
            ),
            False,
            'module.exports = {basePath: "", compress: false, reactStrictMode: true, trailingSlash: true};',
        ),
        (
            Config(
                app_name="test",
                frontend_path="/test",
            ),
            False,
            'module.exports = {basePath: "/test", compress: true, reactStrictMode: true, trailingSlash: true};',
        ),
        (
            Config(
                app_name="test",
                frontend_path="/test",
                next_compression=False,
            ),
            False,
            'module.exports = {basePath: "/test", compress: false, reactStrictMode: true, trailingSlash: true};',
        ),
        (
            Config(
                app_name="test",
            ),
            True,
            'module.exports = {basePath: "", compress: true, reactStrictMode: true, trailingSlash: true, output: "export", distDir: "_static"};',
        ),
    ],
)
def test_update_next_config(config, export, expected_output):
    output = _update_next_config(config, export=export)
    assert output == expected_output


@pytest.mark.parametrize(
    ("transpile_packages", "expected_transpile_packages"),
    (
        (
            ["foo", "@bar/baz"],
            ["@bar/baz", "foo"],
        ),
        (
            ["foo", "@bar/baz", "foo", "@bar/baz@3.2.1"],
            ["@bar/baz", "foo"],
        ),
    ),
)
def test_transpile_packages(transpile_packages, expected_transpile_packages):
    output = _update_next_config(
        Config(app_name="test"),
        transpile_packages=transpile_packages,
    )
    transpile_packages_match = re.search(r"transpilePackages: (\[.*?\])", output)
    transpile_packages_json = transpile_packages_match.group(1)  # type: ignore
    actual_transpile_packages = sorted(json.loads(transpile_packages_json))
    assert actual_transpile_packages == expected_transpile_packages


def test_initialize_requirements_txt_no_op(mocker):
    # File exists, reflex is included, do nothing
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch(
        "charset_normalizer.from_path",
        return_value=Mock(best=lambda: Mock(encoding="utf-8")),
    )
    mock_fp_touch = mocker.patch("pathlib.Path.touch")
    open_mock = mock_open(read_data="reflex==0.2.9")
    mocker.patch("builtins.open", open_mock)
    initialize_requirements_txt()
    assert open_mock.call_count == 1
    assert open_mock.call_args.kwargs["encoding"] == "utf-8"
    assert open_mock().write.call_count == 0
    mock_fp_touch.assert_not_called()


def test_initialize_requirements_txt_missing_reflex(mocker):
    # File exists, reflex is not included, add reflex
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch(
        "charset_normalizer.from_path",
        return_value=Mock(best=lambda: Mock(encoding="utf-8")),
    )
    open_mock = mock_open(read_data="random-package=1.2.3")
    mocker.patch("builtins.open", open_mock)
    initialize_requirements_txt()
    # Currently open for read, then open for append
    assert open_mock.call_count == 2
    for call_args in open_mock.call_args_list:
        assert call_args.kwargs["encoding"] == "utf-8"
    assert (
        open_mock().write.call_args[0][0]
        == f"\n{constants.RequirementsTxt.DEFAULTS_STUB}{constants.Reflex.VERSION}\n"
    )


def test_initialize_requirements_txt_not_exist(mocker):
    # File does not exist, create file with reflex
    mocker.patch("pathlib.Path.exists", return_value=False)
    open_mock = mock_open()
    mocker.patch("builtins.open", open_mock)
    initialize_requirements_txt()
    assert open_mock.call_count == 2
    # By default, use utf-8 encoding
    for call_args in open_mock.call_args_list:
        assert call_args.kwargs["encoding"] == "utf-8"
    assert open_mock().write.call_count == 1
    assert (
        open_mock().write.call_args[0][0]
        == f"{constants.RequirementsTxt.DEFAULTS_STUB}{constants.Reflex.VERSION}\n"
    )


def test_requirements_txt_cannot_detect_encoding(mocker):
    mocker.patch("pathlib.Path.exists", return_value=True)
    mock_open = mocker.patch("builtins.open")
    mocker.patch(
        "charset_normalizer.from_path",
        return_value=Mock(best=lambda: None),
    )
    initialize_requirements_txt()
    mock_open.assert_not_called()


def test_requirements_txt_other_encoding(mocker):
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch(
        "charset_normalizer.from_path",
        return_value=Mock(best=lambda: Mock(encoding="utf-16")),
    )
    initialize_requirements_txt()
    open_mock = mock_open(read_data="random-package=1.2.3")
    mocker.patch("builtins.open", open_mock)
    initialize_requirements_txt()
    # Currently open for read, then open for append
    assert open_mock.call_count == 2
    for call_args in open_mock.call_args_list:
        assert call_args.kwargs["encoding"] == "utf-16"
    assert (
        open_mock().write.call_args[0][0]
        == f"\n{constants.RequirementsTxt.DEFAULTS_STUB}{constants.Reflex.VERSION}\n"
    )


def test_cached_procedure():
    call_count = 0

    @cached_procedure(tempfile.mktemp(), payload_fn=lambda: "constant")
    def _function_with_no_args():
        nonlocal call_count
        call_count += 1

    _function_with_no_args()
    assert call_count == 1
    _function_with_no_args()
    assert call_count == 1

    call_count = 0

    @cached_procedure(
        tempfile.mktemp(),
        payload_fn=lambda *args, **kwargs: f"{repr(args), repr(kwargs)}",
    )
    def _function_with_some_args(*args, **kwargs):
        nonlocal call_count
        call_count += 1

    _function_with_some_args(1, y=2)
    assert call_count == 1
    _function_with_some_args(1, y=2)
    assert call_count == 1
    _function_with_some_args(100, y=300)
    assert call_count == 2
    _function_with_some_args(100, y=300)
    assert call_count == 2


def test_get_cpu_info():
    cpu_info = get_cpu_info()
    assert cpu_info is not None
    assert isinstance(cpu_info, CpuInfo)
    assert cpu_info.model_name is not None

    for attr in ("manufacturer_id", "model_name", "address_width"):
        value = getattr(cpu_info, attr)
        assert value.strip() if attr != "address_width" else value
