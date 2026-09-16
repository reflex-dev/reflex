"""Export navigation and generated page content from prerendered HTML."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
SKIP_TAGS = {"script", "style", "nav", "footer", "button", "svg", "form"}


@dataclass
class Element:
    """A small HTML tree retaining semantic elements and text."""

    tag: str
    attrs: dict[str, str | None] = field(default_factory=dict)
    children: list[Element | str] = field(default_factory=list)

    def find_all(self, tag: str) -> list[Element]:
        """Return descendants matching a tag in document order."""
        return ([self] if self.tag == tag else []) + [
            node
            for child in self.children
            if isinstance(child, Element)
            for node in child.find_all(tag)
        ]

    def text(self) -> str:
        """Return plain text without losing whitespace inside code."""
        return "".join(
            child if isinstance(child, str) else child.text() for child in self.children
        )


class Document(HTMLParser):
    """Parse prerendered HTML without executing scripts or loading resources."""

    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        """Append an element and track non-void parents."""
        element = Element(tag, dict(attrs))
        self.stack[-1].children.append(element)
        if tag not in VOID_TAGS:
            self.stack.append(element)

    def handle_endtag(self, tag):
        """Close the nearest matching parent."""
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        """Preserve text for conversion."""
        self.stack[-1].children.append(data)


def to_markdown(node: Element | str, page_url: str) -> str:
    """Convert semantic HTML to Markdown, retaining code, tables and destinations."""
    if isinstance(node, str):
        return re.sub(r"\s+", " ", node)
    if (
        node.tag in SKIP_TAGS
        or node.attrs.get("aria-hidden") == "true"
        or "hidden" in node.attrs
        or node.attrs.get("data-slot") == "avatar"
    ):
        return ""
    if "sr-only" in (node.attrs.get("class") or "").split():
        return ""
    if node.tag == "pre":
        code = node.text().strip("\n")
        fence = "`" * max(
            3, max((len(run) + 1 for run in re.findall(r"`+", code)), default=0)
        )
        return f"\n\n{fence}\n{code}\n{fence}\n\n"
    content = "".join(to_markdown(child, page_url) for child in node.children)
    if node.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return f"\n\n{'#' * int(node.tag[1])} {content.strip()}\n\n"
    if node.tag == "a" and (href := node.attrs.get("href")):
        destination = urljoin(page_url, href)
        headings = [
            heading for level in range(1, 7) for heading in node.find_all(f"h{level}")
        ]
        if headings:
            # Keep heading permalink wrappers and linked workflow cards readable.
            if destination.split("#")[0] == page_url and "#" in destination:
                return content
            label = node.attrs.get("aria-label") or headings[0].text().strip()
            return f"{content}\n\n[{label}]({destination})\n\n"
        label = " ".join(content.split()) or node.attrs.get("aria-label")
        link = f"[{label}]({destination})" if label else ""
        return f"\n\n{link}\n\n" if "\n" in content else link + " "
    if node.tag == "img" and (src := node.attrs.get("src")):
        alt = node.attrs.get("alt") or ""
        return (
            f"![{alt}]({urljoin(page_url, src)})"
            if alt and not alt.startswith("Image preview of")
            else ""
        )
    if node.tag == "code":
        delimiter = "`" * max(
            1, max((len(run) + 1 for run in re.findall(r"`+", content)), default=0)
        )
        return f"{delimiter}{content}{delimiter}"
    if node.tag == "li":
        return f"\n- {content.strip()}\n"
    if node.tag == "br":
        return "\n"
    if node.tag == "table":
        rows = [
            [
                " ".join(to_markdown(cell, page_url).split()).replace("|", r"\|")
                for cell in row.children
                if isinstance(cell, Element) and cell.tag in {"th", "td"}
            ]
            for row in node.find_all("tr")
        ]
        rows = [row for row in rows if row]
        if not rows:
            return ""
        width = max(map(len, rows))
        rows = [row + [""] * (width - len(row)) for row in rows]
        lines = ["| " + " | ".join(row) + " |" for row in rows]
        lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
        return "\n\n" + "\n".join(lines) + "\n\n"
    if node.tag in {"p", "div", "section", "article", "main", "ul", "ol", "blockquote"}:
        return f"\n\n{content.strip()}\n\n" if content.strip() else ""
    return content


def rendered_content(html: str, page_url: str) -> tuple[str, str]:
    """Extract the page answer while excluding shared navigation and controls."""
    document = Document(html).root
    roots = document.find_all("article") or document.find_all("main")
    if not roots or not (headings := roots[0].find_all("h1")):
        raise ValueError(f"Missing main content or heading: {page_url}")
    content = to_markdown(roots[0], page_url)
    return headings[0].text().strip(), re.sub(r"\n{3,}", "\n\n", content).strip() + "\n"


def export_rendered_pages(static_dir: Path, frontend_path: str) -> None:
    """Complete canonical-page exports and discovery files after prerendering."""
    from agent_files._plugin import (
        MarkdownIndexEntry,
        _extract_markdown_title,
        _markdown_directive,
        _section_for_path,
        generate_llms_full_txt,
        generate_llms_txt,
        markdown_path_for_trailing_slash_url,
    )

    base = static_dir / frontend_path.strip("/")
    sitemap = static_dir / "sitemap.xml"
    if not sitemap.exists():
        sitemap = base / "sitemap.xml"
    entries = []
    for loc in ElementTree.parse(sitemap).iter():
        if not loc.tag.endswith("loc") or not loc.text:
            continue
        url = loc.text
        relative = urlsplit(url).path.removeprefix(frontend_path).strip("/")
        page = base / relative / "index.html"
        html = page.read_text()
        path = Path(relative + ".md") if relative else Path("index.md")
        target = base / path
        existing = target.read_text() if target.exists() else ""
        # Eval-only source files expose a rendering function, not their answer.
        prose = re.sub(
            r"^```python (?:exec|eval)[^\n]*\n.*?^```\s*$",
            "",
            existing,
            flags=re.MULTILINE | re.DOTALL,
        )
        prose = re.sub(r"^> For AI agents:.*$", "", prose, flags=re.MULTILINE).strip()
        title = None
        if not prose:
            title, content = rendered_content(html, url)
            existing = f"{_markdown_directive()}\n\n{content}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(existing)
        if title is None:
            title = _extract_markdown_title(existing) or relative.rsplit("/", 1)[-1]
        twin = base / markdown_path_for_trailing_slash_url(path)
        twin.parent.mkdir(parents=True, exist_ok=True)
        twin.write_text(existing)
        entry = MarkdownIndexEntry(path, title, _section_for_path(path))
        entries.append((entry, existing))
    for name, content in (
        generate_llms_txt([entry for entry, _ in entries]),
        generate_llms_full_txt((), entries),
    ):
        (base / name).write_text(content)
