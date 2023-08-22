import pytest

from reflex.config import Config
from reflex.utils.prerequisites import update_next_config


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
