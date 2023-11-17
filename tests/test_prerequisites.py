import pytest

from reflex.config import Config
from reflex.utils.prerequisites import _update_next_config


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
