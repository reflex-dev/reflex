"""Module for documenting Reflex environment variables."""

from __future__ import annotations

import inspect
from typing import Any, List, Optional, Tuple

import reflex as rx
from reflex.config import EnvironmentVariables

from reflex_docs.docgen_pipeline import render_markdown
from reflex_docs.templates.docpage import docpage, h1_comp, h2_comp


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
                if not getattr(var, "internal", False)
            ]

        env_vars.sort(key=lambda x: x[0])

        return rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell(
                            "Name",
                            class_name="font-small text-slate-12 text-normal w-[20%] justify-start pl-4 font-bold",
                        ),
                        rx.table.column_header_cell(
                            "Type",
                            class_name="font-small text-slate-12 text-normal w-[15%] justify-start pl-4 font-bold",
                        ),
                        rx.table.column_header_cell(
                            "Default",
                            class_name="font-small text-slate-12 text-normal w-[15%] justify-start pl-4 font-bold",
                        ),
                        rx.table.column_header_cell(
                            "Description",
                            class_name="font-small text-slate-12 text-normal w-[50%] justify-start pl-4 font-bold",
                        ),
                    )
                ),
                rx.table.body(
                    *[
                        rx.table.row(
                            rx.table.cell(
                                rx.code(var.name, class_name="code-style"),
                                class_name="w-[20%]",
                            ),
                            rx.table.cell(
                                rx.code(
                                    str(
                                        var.type_.__name__
                                        if hasattr(var.type_, "__name__")
                                        else str(var.type_)
                                    ),
                                    class_name="code-style",
                                ),
                                class_name="w-[15%]",
                            ),
                            rx.table.cell(
                                rx.code(str(var.default), class_name="code-style"),
                                class_name="w-[15%]",
                            ),
                            rx.table.cell(
                                render_markdown(cls.get_env_var_docstring(name) or ""),
                                class_name="font-small text-slate-11 w-[50%]",
                            ),
                        )
                        for name, var in env_vars
                    ],
                ),
                width="100%",
                overflow_x="visible",
                class_name="w-full",
            ),
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

            This page documents all available environment variables in Reflex.
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
