from __future__ import annotations

import dataclasses
import functools
import inspect
from collections.abc import Callable, Sequence
from importlib.util import find_spec
from typing import Any, TypedDict, cast

import click
import reflex as rx
from reflex.reflex import cli

from reflex_docs.docgen_pipeline import render_markdown_with_toc
from reflex_docs.templates.docpage import docpage, h1_comp


@dataclasses.dataclass(frozen=True)
class Element:
    def into_text(self) -> str:
        """Convert the element into a text representation."""
        raise NotImplementedError("Subclasses must implement this method.")


@dataclasses.dataclass(frozen=True)
class InlineElement(Element): ...


@dataclasses.dataclass(frozen=True)
class InlineTextCollection(InlineElement):
    elements: tuple[InlineElement, ...]

    def into_text(self) -> str:
        return "".join(element.into_text() for element in self.elements)


@dataclasses.dataclass(frozen=True)
class InlineText(InlineElement):
    text: str

    def into_text(self) -> str:
        import html

        return html.escape(self.text)


@dataclasses.dataclass(frozen=True)
class InlineCode(InlineText):
    def into_text(self) -> str:
        return f"`{super().into_text()}`"


@dataclasses.dataclass(frozen=True)
class InlineStrong(InlineText):
    def into_text(self) -> str:
        """Render the text in bold.

        Returns:
            The escaped text wrapped in markdown strong emphasis.
        """
        return f"**{super().into_text()}**"


@dataclasses.dataclass(frozen=True)
class Paragraph(Element):
    text: InlineElement

    def into_text(self) -> str:
        return f"{self.text.into_text()}\n\n"


@dataclasses.dataclass(frozen=True)
class Header(Element):
    level: int
    text: InlineElement

    def into_text(self) -> str:
        return f"{'#' * self.level} {self.text.into_text()}\n"


@dataclasses.dataclass(frozen=True)
class List(Element):
    items: tuple[InlineElement, ...]
    ordered: bool = False

    def into_text(self) -> str:
        prefix = "1. " if self.ordered else "* "
        return "\n".join(f"{prefix}{item.into_text()}" for item in self.items) + "\n\n"


@dataclasses.dataclass(frozen=True)
class CodeBlock(Element):
    code: str
    language: str | None = None

    def into_text(self) -> str:
        if self.language:
            return f"```{self.language}\n{self.code}\n```\n\n"
        return f"```\n{self.code}\n```\n\n"


@dataclasses.dataclass(frozen=True)
class Empty(Element):
    def into_text(self) -> str:
        return ""


@dataclasses.dataclass(frozen=True)
class Section(Element):
    sub_elements: tuple[Element, ...]

    def into_text(self) -> str:
        return "\n".join(sub_element.into_text() for sub_element in self.sub_elements)


class ParamTypeInfoDict(TypedDict):
    param_type: str
    name: str


class ChoiceParamTypeInfoDict(ParamTypeInfoDict):
    choices: list[str]
    case_sensitive: bool


class ParamsInfoDict(TypedDict):
    name: str | None
    param_type_name: str
    opts: list[str]
    secondary_opts: list[str]
    type: ParamTypeInfoDict | ChoiceParamTypeInfoDict
    required: bool
    nargs: int
    multiple: bool
    default: Any | Callable[[], Any] | None
    envvar: str | Sequence[str] | None


class OptionInfoDict(ParamsInfoDict):
    help: str | None
    prompt: str | None
    is_flag: bool
    flag_value: Any
    count: bool
    hidden: bool


class CommandInfoDict(TypedDict):
    name: str | None
    params: list[ParamsInfoDict | OptionInfoDict]
    help: str | None
    epilog: str | None
    short_help: str | None
    hidden: bool
    deprecated: bool


class MultiCommandInfoDict(CommandInfoDict):
    commands: dict[str, CommandInfoDict | MultiCommandInfoDict]
    chain: bool


class InfoDict(TypedDict):
    command: CommandInfoDict | MultiCommandInfoDict
    info_name: str | None
    allow_extra_args: bool
    allow_interspersed_args: bool
    ignore_unknown_options: bool
    auto_envvar_prefix: str | None


def sort_subcommands(
    commands: dict[str, CommandInfoDict | MultiCommandInfoDict],
) -> dict[str, CommandInfoDict | MultiCommandInfoDict]:
    """Sort subcommands by name."""
    return dict(
        sorted(commands.items(), key=lambda item: len(item[1].get("commands", {})))
    )


@dataclasses.dataclass(frozen=True)
class CommandDoc:
    """A documented command, kept in parts so a page can lay several out together."""

    help: str | None
    usage: str
    options: tuple[InlineElement, ...]


# Documentation for every command, keyed by its full name.
cli_to_doc: dict[str, CommandDoc] = {}


def usage_line(command: CommandInfoDict, prefix: str | None, name: str) -> str:
    """Build the console usage line for a command.

    Args:
        command: The command's click info dict.
        prefix: The names of the parent commands, if any.
        name: The command's own name.

    Returns:
        The usage line, including the shell prompt.
    """
    params = command["params"]
    options = (
        " [OPTIONS]"
        if any(param.get("param_type_name") != "argument" for param in params)
        else ""
    )
    arguments = "".join(
        " " + argument_metavar(param)
        for param in params
        if param.get("param_type_name") == "argument" and param["name"]
    )
    if "commands" in command:
        arguments += (
            " COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]..."
            if cast(MultiCommandInfoDict, command)["chain"]
            else " COMMAND [ARGS]..."
        )
    return (
        f"${' ' + prefix.strip() if prefix else ''} {name.strip()}{options}{arguments}"
    )


def argument_metavar(param: ParamsInfoDict) -> str:
    """Name an argument in a usage line the way click's own usage does.

    Args:
        param: The argument's click info dict.

    Returns:
        The upper-cased name, bracketed when optional and followed by an
        ellipsis when it takes more than one value.
    """
    metavar = cast(str, param["name"]).upper()
    if not param["required"]:
        metavar = f"[{metavar}]"
    return metavar + ("..." if param["nargs"] != 1 else "")


def option_item(
    param: ParamsInfoDict | OptionInfoDict, help_text: str
) -> InlineElement:
    """Describe one option as a list item.

    Args:
        param: The option's click info dict.
        help_text: The option's help text.

    Returns:
        The option's flags and type in code, followed by its help text.
    """
    secondary = (
        " / " + ", ".join(param["secondary_opts"]) if param["secondary_opts"] else ""
    )
    choices = param["type"].get("choices")
    if choices is not None:
        type_label = " [" + "|".join(choices) + "]"
    elif param["type"]["name"] != "boolean":
        type_label = " " + param["type"]["name"].upper()
    else:
        type_label = ""
    return InlineTextCollection((
        InlineCode(", ".join(param["opts"]) + secondary + type_label),
        InlineText(": " + help_text),
    ))


def process(
    command: CommandInfoDict | MultiCommandInfoDict,
    prefix: str | None,
    override_name: str | None,
) -> None:
    """Record a click command and its subcommands in ``cli_to_doc``.

    Args:
        command: The command's click info dict.
        prefix: The names of the parent commands, if any.
        override_name: The name the command is registered under.
    """
    actual_name = override_name or command["name"]
    full_name = prefix + " " + actual_name if prefix and actual_name else actual_name
    cli_to_doc[full_name] = CommandDoc(
        help=command["help"],
        usage=usage_line(command, prefix, actual_name) if actual_name else "",
        options=tuple(
            option_item(param, option_help)
            for param in command["params"]
            if (option_help := param.get("help")) is not None
        ),
    )
    for name, sub_command in sort_subcommands(command.get("commands", {})).items():
        process(sub_command, full_name, name)


def process_command(command: click.Command, name: str) -> None:
    """Record a click command tree in ``cli_to_doc``.

    Args:
        command: The root click command.
        name: The name the root command is invoked as.
    """
    with click.Context(command) as ctx:
        process(ctx.to_info_dict()["command"], None, name)


if find_spec("typer") is not None and find_spec("typer.main") is not None:
    import typer  # pyright: ignore[reportMissingImports]

    if isinstance(cli, typer.Typer):
        cli = typer.main.get_command(cli)

# Iterate over each command configuration
process_command(cli, "reflex")


REFLEX_PREFIX = "reflex"
REFLEX_CLOUD_PREFIX = REFLEX_PREFIX + " cloud"


def prefix(
    prefix: str,
    commands: list[str],
) -> list[str]:
    return [prefix + " " + command for command in commands]


# Dictionary to store the categories and their respective commands
categories = {
    "login": prefix(REFLEX_PREFIX, ["login", "logout"]),
    "deploy": prefix(REFLEX_PREFIX, ["deploy"]),
    "scan": prefix(REFLEX_CLOUD_PREFIX, ["scan"]),
    "apps": prefix(
        REFLEX_CLOUD_PREFIX + " apps",
        [
            "scale",
            "status",
            "start",
            "stop",
            "delete",
            "logs",
            "history",
            "build-logs",
            "list",
            "rollback",
            "describe",
        ],
    ),
    "providers": prefix(
        REFLEX_CLOUD_PREFIX + " providers",
        ["status", "list"],
    ),
    "projects": prefix(
        REFLEX_CLOUD_PREFIX + " project",
        [
            "list",
            "create",
            "select",
            "invite",
            "get-select",
            "usage",
            "role-permissions",
            "users",
        ],
    ),
    "secrets": prefix(
        REFLEX_CLOUD_PREFIX + " secrets",
        ["list", "delete", "update"],
    ),
    "vmtypes": prefix(REFLEX_CLOUD_PREFIX, ["vmtypes"]),
    "regions": prefix(REFLEX_CLOUD_PREFIX, ["regions"]),
    "config": prefix(REFLEX_CLOUD_PREFIX, ["config"]),
}

COMMON_OPTIONS_TITLE = "Common options"


def command_markdown(
    name: str, doc: CommandDoc, common: frozenset[InlineElement]
) -> str:
    """Render one command's section, leaving out the page's common options.

    Args:
        name: The command's full name.
        doc: The command's documentation.
        common: Options documented once for the whole page.

    Returns:
        The command's markdown section.
    """
    options = tuple(option for option in doc.options if option not in common)
    return Section((
        Header(2, InlineText(name)),
        Paragraph(InlineText(doc.help)) if doc.help else Empty(),
        CodeBlock(doc.usage, language="console") if doc.usage else Empty(),
        Section((Paragraph(InlineStrong("Options")), List(options)))
        if options
        else Empty(),
    )).into_text()


def category_markdown(commands: Sequence[str]) -> str:
    """Render a reference page documenting one or more commands.

    Options every command on the page accepts are listed once, in a common
    options section, instead of under each command.

    Args:
        commands: Full names of the commands on the page.

    Returns:
        The page's markdown.
    """
    docs = {name: cli_to_doc[name] for name in commands if name in cli_to_doc}
    common: tuple[InlineElement, ...] = ()
    if len(docs) > 1:
        first, *rest = docs.values()
        common = tuple(
            option
            for option in first.options
            if all(option in doc.options for doc in rest)
        )
    common_set = frozenset(common)
    sections = [command_markdown(name, doc, common_set) for name, doc in docs.items()]
    if common:
        sections.insert(
            0,
            Section((
                Header(2, InlineText(COMMON_OPTIONS_TITLE)),
                Paragraph(
                    InlineText("Every command on this page accepts these options.")
                ),
                List(common),
            )).into_text(),
        )
    return "\n\n".join(sections)


# The combined markdown for each category page.
modules: dict[str, str] = {
    category: category_markdown(commands) for category, commands in categories.items()
}


def generate_docs(
    source: str, title: str
) -> tuple[tuple[list[tuple[int, str]], str], rx.Component]:
    """Render a CLI reference page with its table of contents.

    Args:
        source: The page's markdown.
        title: The page title.

    Returns:
        The ``(toc, source)`` pair the docpage template reads, and the page body.
    """
    toc, body = render_markdown_with_toc(source)
    # Emit a single page-level <h1> (mirrors the API-reference generator) so the
    # per-command sections stay <h2> and the page has exactly one <h1> for SEO.
    return (toc, source), rx.box(h1_comp(text=title), body)


def command_source_path(name: str) -> str | None:
    """Locate the callback supplying a documented command's help text.

    Args:
        name: Full command name, including the leading ``reflex``.

    Returns:
        Callback source path, or None for commands without a callback.
    """
    command = cli
    for part in name.split()[1:]:
        # Creating a parsing-only context resolves lazy commands without
        # invoking their callbacks or authenticating with the hosting service.
        with command.make_context(command.name, [], resilient_parsing=True) as ctx:
            command = cast(click.Group, ctx.command).get_command(ctx, part)
        if command is None:
            return None
    return (
        inspect.getsourcefile(inspect.unwrap(command.callback))
        if command.callback is not None
        else None
    )


# Titles that title-casing the module name gets wrong.
_TITLES = {"vmtypes": "VM Types"}

pages = []
for module_name, module_value in modules.items():
    title = _TITLES.get(module_name) or module_name.replace("_", " ").title()
    docs = functools.partial(generate_docs, module_value, title)
    sources = {
        source
        for name in categories[module_name]
        if name in cli_to_doc and (source := command_source_path(name)) is not None
    }
    # A category spanning several modules is maintained in this aggregation file.
    source_path = next(iter(sources)) if len(sources) == 1 else __file__
    page_data = docpage(f"/hosting/cli/{module_name}/", title, source_path=source_path)(
        docs
    )
    # Keep the short sidebar/nav label (e.g. "Deploy"), but emit a descriptive
    # HTML <title> for SEO.
    page_data.title = title
    page_data.seo_title = f"{title} · Reflex Cloud CLI Reference · Reflex Docs"
    pages.append(page_data)
