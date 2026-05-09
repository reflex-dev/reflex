import re
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace, UnionType
from typing import Any, Literal, Union, get_args, get_origin

from reflex.constants import Dirs
from reflex_base.plugins import CommonContext, Plugin
from typing_extensions import Unpack

MCP_DOC_PATHS = {
    "ai/integrations/mcp-installation.md",
    "ai/integrations/mcp-overview.md",
}
AI_ONBOARDING_DOC_PATHS = {
    "ai/integrations/ai-onboarding.md",
}
MCP_DOC_ORDER = {
    "ai/integrations/mcp-overview.md": 0,
    "ai/integrations/mcp-installation.md": 1,
}
SKILLS_DOC_PATHS = {
    "ai/integrations/skills.md",
}

LLMS_TXT_INTRO = """\
# Reflex Documentation

> Reflex is a Python framework for building full-stack web apps. Use this index to find agent-readable Markdown docs, or see [llms-full.txt]({llms_full_txt_url}) for the complete docs in one file.

## Docs
"""

LLMS_FULL_INTRO = """\
# Reflex Documentation
Source: {docs_home_url}

This file stitches together the full Reflex documentation as Markdown for AI agents and LLM indexing.

For a navigable index with links to individual docs pages, see [llms.txt]({llms_txt_url}).
"""

MARKDOWN_DIRECTIVE = (
    "> For AI agents: the complete documentation index is at "
    "[llms.txt]({llms_txt_url}). Markdown versions are available by appending "
    "`.md` or sending `Accept: text/markdown`."
)
PUBLIC_LLMS_TXT_URL = "https://reflex.dev/docs/llms.txt"
PUBLIC_EVENT_TRIGGERS_URL = "https://reflex.dev/docs/api-reference/event-triggers/"


@dataclass(frozen=True)
class MarkdownFileEntry:
    """A generated markdown file and its llms.txt metadata."""

    url_path: Path
    source_path: Path
    title: str
    section: str


@dataclass(frozen=True)
class MarkdownIndexEntry:
    """An llms.txt entry for generated markdown content."""

    url_path: Path
    title: str
    section: str


def _format_title(value: str) -> str:
    """Format a route or file segment as a title."""
    words = re.split(r"[-_\s]+", value)
    acronyms = {
        "ag": "AG",
        "ai": "AI",
        "api": "API",
        "cli": "CLI",
        "css": "CSS",
        "html": "HTML",
        "ide": "IDE",
        "mcp": "MCP",
        "ui": "UI",
        "url": "URL",
        "urls": "URLs",
    }
    return " ".join(acronyms.get(word.lower(), word.capitalize()) for word in words)


def _extract_markdown_title(source: str) -> str | None:
    """Extract the first top-level heading from markdown source."""
    in_frontmatter = source.startswith("---\n")
    in_code_block = False

    for line in source.splitlines():
        stripped = line.strip()
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped.startswith("# "):
            return stripped.removeprefix("# ").strip()
    return None


def _llms_url_for_path(url_path: Path) -> str:
    """Return the public URL for a generated markdown asset."""
    from reflex_base.config import get_config

    config = get_config()
    deploy_url = config.deploy_url.removesuffix("/") if config.deploy_url else ""
    frontend_path = (config.frontend_path or "").strip("/")
    base_url = deploy_url
    if frontend_path:
        base_url = f"{base_url}/{frontend_path}" if base_url else f"/{frontend_path}"
    return (
        f"{base_url}/{url_path.as_posix()}" if base_url else f"/{url_path.as_posix()}"
    )


def _docs_home_url() -> str:
    """Return the public URL for the docs home."""
    from reflex_base.config import get_config

    config = get_config()
    deploy_url = config.deploy_url.removesuffix("/") if config.deploy_url else ""
    frontend_path = (config.frontend_path or "").strip("/")
    if deploy_url and frontend_path:
        return f"{deploy_url}/{frontend_path}/"
    if deploy_url:
        return f"{deploy_url}/"
    if frontend_path:
        return f"/{frontend_path}/"
    return "/"


def _strip_first_heading(source: str) -> str:
    """Remove the first top-level markdown heading from a page body."""
    lines = source.strip().splitlines()
    in_frontmatter = bool(lines) and lines[0].strip() == "---"
    in_code_block = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if in_frontmatter:
            if stripped == "---" and index > 0:
                in_frontmatter = False
            continue
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped.startswith("# "):
            return "\n".join([*lines[:index], *lines[index + 1 :]]).strip()
    return source.strip()


def _strip_markdown_directive(source: str) -> str:
    """Remove the generated agent discovery directive from markdown content.

    Args:
        source: The markdown content.

    Returns:
        The markdown content without the generated directive.
    """
    directive = _markdown_directive()
    if source.startswith(directive):
        return source.removeprefix(directive).lstrip()
    return source


def _include_index_entry_in_llms_txt(markdown_file: MarkdownIndexEntry) -> bool:
    """Return whether an index entry should appear in llms.txt.

    Args:
        markdown_file: The markdown index entry.

    Returns:
        Whether the entry should be included in llms.txt.
    """
    path = markdown_file.url_path.as_posix()
    return (
        path in MCP_DOC_PATHS
        or path in AI_ONBOARDING_DOC_PATHS
        or path in SKILLS_DOC_PATHS
        or not path.startswith("ai/")
        or path.startswith("ai/overview/")
    )


def _section_for_path(url_path: Path) -> str:
    """Return the llms.txt section for a generated markdown asset."""
    path = url_path.as_posix()
    if path in AI_ONBOARDING_DOC_PATHS:
        return "AI Onboarding"
    if path in MCP_DOC_PATHS:
        return "MCP"
    if path in SKILLS_DOC_PATHS:
        return "Skills"
    if path.startswith("ai/"):
        return "AI Builder"
    return _format_title(path.split("/", maxsplit=1)[0])


def _ordered_sections(
    sections: OrderedDict[str, list[MarkdownIndexEntry]],
) -> list[str]:
    """Return sections in display order."""
    ordered_sections = list(sections)
    if "AI Builder" in sections and "MCP" in sections:
        ordered_sections.remove("MCP")
        ordered_sections.insert(ordered_sections.index("AI Builder") + 1, "MCP")
    if "AI Builder" in sections and "AI Onboarding" in sections:
        ordered_sections.remove("AI Onboarding")
        ordered_sections.insert(
            ordered_sections.index("AI Builder") + 1, "AI Onboarding"
        )
    if "MCP" in sections and "Skills" in sections:
        ordered_sections.remove("Skills")
        ordered_sections.insert(ordered_sections.index("MCP") + 1, "Skills")
    elif "AI Builder" in sections and "Skills" in sections:
        ordered_sections.remove("Skills")
        ordered_sections.insert(ordered_sections.index("AI Builder") + 1, "Skills")
    return ordered_sections


def _ordered_entries(
    section: str, entries: list[MarkdownIndexEntry]
) -> list[MarkdownIndexEntry]:
    """Return entries in display order within a section."""
    if section == "MCP":
        return sorted(
            entries,
            key=lambda entry: MCP_DOC_ORDER[entry.url_path.as_posix()],
        )
    return entries


def generate_markdown_file_entries() -> tuple[MarkdownFileEntry, ...]:
    """Generate the markdown files exposed to agents and llms.txt."""
    from reflex_docs.pages.docs import (
        all_docs,
        doc_route_from_path,
        doc_title_from_path,
        manual_titles,
    )
    from reflex_docs.whitelist import _check_whitelisted_path

    return tuple([
        MarkdownFileEntry(
            url_path=Path(route.strip("/") + ".md"),
            source_path=resolved,
            title=manual_titles.get(
                virtual_path,
                _extract_markdown_title(resolved.read_text(encoding="utf-8"))
                or _format_title(doc_title_from_path(virtual_path)),
            ),
            section=_section_for_path(Path(route.strip("/") + ".md")),
        )
        for virtual_path, source_path in sorted(all_docs.items())
        if not virtual_path.endswith(("-style.md", "-ll.md"))
        if _check_whitelisted_path(route := doc_route_from_path(virtual_path))
        if (resolved := Path(source_path)).is_file()
    ])


def generate_markdown_files() -> tuple[tuple[Path, str], ...]:
    """Generate markdown asset contents for agent-friendly docs pages."""
    return tuple(
        (entry.url_path, generate_markdown_file_content(entry))
        for entry in generate_markdown_file_entries()
    )


def _markdown_directive() -> str:
    """Return the standard agent discovery directive for generated markdown.

    Returns:
        The markdown blockquote directive.
    """
    return MARKDOWN_DIRECTIVE.format(llms_txt_url=PUBLIC_LLMS_TXT_URL).strip()


def generate_markdown_file_content(entry: MarkdownFileEntry) -> str:
    """Generate a markdown asset body with the agent discovery directive.

    Args:
        entry: The markdown file metadata and source path.

    Returns:
        The generated markdown content.
    """
    source = entry.source_path.read_text(encoding="utf-8").lstrip()
    component_reference = _component_api_reference_markdown(entry.source_path)
    body = source.rstrip()
    if component_reference:
        body = f"{body}\n\n{component_reference}"
    return f"{_markdown_directive()}\n\n{body.rstrip()}\n"


def _literal_display(value: Any) -> str:
    """Return a readable display value for a Literal option."""
    return f'"{value}"' if isinstance(value, str) else repr(value)


def _type_name(type_: Any) -> str:
    """Return a readable name for a type."""
    if type_ is None:
        return "None"
    name = getattr(type_, "__name__", None)
    if name:
        return name
    return str(type_).replace("typing.", "")


def _component_prop_type_display(type_: Any) -> str:
    """Return a markdown-friendly display type for a component prop."""
    import reflex as rx

    origin = get_origin(type_)
    try:
        if issubclass(origin, rx.Var):
            type_ = get_args(type_)[0]
            origin = get_origin(type_)
    except TypeError:
        pass

    args = get_args(type_)
    if origin is Literal:
        literal_values = [arg for arg in args if str(arg) != ""]
        return f"Literal[{', '.join(_literal_display(arg) for arg in literal_values)}]"
    if origin in (Union, UnionType):
        displays = []
        for arg in args:
            display = _component_prop_type_display(arg)
            if display and display not in displays:
                displays.append(display)
        return ", ".join(displays)
    if origin is not None and args:
        return f"{_type_name(origin)}[{', '.join(_component_prop_type_display(arg) for arg in args)}]"
    return _type_name(type_)


def _component_prop_description_display(description: str | None) -> str:
    """Return a markdown-friendly display description for a component prop."""
    return (description or "").replace(" | ", ", ")


def _component_from_frontmatter_ref(component_ref: str):
    """Resolve a component reference from a docs frontmatter component entry."""
    import reflex as rx
    from reflex_components_core.core.cond import Cond
    from reflex_pyplot import pyplot as pyplot

    component = (
        Cond
        if component_ref == "rx.cond"
        else eval(component_ref, {"rx": rx, "pyplot": pyplot})
    )
    if isinstance(component, type):
        return component
    if hasattr(component, "__self__"):
        return component.__self__
    if isinstance(component, SimpleNamespace) and hasattr(component, "__call__"):  # noqa: B004
        return component.__call__.__self__
    msg = f"Invalid component: {component}"
    raise ValueError(msg)


def _component_refs_from_source(source_path: Path) -> tuple[tuple[type, str], ...]:
    """Return component classes and display refs from a markdown source file."""
    from reflex_docgen.markdown import parse_document

    source = source_path.read_text(encoding="utf-8")
    doc = parse_document(source)
    if doc.frontmatter is None:
        return ()
    component_refs = getattr(doc.frontmatter, "components", ()) or ()
    return tuple(
        (_component_from_frontmatter_ref(component_ref), component_ref)
        for component_ref in component_refs
    )


def _component_api_reference_markdown(source_path: Path) -> str:
    """Generate the component API reference section for a markdown docs page."""
    from reflex_docgen import generate_documentation

    components = _component_refs_from_source(source_path)
    if not components:
        return ""

    lines = ["## API Reference", ""]
    component_display_name_map = {
        "rx.el.Del": "rx.el.del",
    }
    for component, component_ref in components:
        doc = generate_documentation(component)
        display_name = component_display_name_map.get(component_ref, component_ref)
        lines.extend([f"### {display_name}", ""])
        if doc.description:
            lines.extend([doc.description.strip(), ""])

        props_table = _markdown_table(
            ["Prop", "Type", "Default", "Description"],
            [
                (
                    f"`{prop.name}`",
                    _component_prop_type_display(prop.type),
                    f"`{prop.default_value}`"
                    if prop.default_value is not None
                    else "-",
                    _component_prop_description_display(prop.description),
                )
                for prop in doc.props
                if not prop.name.startswith("on_")
            ],
        )
        if props_table:
            lines.extend(["#### Props", "", *props_table, ""])

        custom_event_handlers = [
            handler for handler in doc.event_handlers if not handler.is_inherited
        ]
        event_table = _markdown_table(
            ["Event Trigger", "Description"],
            [
                (
                    f"`{handler.name}`",
                    handler.description or "",
                )
                for handler in custom_event_handlers
            ],
        )
        lines.extend([
            "#### Event Triggers",
            "",
            f"Base event triggers: {PUBLIC_EVENT_TRIGGERS_URL}",
            "",
        ])
        if event_table:
            lines.extend(["Component-specific event triggers:", "", *event_table, ""])

    return "\n".join(lines).rstrip()


def _escape_table_cell(value: str) -> str:
    """Escape content for a markdown table cell.

    Args:
        value: The cell content.

    Returns:
        The escaped cell content.
    """
    return value.replace("\n", " ").replace("|", "\\|")


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """Return a markdown table.

    Args:
        headers: The table headers.
        rows: The table rows.

    Returns:
        The markdown table lines.
    """
    if not rows:
        return []
    escaped_headers = [_escape_table_cell(header) for header in headers]
    escaped_rows = [[_escape_table_cell(cell) for cell in row] for row in rows]

    return [
        "| " + " | ".join(escaped_headers) + " |",
        "| " + " | ".join("---" for _ in escaped_headers) + " |",
        *["| " + " | ".join(row) + " |" for row in escaped_rows],
    ]


def generate_api_reference_markdown_content(
    *,
    title: str,
    class_name: str,
    description: str | None,
    class_fields: Sequence[tuple[str, str, str]],
    fields: Sequence[tuple[str, str, str]],
    methods: Sequence[tuple[str, str]],
) -> str:
    """Generate markdown content for a dynamic API reference page.

    Args:
        title: The page title.
        class_name: The documented class name.
        description: The class description.
        class_fields: The class field rows as name, type, description.
        fields: The field rows as name, type, description.
        methods: The method rows as signature, description.

    Returns:
        The generated markdown content.
    """
    lines = [
        _markdown_directive(),
        "",
        f"# {title}",
        "",
        f"`{class_name}`",
        "",
    ]
    if description:
        lines.extend([description, ""])
    for heading, field_rows in (
        ("Class Fields", class_fields),
        ("Fields", fields),
    ):
        table = _markdown_table(
            ["Prop", "Description"],
            [
                (
                    f"`{name}: {type_display}`",
                    field_description,
                )
                for name, type_display, field_description in field_rows
            ],
        )
        if table:
            lines.extend([f"## {heading}", "", *table, ""])

    method_table = _markdown_table(
        ["Signature", "Description"],
        [
            (
                f"`{signature}`",
                method_description,
            )
            for signature, method_description in methods
        ],
    )
    if method_table:
        lines.extend(["## Methods", "", *method_table, ""])

    return "\n".join(lines).rstrip() + "\n"


def generate_class_api_reference_markdown(
    *,
    url_path: Path,
    title: str,
    cls: type,
    extra_fields: Sequence[object] = (),
) -> tuple[Path, str]:
    """Generate a dynamic class API reference markdown asset.

    Args:
        url_path: The public markdown asset path.
        title: The page title.
        cls: The class to document.
        extra_fields: Extra docgen fields to include.

    Returns:
        The public path and generated markdown content.
    """
    from reflex_docgen import FieldDocumentation, generate_class_documentation

    doc = generate_class_documentation(cls)
    fields = (
        *doc.fields,
        *(field for field in extra_fields if isinstance(field, FieldDocumentation)),
    )
    return (
        url_path,
        generate_api_reference_markdown_content(
            title=title,
            class_name=doc.name,
            description=doc.description,
            class_fields=tuple(
                (field.name, field.type_display, field.description or "")
                for field in doc.class_fields
            ),
            fields=tuple(
                (field.name, field.type_display, field.description or "")
                for field in fields
            ),
            methods=tuple(
                (method.name + method.signature, method.description or "")
                for method in doc.methods
            ),
        ),
    )


def generate_environment_variables_markdown() -> tuple[Path, str]:
    """Generate the dynamic environment variables markdown asset.

    Returns:
        The public path and generated markdown content.
    """
    import inspect

    from reflex.config import EnvironmentVariables

    env_vars = [
        (name, var)
        for name, var in inspect.getmembers(EnvironmentVariables)
        if not name.startswith("_")
        if hasattr(var, "name")
        if not getattr(var, "internal", False)
    ]
    env_vars.sort(key=lambda item: item[0])
    source_code = inspect.getsource(EnvironmentVariables)
    source_lines = source_code.splitlines()

    def env_var_docstring(name: str) -> str:
        """Return comments documenting an environment variable."""
        for index, line in enumerate(source_lines):
            if f"{name}:" not in line or "EnvVar" not in line:
                continue
            comments = []
            comment_index = index - 1
            while comment_index >= 0 and source_lines[comment_index].strip().startswith(
                "#"
            ):
                comments.insert(0, source_lines[comment_index].strip()[1:].strip())
                comment_index -= 1
            return "\n".join(comments)
        return ""

    table = _markdown_table(
        ["Name", "Type", "Default", "Description"],
        [
            (
                f"`{var.name}`",
                f"`{getattr(var.type_, '__name__', str(var.type_))}`",
                f"`{var.default}`",
                env_var_docstring(name),
            )
            for name, var in env_vars
        ],
    )
    lines = [
        _markdown_directive(),
        "",
        "# Environment Variables",
        "",
        "`reflex.config.EnvironmentVariables`",
        "",
        "Reflex provides a number of environment variables that can be used to configure the behavior of your application.",
        "These environment variables can be set in your shell environment or in a `.env` file.",
        "",
        "This page documents all available environment variables in Reflex.",
        "",
        "## Environment Variables",
        "",
        *table,
        "",
    ]
    return (
        Path("api-reference/environment-variables.md"),
        "\n".join(lines).rstrip() + "\n",
    )


def generate_dynamic_api_reference_files() -> tuple[tuple[Path, str], ...]:
    """Generate markdown assets for dynamic API reference pages.

    Returns:
        The generated dynamic API reference markdown assets.
    """
    import reflex as rx
    from reflex.istate.manager import StateManager
    from reflex.utils.imports import ImportVar
    from reflex_docgen import generate_class_documentation

    modules = [
        rx.App,
        rx.Component,
        rx.ComponentState,
        (rx.Config, rx.config.BaseConfig),
        rx.event.Event,
        rx.event.EventHandler,
        rx.event.EventSpec,
        rx.Model,
        StateManager,
        rx.State,
        ImportVar,
        rx.Var,
    ]
    files = []
    for module in modules:
        extra_fields: list[object] = []
        if isinstance(module, tuple):
            module, *extra_modules = module
            for extra_module in extra_modules:
                extra_fields.extend(generate_class_documentation(extra_module).fields)
        slug = module.__name__.lower()
        files.append(
            generate_class_api_reference_markdown(
                url_path=Path(f"api-reference/{slug}.md"),
                title=_format_title(slug),
                cls=module,
                extra_fields=tuple(extra_fields),
            )
        )
    files.append(generate_environment_variables_markdown())
    return tuple(files)


def dynamic_api_reference_index_entries(
    files: Sequence[tuple[Path, str]],
) -> tuple[MarkdownIndexEntry, ...]:
    """Return llms.txt entries for dynamic API reference markdown assets.

    Args:
        files: The generated dynamic API reference markdown assets.

    Returns:
        The dynamic API reference index entries.
    """
    return tuple(
        MarkdownIndexEntry(
            url_path=path,
            title=_format_title(path.stem),
            section="API Reference",
        )
        for path, _content in files
    )


def generate_llms_txt(
    markdown_files: Sequence[MarkdownIndexEntry],
) -> tuple[Path, str]:
    """Generate an llms.txt index grouped by docs section."""
    sections: OrderedDict[str, list[MarkdownIndexEntry]] = OrderedDict()
    for markdown_file in markdown_files:
        if not _include_index_entry_in_llms_txt(markdown_file):
            continue
        sections.setdefault(markdown_file.section, []).append(markdown_file)

    lines = [
        LLMS_TXT_INTRO.format(
            llms_full_txt_url=_llms_url_for_path(Path("llms-full.txt")),
        ).strip(),
        "",
    ]
    for section in _ordered_sections(sections):
        entries = _ordered_entries(section, sections[section])
        lines.extend([f"### {section}", ""])
        lines.extend(
            f"- [{entry.title}]({_llms_url_for_path(entry.url_path)})"
            for entry in entries
        )
        lines.append("")

    return (Path("llms.txt"), "\n".join(lines).rstrip() + "\n")


def generate_llms_full_txt(
    markdown_files: Sequence[MarkdownFileEntry],
    dynamic_markdown_files: Sequence[tuple[MarkdownIndexEntry, str]] = (),
) -> tuple[Path, str]:
    """Generate an llms-full.txt by stitching all docs markdown together.

    Args:
        markdown_files: Static markdown docs to stitch together.
        dynamic_markdown_files: Generated markdown docs to stitch together.

    Returns:
        The llms-full.txt path and content.
    """
    lines = [
        LLMS_FULL_INTRO.format(
            docs_home_url=_docs_home_url(),
            llms_txt_url=_llms_url_for_path(Path("llms.txt")),
        ).strip(),
        "",
    ]
    for entry in markdown_files:
        source = _strip_first_heading(
            _strip_markdown_directive(generate_markdown_file_content(entry))
        )
        lines.extend([
            f"# {entry.title}",
            f"Source: {_llms_url_for_path(entry.url_path)}",
            "",
            source,
            "",
        ])

    for entry, content in dynamic_markdown_files:
        source = _strip_first_heading(_strip_markdown_directive(content))
        lines.extend([
            f"# {entry.title}",
            f"Source: {_llms_url_for_path(entry.url_path)}",
            "",
            source,
            "",
        ])

    return (Path("llms-full.txt"), "\n".join(lines).rstrip() + "\n")


def markdown_path_for_trailing_slash_url(path: Path) -> Path:
    """Return the static-asset path that serves the trailing-slash URL variant.

    A request for `<page>/.md` is served from the file at `<page>/.md` on disk,
    making the trailing-slash URL `<page>/` resolve to the same content as the
    no-slash URL `<page>.md`.

    Example:
        >>> markdown_path_for_trailing_slash_url(Path("ai/overview.md"))
        PosixPath('ai/overview/.md')

    Args:
        path: The markdown file path.

    Returns:
        The asset path under which to serve the trailing-slash variant.
    """
    return path.with_suffix("") / ".md"


def generate_agent_files() -> tuple[tuple[Path, str | bytes], ...]:
    markdown_file_entries = generate_markdown_file_entries()
    markdown_index_entries = tuple(
        MarkdownIndexEntry(
            url_path=entry.url_path,
            title=entry.title,
            section=entry.section,
        )
        for entry in markdown_file_entries
    )
    dynamic_api_reference_files = generate_dynamic_api_reference_files()
    dynamic_api_reference_entries = dynamic_api_reference_index_entries(
        dynamic_api_reference_files
    )
    markdown_files = tuple(
        (entry.url_path, generate_markdown_file_content(entry))
        for entry in markdown_file_entries
    )

    all_markdown_files = [
        *markdown_files,
        *dynamic_api_reference_files,
    ]

    return (
        *all_markdown_files,
        # Such that `path/.md` would resolve to the same content as `path.md`
        *[
            (markdown_path_for_trailing_slash_url(path), content)
            for path, content in all_markdown_files
        ],
        generate_llms_txt((
            *markdown_index_entries,
            *dynamic_api_reference_entries,
        )),
        generate_llms_full_txt(
            markdown_file_entries,
            tuple(
                (entry, content)
                for entry, (_path, content) in zip(
                    dynamic_api_reference_entries,
                    dynamic_api_reference_files,
                    strict=True,
                )
            ),
        ),
    )


class AgentFilesPlugin(Plugin):
    def get_static_assets(
        self, **context: Unpack[CommonContext]
    ) -> Sequence[tuple[Path, str | bytes]]:
        return [
            (Dirs.PUBLIC / path, content) for path, content in generate_agent_files()
        ]
