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


def test_env_vars_toc_lists_sections_not_every_variable():
    """The table of contents stays scannable: one entry per section."""
    from reflex_docs.pages.docs.env_vars import env_vars_page

    toc, _page = env_vars_page()
    assert toc == [
        (2, "General"),
        (2, "Hot reload"),
        (2, "Frontend build"),
        (2, "State and Redis"),
        (2, "Database"),
        (2, "Networking"),
        (2, "Logging"),
        (2, "Testing"),
    ]


def test_every_env_var_is_documented_in_exactly_one_section():
    """Grouping neither drops nor duplicates a variable."""
    from reflex_docs.pages.docs.env_vars import EnvVarDocs, group_env_vars

    fields = EnvVarDocs.get_documented_fields()
    grouped = [field for group in group_env_vars(fields).values() for field in group]
    assert sorted(field.name for field in grouped) == [field.name for field in fields]


def test_group_env_vars_uses_first_matching_prefix_and_general_fallback():
    """Narrower sections win over broader ones; unknown variables are general."""
    from reflex_docgen import FieldDocumentation

    from reflex_docs.pages.docs.env_vars import group_env_vars

    def field(name: str) -> FieldDocumentation:
        """Build a minimal documented variable.

        Args:
            name: The variable's name.

        Returns:
            The variable's documentation with no type details.
        """
        return FieldDocumentation(
            name=name, type=str, type_display="str", default=None, description=None
        )

    hmr, minify, port, pool, new = (
        field("VITE_HMR"),
        field("VITE_MINIFY"),
        field("REFLEX_BACKEND_PORT"),
        field("SQLALCHEMY_POOL_SIZE"),
        field("REFLEX_SOMETHING_NEW"),
    )
    assert group_env_vars([hmr, minify, port, pool, new]) == {
        "General": [port, new],
        "Hot reload": [hmr],
        "Frontend build": [minify],
        "Database": [pool],
    }
