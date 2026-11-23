"""Module for documenting Reflex environment variables."""

from __future__ import annotations

import inspect
from typing import Any, List, Optional, Tuple

import reflex as rx
from reflex_base.environment import EnvironmentVariables
from reflex_docgen import FieldDocumentation

from reflex_docs.docgen_pipeline import render_markdown
from reflex_docs.templates.docpage import docpage, h1_comp, h2_comp

from .api_reference_layout import field_row

# Page sections in display order, each claiming the variables whose names start
# with one of its prefixes. The first matching section wins, so a narrower
# section precedes a broader one sharing its prefix.
ENV_VAR_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Hot reload",
        (
            "REFLEX_AUTO_RELOAD_",
            "REFLEX_HOT_RELOAD_",
            "REFLEX_STRICT_HOT_RELOAD",
            "VITE_EXPERIMENTAL_HMR",
            "VITE_FORCE_FULL_RELOAD",
            "VITE_HMR",
        ),
    ),
    (
        "Frontend build",
        (
            "NPM_",
            "REFLEX_DEV_PROD_REACT",
            "REFLEX_NO_AUTOPREFIXER",
            "REFLEX_PERSIST_WEB_DIR",
            "REFLEX_REACT_OWNER_STACKS",
            "REFLEX_SSR",
            "REFLEX_USE_NPM",
            "REFLEX_USE_SYSTEM_BUN",
            "REFLEX_VITE_",
            "REFLEX_WEB_WORKDIR",
            "VITE_",
        ),
    ),
    (
        "State and Redis",
        ("REFLEX_IGNORE_REDIS_", "REFLEX_OPLOCK_", "REFLEX_REDIS_", "REFLEX_STATE"),
    ),
    ("Database", ("ALEMBIC_", "SQLALCHEMY_")),
    (
        "Networking",
        ("REFLEX_HTTP_CLIENT_", "REFLEX_SOCKET_", "SSL_NO_VERIFY"),
    ),
    ("Logging", ("REFLEX_ENABLE_FULL_LOGGING", "REFLEX_LOG_")),
    ("Testing", ("APP_HARNESS_",)),
)
# Claims the rest: run modes, ports, servers, directories and the like.
GENERAL_SECTION = "General"


class EnvVarDocs:
    """Documentation for Reflex environment variables."""

    @classmethod
    def get_all_env_vars(cls) -> List[Tuple[str, Any]]:
        """Get all environment variables from the environment class.

        Returns:
            A list of tuples containing the environment variable name and its EnvVar instance.
        """
        env_vars = []
        for name, attr in inspect.getmembers(EnvironmentVariables):
            if name.startswith("_") or not hasattr(attr, "name"):
                continue
            env_vars.append((name, attr))
        return env_vars

    @classmethod
    def get_env_var_docstring(cls, name: str) -> Optional[str]:
        """Get the docstring for an environment variable.

        Args:
            name: The name of the environment variable.

        Returns:
            The docstring for the environment variable, or None if not found.
        """
        source_code = inspect.getsource(EnvironmentVariables)
        lines = source_code.splitlines()

        for i, line in enumerate(lines):
            if f"{name}:" in line and "EnvVar" in line:
                j = i - 1
                comments = []
                while j >= 0 and lines[j].strip().startswith("#"):
                    comments.insert(0, lines[j].strip()[1:].strip())
                    j -= 1
                if comments:
                    return "\n".join(comments)
        return None

    @classmethod
    def get_documented_fields(cls) -> list[FieldDocumentation]:
        """Represent public environment variables using the shared reference metadata."""
        return [
            FieldDocumentation(
                name=var.name,
                type=var.type_,
                type_display=str(getattr(var.type_, "__name__", var.type_)),
                default=str(var.default),
                description=cls.get_env_var_docstring(name),
            )
            for name, var in sorted(cls.get_all_env_vars())
            if not var.name.startswith("__")
        ]


def group_env_vars(
    fields: list[FieldDocumentation],
) -> dict[str, list[FieldDocumentation]]:
    """Sort environment variables into the page's sections.

    Args:
        fields: The documented environment variables.

    Returns:
        The non-empty sections in display order, general first, mapped to
        their variables in the order given.
    """
    sections: dict[str, list[FieldDocumentation]] = {
        GENERAL_SECTION: [],
        **{title: [] for title, _ in ENV_VAR_SECTIONS},
    }
    for field in fields:
        section = next(
            (
                title
                for title, prefixes in ENV_VAR_SECTIONS
                if field.name.startswith(prefixes)
            ),
            GENERAL_SECTION,
        )
        sections[section].append(field)
    return {title: fields for title, fields in sections.items() if fields}


def env_vars_page():
    """Generate the environment variables documentation page.

    Returns:
        A Reflex component containing the documentation.
    """
    sections = group_env_vars(EnvVarDocs.get_documented_fields())
    # Variables keep their own anchors, but the table of contents lists only
    # the sections so it stays short enough to scan.
    toc = [(2, title) for title in sections]
    return toc, rx.el.div(
        h1_comp(text="Environment Variables"),
        rx.el.p(
            f"{EnvironmentVariables.__module__}.{EnvironmentVariables.__qualname__}",
            class_name="mb-5 font-mono text-sm text-muted-foreground",
        ),
        render_markdown(
            """
            Reflex provides a number of environment variables that can be used to configure the behavior of your application.
            These environment variables can be set in your shell environment or in a `.env` file.

            This page documents the environment variables that are not config parameters. Environment variables that override `rx.Config` parameters (e.g. `REFLEX_FRONTEND_PORT`) are listed in the [config reference](/docs/api-reference/config/).
            """
        ),
        *(
            rx.el.section(
                h2_comp(text=title),
                rx.el.div(
                    *(field_row(field) for field in fields),
                    class_name="border-t border-border",
                ),
            )
            for title, fields in sections.items()
        ),
        class_name="min-w-0 api-reference-detail",
    )


env_vars_doc = docpage(
    "/api-reference/environment-variables/",
    "Environment Variables",
)(env_vars_page)
# The sidebar keeps the short title; the HTML <title> carries the site suffix.
env_vars_doc.title = "Environment Variables"
env_vars_doc.seo_title = "Environment Variables · Reflex Docs"
