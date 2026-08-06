"""Module for documenting Reflex environment variables."""

from __future__ import annotations

import inspect
import itertools
from functools import partial
from typing import Any, List, Optional, Tuple

import reflex as rx
from reflex.config import EnvironmentVariables

from reflex_docs.docgen_pipeline import render_markdown
from reflex_docs.templates.docpage import docpage, h1_comp, h2_comp

from .source import stacked_description_header, stacked_description_rows


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
    def generate_env_var_table(cls, include_internal: bool = False) -> rx.Component:
        """Generate a table of environment variables.

        Args:
            include_internal: Whether to include internal environment variables.

        Returns:
            A Reflex component containing the table.
        """
        env_vars = cls.get_all_env_vars()

        if not include_internal:
            env_vars = [
                (name, var)
                for name, var in env_vars
                if not getattr(var, "name", "").startswith("__")
            ]

        env_vars.sort(key=lambda x: x[0])

        def env_var_rows(name: str, var: Any) -> tuple[rx.Component, rx.Component]:
            type_name = str(
                var.type_.__name__ if hasattr(var.type_, "__name__") else str(var.type_)
            )
            return stacked_description_rows(
                [
                    (rx.code(var.name, class_name="code-style"), "@4xl:w-[20%]"),
                    (rx.code(type_name, class_name="code-style"), "@4xl:w-[15%]"),
                    (
                        rx.code(str(var.default), class_name="code-style"),
                        "@4xl:w-[15%]",
                    ),
                ],
                partial(render_markdown, cls.get_env_var_docstring(name) or ""),
                "4xl",
                description_cell_class="@4xl:w-[50%]",
            )

        return rx.box(
            rx.table.root(
                stacked_description_header(
                    ["Name", "Type", "Default", "Description"],
                    "4xl",
                ),
                rx.table.body(
                    *itertools.chain.from_iterable(
                        env_var_rows(name, var) for name, var in env_vars
                    ),
                ),
                width="100%",
                overflow_x="visible",
                class_name="w-full",
            ),
            class_name="@container",
        )


def env_vars_page():
    """Generate the environment variables documentation page.

    Returns:
        A Reflex component containing the documentation.
    """
    return rx.box(
        h1_comp(text="Environment Variables"),
        rx.code(
            "reflex.config.EnvironmentVariables", class_name="code-style text-[18px]"
        ),
        rx.divider(),
        render_markdown(
            """
            Reflex provides a number of environment variables that can be used to configure the behavior of your application.
            These environment variables can be set in your shell environment or in a `.env` file.

            This page documents the environment variables that are not config parameters. Environment variables that override `rx.Config` parameters (e.g. `REFLEX_FRONTEND_PORT`) are listed in the [config reference](/docs/api-reference/config/).
            """
        ),
        h2_comp(text="Environment Variables"),
        EnvVarDocs.generate_env_var_table(include_internal=False),
    )


env_vars_doc = docpage(
    "/api-reference/environment-variables/",
    "Environment Variables",
    right_sidebar=False,
)(env_vars_page)
env_vars_doc.title = "Environment Variables"
