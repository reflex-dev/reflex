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


def test_env_vars_head_title_has_site_suffix():
    """The environment variables page title matches the other reference pages."""
    from reflex_docs.pages.docs.env_vars import env_vars_doc

    assert env_vars_doc.title == "Environment Variables"
    assert env_vars_doc.seo_title == "Environment Variables · Reflex Docs"
