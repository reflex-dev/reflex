"""Tests for the generated Reflex Cloud CLI reference pages."""

import re

import click
from reflex.reflex import cli

from reflex_docs.pages.docs.cloud_cliref import (
    CommandDoc,
    InlineCode,
    InlineText,
    InlineTextCollection,
    category_markdown,
    cli_to_doc,
    generate_docs,
    modules,
    usage_line,
)


def _option(flag: str, help_text: str) -> InlineTextCollection:
    """Build an option list item the way the generator does.

    Args:
        flag: The option's flags and type label.
        help_text: The option's help text.

    Returns:
        The flags in code, followed by the help text.
    """
    return InlineTextCollection((InlineCode(flag), InlineText(": " + help_text)))


def test_apps_page_toc_lists_common_options_then_each_command():
    """Each command is one TOC entry; shared options are not repeated per command."""
    toc, _ = generate_docs(modules["apps"], "Apps")[0]
    assert toc == [
        (2, "Common options"),
        (2, "reflex cloud apps scale"),
        (2, "reflex cloud apps status"),
        (2, "reflex cloud apps start"),
        (2, "reflex cloud apps stop"),
        (2, "reflex cloud apps delete"),
        (2, "reflex cloud apps logs"),
        (2, "reflex cloud apps history"),
        (2, "reflex cloud apps build-logs"),
        (2, "reflex cloud apps list"),
        (2, "reflex cloud apps rollback"),
        (2, "reflex cloud apps describe"),
    ]

    # Map each section to the flags it lists: the common ones appear only once.
    flags = {}
    for section in modules["apps"].split("## ")[1:]:
        title, _, body = section.partition("\n")
        flags[title] = re.findall(r"^\* `([^`]+)`", body, flags=re.MULTILINE)
    common = flags.pop("Common options")
    assert common == [
        "--token TEXT",
        "--json, -j / --no-json",
        "--interactive, -i / --no-interactive",
        "--help",
    ]
    assert [flag for own in flags.values() for flag in own if flag in common] == []


def test_category_markdown_factors_out_options_every_command_shares(monkeypatch):
    """Options all commands accept move to one section; the rest stay per command."""
    token = _option("--token TEXT", "The authentication token.")
    watch = _option("--watch / --no-watch", "Whether to watch.")
    monkeypatch.setitem(
        cli_to_doc,
        "reflex a",
        CommandDoc(help="Run a.", usage="$ reflex a [OPTIONS]", options=(token, watch)),
    )
    monkeypatch.setitem(
        cli_to_doc,
        "reflex b",
        CommandDoc(help=None, usage="$ reflex b [OPTIONS]", options=(token,)),
    )
    assert category_markdown(["reflex a", "reflex b", "reflex missing"]) == (
        "## Common options\n"
        "\n"
        "Every command on this page accepts these options.\n"
        "\n\n"
        "* `--token TEXT`: The authentication token.\n"
        "\n"
        "\n\n"
        "## reflex a\n"
        "\n"
        "Run a.\n"
        "\n\n"
        "```console\n"
        "$ reflex a [OPTIONS]\n"
        "```\n"
        "\n\n"
        "**Options**\n"
        "\n\n"
        "* `--watch / --no-watch`: Whether to watch.\n"
        "\n"
        "\n\n"
        "## reflex b\n"
        "\n"
        "\n"
        "```console\n"
        "$ reflex b [OPTIONS]\n"
        "```\n"
        "\n"
        "\n"
    )


def test_single_command_page_keeps_its_options_inline(monkeypatch):
    """A page with one command has nothing to share, so no common section."""
    token = _option("--token TEXT", "The authentication token.")
    monkeypatch.setitem(
        cli_to_doc,
        "reflex a",
        CommandDoc(help=None, usage="$ reflex a [OPTIONS]", options=(token,)),
    )
    assert category_markdown(["reflex a"]) == (
        "## reflex a\n"
        "\n"
        "\n"
        "```console\n"
        "$ reflex a [OPTIONS]\n"
        "```\n"
        "\n"
        "\n"
        "**Options**\n"
        "\n\n"
        "* `--token TEXT`: The authentication token.\n"
        "\n"
    )


def _command_usages(command: click.Command, path: tuple[str, ...]):
    """Yield click's own usage line and info dict for every command in a tree.

    Args:
        command: The command to walk; a lazy command resolves in its context.
        path: The names leading to the command, its own name last.

    Yields:
        Each command's ``(path, usage, info)``, the root included.
    """
    with command.make_context(" ".join(path), [], resilient_parsing=True) as ctx:
        resolved = ctx.command
        yield path, ctx.get_usage(), ctx.to_info_dict()["command"]
        if isinstance(resolved, click.Group):
            for name in resolved.list_commands(ctx):
                if (sub := resolved.get_command(ctx, name)) is not None:
                    yield from _command_usages(sub, (*path, name))


def test_usage_line_matches_click_usage_for_every_command():
    """Optional and variadic arguments are shown the way click's --help shows them."""
    mismatched = {}
    for path, usage, info in _command_usages(cli, ("reflex",)):
        expected = "$ " + usage.removeprefix("Usage: ")
        actual = usage_line(info, " ".join(path[:-1]) or None, path[-1])
        if actual != expected:
            mismatched[" ".join(path)] = (actual, expected)
    assert mismatched == {}
