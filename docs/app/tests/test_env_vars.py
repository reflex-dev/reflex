"""Tests for the environment variables reference page."""

from reflex_base.environment import EnvironmentVariables


def test_page_names_the_module_the_class_is_defined_in():
    """The page shows where EnvironmentVariables lives, not a re-export path."""
    from reflex_docs.pages.docs.env_vars import env_vars_page

    _toc, page = env_vars_page()
    rendered = str(page)

    assert (
        f"{EnvironmentVariables.__module__}.{EnvironmentVariables.__qualname__}"
        in rendered
    )
    assert "reflex.config.EnvironmentVariables" not in rendered
