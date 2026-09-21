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


def env_vars_page():
    """Generate the environment variables documentation page.

    Returns:
        A Reflex component containing the documentation.
    """
    fields = EnvVarDocs.get_documented_fields()
    toc = [(2, "Variables"), *((3, field.name) for field in fields)]
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
        h2_comp(text="Variables"),
        rx.el.div(
            *(field_row(field) for field in fields), class_name="border-t border-border"
        ),
        class_name="min-w-0 api-reference-detail",
    )


env_vars_doc = docpage(
    "/api-reference/environment-variables/",
    "Environment Variables",
)(env_vars_page)
env_vars_doc.title = "Environment Variables"
