import os
import re
from collections import defaultdict, namedtuple
from pathlib import Path
from types import SimpleNamespace

import reflex as rx
from reflex_components_core.core.cond import Cond
from reflex_docgen.markdown import parse_document

# External Components
from reflex_pyplot import pyplot as pyplot
from reflex_site_shared.route import Route

from reflex_docs.changelogs import (
    changelog_page_title,
    discover_changelogs,
    normalize_changelog,
)
from reflex_docs.docgen_pipeline import (
    get_docgen_toc,
    render_docgen_document,
    render_markdown_with_toc,
)
from reflex_docs.pages.docs.component import multi_docs
from reflex_docs.pages.library_previews import components_previews_pages
from reflex_docs.templates.docpage import docpage
from reflex_docs.whitelist import _check_whitelisted_path

from .apiref import pages as apiref_pages
from .cloud import pages as cloud_pages
from .cloud_cliref import pages as cloud_cliref_pages
from .custom_components import custom_components
from .library import library
from .recipes_overview import overview

SPECIAL_COMPONENT_DOCS = {
    "rx.cond": Cond,
}


def to_title_case(text: str) -> str:
    return " ".join(word.capitalize() for word in text.split("_"))


def build_nested_namespace(
    parent_namespace: SimpleNamespace, path: list, title: str, comp
):
    namespace = rx.utils.format.to_snake_case(path[0])

    if (
        isinstance(parent_namespace, SimpleNamespace)
        and getattr(parent_namespace, namespace, None) is None
    ):
        setattr(parent_namespace, namespace, SimpleNamespace())

    nested_namespace = getattr(parent_namespace, namespace)

    if len(path) == 1:
        setattr(nested_namespace, title, comp)
    else:
        setattr(
            parent_namespace,
            namespace,
            build_nested_namespace(
                nested_namespace,
                path[1:],
                title,
                comp,
            ),
        )
    return parent_namespace


def get_components_from_frontmatter(filepath: str) -> list:
    """Extract component tuples from a doc's frontmatter."""
    source = Path(filepath).read_text(encoding="utf-8")
    doc = parse_document(source)
    if doc.frontmatter is None:
        return []
    components = []
    for comp_str in doc.frontmatter.components:
        if component := SPECIAL_COMPONENT_DOCS.get(comp_str):
            components.append((component, comp_str))
            continue
        component = eval(comp_str)
        if isinstance(component, type):
            components.append((component, comp_str))
        elif hasattr(component, "__self__"):
            components.append((component.__self__, comp_str))
        elif isinstance(component, SimpleNamespace) and hasattr(component, "__call__"):  # noqa: B004
            components.append((component.__call__.__self__, comp_str))
        else:
            raise ValueError(f"Invalid component: {component}")
    return components


def get_previews_from_frontmatter(filepath: str) -> dict[str, str]:
    """Extract component preview sources from a doc's frontmatter."""
    source = Path(filepath).read_text(encoding="utf-8")
    doc = parse_document(source)
    if doc.frontmatter is None:
        return {}
    return {p.name: p.source for p in doc.frontmatter.component_previews}


# ---------------------------------------------------------------------------
# Discover all docs — single pipeline via reflex_docgen
# ---------------------------------------------------------------------------
_app_root = Path(__file__).resolve().parent.parent.parent.parent  # …/app/
_docs_dir = _app_root.parent  # …/docs/ (parent of app/)
_pkg_root = _docs_dir / "package"  # …/package/ (reflex-docs-bundle)

all_docs: dict[str, str] = {}  # virtual_path → actual_path
for _md_file in sorted(_docs_dir.rglob("*.md")):
    # Skip anything inside the app/ or package/ subdirectories.
    if _md_file.is_relative_to(_app_root) or _md_file.is_relative_to(_pkg_root):
        continue
    _virtual = "docs/" + str(_md_file.relative_to(_docs_dir)).replace("\\", "/")
    all_docs[_virtual] = str(_md_file)

# Add integration docs from the installed package
doc_path_mapping: dict[str, str] = {}
from integrations_docs import DOCS_DIR

if DOCS_DIR.exists():
    for integration_doc in DOCS_DIR.glob("*.md"):
        # TODO: Fix the snowflake integration docs and remove this.
        if integration_doc.name in ("snowflake.md", "overview.md"):
            continue
        virtual_path = f"docs/ai_builder/integrations/{integration_doc.name}"
        vp = virtual_path.replace("\\", "/")
        actual_path = str(integration_doc).replace("\\", "/")
        if vp not in all_docs:
            doc_path_mapping[vp] = actual_path
            all_docs[vp] = actual_path

graphing_components = defaultdict(list)
component_list = defaultdict(list)
recipes_list = defaultdict(list)
docs_ns = SimpleNamespace()

doc_markdown_sources: dict[str, str] = {}


manual_titles = {
    "docs/database/overview.md": "Database Overview",
    "docs/custom-components/overview.md": "Custom Components Overview",
    "docs/custom-components/command-reference.md": "Custom Component CLI Reference",
    "docs/api-routes/overview.md": "API Routes Overview",
    "docs/client_storage/overview.md": "Client Storage Overview",
    "docs/state_structure/overview.md": "State Structure Overview",
    "docs/state/overview.md": "State Overview",
    "docs/styling/overview.md": "Styling Overview",
    "docs/ui/overview.md": "UI Overview",
    "docs/wrapping-react/overview.md": "Wrapping React Overview",
    "docs/library/html/html.md": "HTML Elements",
    "docs/recipes-overview.md": "Recipes Overview",
    "docs/events/special_events.md": "Special Events Docs",
    "docs/library/graphing/general/tooltip.md": "Graphing Tooltip",
    "docs/recipes/content/grid.md": "Grid Recipe",
    "docs/hosting/deploy-to-gcp.md": "Deploy to GCP",
    "docs/enterprise/ag_grid/index.md": "AG Grid in Python: Interactive Data Grid",
    "docs/enterprise/ag_grid/column-defs.md": "AG Grid Column Definitions in Python",
    "docs/enterprise/ag_grid/pivot-mode.md": "AG Grid Pivot Mode in Python",
    "docs/enterprise/ag_grid/cell-selection.md": "AG Grid Cell Selection in Python",
    "docs/enterprise/ag_grid/theme.md": "AG Grid Themes in Python",
    "docs/enterprise/ag_grid/model-wrapper.md": "AG Grid with a Pandas DataFrame in Python",
    "docs/enterprise/ag_grid/value-transformers.md": "AG Grid Value Transformers in Python",
    "docs/enterprise/ag_grid/aligned-grids.md": "AG Grid Aligned Grids in Python",
}


ResolvedDoc = namedtuple("ResolvedDoc", ["route", "display_title", "category"])


def doc_title_from_path(doc: str) -> str:
    """Extract a snake_case title from a doc path."""
    return rx.utils.format.to_snake_case(os.path.basename(doc).replace(".md", ""))


def doc_route_from_path(doc: str) -> str:
    """Compute the URL route from a doc path.

    Virtual paths are rooted at ``docs/`` (the content directory). The site is
    already served under ``frontend_path`` (e.g. ``/docs``), so the public path
    must not repeat that segment (``/docs/docs/...``).
    """
    doc = doc.replace("\\", "/")
    doc = doc.removeprefix("docs/")
    if doc.startswith("ai_builder/"):
        doc = "ai/" + doc.removeprefix("ai_builder/")
    route = rx.utils.format.to_kebab_case(f"/{doc.replace('.md', '/')}")
    if route.endswith("/index/"):
        route = route[:-7] + "/"
    return route


def resolve_doc_route(doc: str, title: str) -> ResolvedDoc | None:
    """Compute route, display title, and category for a doc path.

    Returns None if the doc should be skipped (suffix or whitelist).
    """
    if doc.endswith("-style.md") or doc.endswith("-ll.md"):
        return None
    doc = doc.replace("\\", "/")
    route = doc_route_from_path(doc)
    if not _check_whitelisted_path(route):
        return None
    display_title = manual_titles.get(doc, to_title_case(title))
    category = os.path.basename(os.path.dirname(doc)).title()
    return ResolvedDoc(route=route, display_title=display_title, category=category)


def extract_doc_description(
    markdown_text: str | None,
    metadata: dict | None = None,
    max_len: int = 155,
) -> str | None:
    """Derive a meta description for a documentation page.

    Prefers an explicit frontmatter ``meta_description``/``description``;
    otherwise extracts the first prose paragraph of the markdown body. Returns
    None if nothing usable is found (callers fall back to a title-based default).

    Args:
        markdown_text: The raw markdown body of the doc.
        metadata: Parsed frontmatter, if any.
        max_len: Soft maximum length for the description.

    Returns:
        A cleaned, truncated description, or None.
    """
    min_len = 120
    if metadata:
        for key in ("meta_description", "description"):
            value = metadata.get(key)
            if isinstance(value, str) and len(value.strip()) >= min_len:
                return value.strip()
    if not markdown_text:
        return None
    try:
        text = markdown_text
        # Handle a leading YAML frontmatter block (--- ... ---): use an explicit
        # description only when it's already long enough; otherwise strip the
        # block and fall through to the body prose, which is usually richer than
        # a short frontmatter field.
        frontmatter = re.match(r"﻿?\s*---\r?\n(.*?)\r?\n---\r?\n", text, flags=re.DOTALL)
        if frontmatter:
            for fm_line in frontmatter.group(1).splitlines():
                key_value = re.match(
                    r"\s*(?:meta_description|description)\s*:\s*(\S.*)", fm_line
                )
                if key_value:
                    value = key_value.group(1).strip().strip("\"'")
                    if len(value) >= min_len:
                        return value
                    # Too short: keep scanning in case a later key
                    # (e.g. `description:` after a short `meta_description:`)
                    # holds a long-enough value before falling to body prose.
            text = text[frontmatter.end() :]
        # Drop fenced code blocks (```...```), including ```python exec blocks.
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        para_lines: list[str] = []
        skip_prefixes = (
            "#",
            ">",
            "---",
            "import ",
            "from ",
            "|",
            "<",
            "- ",
            "* ",
            "rx.",
            "```",
            *(f"{n}." for n in range(1, 10)),
        )
        # Accumulate prose across paragraph breaks until the description is
        # substantial (~120 chars) so a short opening sentence doesn't become a
        # too-short meta description. Stop at the first structural line
        # (heading/list/code) once some prose has been collected.
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                if len(" ".join(para_lines)) >= min_len:
                    break
                continue
            if line.startswith(skip_prefixes):
                # At a structural line (heading/list/code): stop if we already
                # have enough prose (so a later section isn't stitched in),
                # otherwise keep gathering so short openers aren't too short.
                if len(" ".join(para_lines)) >= min_len:
                    break
                continue
            para_lines.append(line)
        if not para_lines:
            return None
        para = " ".join(para_lines)
        para = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", para)  # images
        para = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", para)  # links -> text
        para = re.sub(r"[*_`]+", "", para)  # emphasis / inline code
        # Leading reading-time marker ("3 min read", "~3 min ·"). Require a
        # "read" keyword or a "·" separator so real prose that merely opens with
        # "<n> minutes …" isn't mistaken for a badge and stripped of its subject.
        para = re.sub(r"^~?\s*\d+\s*min(?:ute)?s?\s*(?:read\s*·?|·)\s*", "", para)
        para = re.sub(r"\s+", " ", para).strip()
        # A result shorter than the target length means the page lacks
        # substantial body prose; return None so the caller's title-based
        # fallback (~115 chars) is used instead of a too-short description.
        if len(para) < min_len:
            return None
        if len(para) > max_len:
            para = para[:max_len].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
        return para or None
    except Exception:
        return None


def make_docpage(
    route: str, title: str, doc_virtual: str, render_fn, description: str | None = None
):
    """Wrap a render function as a docpage, setting module metadata."""
    doc_path = Path(doc_virtual)
    render_fn.__module__ = ".".join(doc_path.parts[:-1])
    render_fn.__name__ = doc_path.stem
    render_fn.__qualname__ = doc_path.stem
    return docpage(set_path=route, t=title, description=description)(render_fn)


CHANGELOG_VIRTUAL_PREFIX = "docs/changelog/"


def handle_changelog_doc(doc: str, actual_path: str, resolved: ResolvedDoc):
    """Handle docs/changelog/** docs — package changelogs pulled from outside the docs tree.

    Changelog markdown ships without a meaningful top-level heading, so the
    canonical page title is normalized in and the table of contents is limited
    to version headings.
    """

    def comp(_actual=actual_path, _title=resolved.display_title):
        source = normalize_changelog(Path(_actual).read_text(encoding="utf-8"), _title)
        toc, body = render_markdown_with_toc(source)
        toc = [(level, text) for level, text in toc if level <= 2]
        return ((toc, source), body)

    return make_docpage(resolved.route, resolved.display_title, doc, comp)


def handle_library_doc(
    doc: str,
    actual_path: str,
    title: str,
    resolved: ResolvedDoc,
):
    """Handle docs/library/** docs — component API reference via multi_docs."""
    clist = [title, *get_components_from_frontmatter(actual_path)]
    previews = get_previews_from_frontmatter(actual_path)
    ll_actual_path = actual_path.replace(".md", "-ll.md")
    ll_clist: list | None = None
    if os.path.exists(ll_actual_path):
        ll_clist = [title, *get_components_from_frontmatter(ll_actual_path)]
    if doc.startswith("docs/library/graphing"):
        graphing_components[resolved.category].append(clist)
    else:
        component_list[resolved.category].append(clist)
    return multi_docs(
        path=resolved.route,
        virtual_path=doc,
        actual_path=actual_path,
        previews=previews,
        component_list=clist,
        title=resolved.display_title,
        ll_component_list=ll_clist,
    )


def get_component_docgen(virtual_doc: str, actual_path: str, title: str):
    """Build a page component for a doc via reflex_docgen."""
    resolved = resolve_doc_route(virtual_doc, title)
    if resolved is None:
        return None

    if virtual_doc.startswith("docs/library"):
        return handle_library_doc(virtual_doc, actual_path, title, resolved)

    if virtual_doc.startswith(CHANGELOG_VIRTUAL_PREFIX):
        return handle_changelog_doc(virtual_doc, actual_path, resolved)

    # Read the markdown once and reuse it for both the rendered body and the
    # meta description, instead of reading the same file twice during compile.
    try:
        doc_text: str | None = Path(actual_path).read_text(encoding="utf-8")
    except Exception:
        doc_text = None

    def comp(_actual=actual_path, _virtual=virtual_doc, _content=doc_text):
        toc = get_docgen_toc(_actual)
        doc_content = (
            _content
            if _content is not None
            else Path(_actual).read_text(encoding="utf-8")
        )
        body, faq_script = render_docgen_document(
            virtual_filepath=_virtual, actual_filepath=_actual
        )
        if faq_script is not None:
            body = rx.fragment(body, faq_script)
        return ((toc, doc_content), body)

    description = extract_doc_description(doc_text)
    return make_docpage(
        resolved.route,
        resolved.display_title,
        virtual_doc,
        comp,
        description=description,
    )


# Package changelogs live outside the docs tree — the towncrier-managed ones
# at the repo root (CHANGELOG.md and packages/*/CHANGELOG.md) and the
# reflex-enterprise one inside the installed distribution. Reach up and pull
# them in as regular docs under docs/changelog/, with the main reflex
# changelog served at the section index.
changelog_packages: dict[str, str] = {}  # package name → route
for _package, _changelog_path in discover_changelogs(_docs_dir.parent).items():
    _virtual = (
        f"{CHANGELOG_VIRTUAL_PREFIX}index.md"
        if _package == "reflex"
        else f"{CHANGELOG_VIRTUAL_PREFIX}{_package}.md"
    )
    all_docs[_virtual] = str(_changelog_path)
    manual_titles[_virtual] = changelog_page_title(_package)
    changelog_packages[_package] = doc_route_from_path(_virtual)

# Build doc_markdown_sources mapping
for _virtual, _actual in all_docs.items():
    if _virtual.endswith("-style.md"):
        continue
    if _virtual.endswith("-ll.md"):
        # Register low-level docs at /<path>-ll.md so the copy button can
        # fetch them from the served URL.
        _hl_virtual = _virtual.replace("-ll.md", ".md")
        _hl_route = doc_route_from_path(_hl_virtual)
        if not _check_whitelisted_path(_hl_route):
            continue
        _ll_route = _hl_route.rstrip("/") + "-ll"
        doc_markdown_sources[_ll_route] = _actual
        continue
    _route = doc_route_from_path(_virtual)
    if not _check_whitelisted_path(_route):
        continue
    doc_markdown_sources[_route] = _actual

doc_routes = [
    library,
    custom_components,
    overview,
    *components_previews_pages,
    *apiref_pages,
    *cloud_cliref_pages,
    # * ai_builder_pages,
    *cloud_pages,
]

for cloud_page in cloud_pages:
    title = rx.utils.format.to_snake_case(cloud_page.title)
    build_nested_namespace(docs_ns, ["cloud"], title, cloud_page)

for api_route in apiref_pages:
    title = rx.utils.format.to_snake_case(api_route.title)
    build_nested_namespace(docs_ns, ["api_reference"], title, api_route)

for ref in cloud_cliref_pages:
    title = rx.utils.format.to_snake_case(ref.title)
    build_nested_namespace(docs_ns, ["cloud"], title, ref)


def register_doc(virtual_doc: str, comp):
    """Register a doc into the namespace, doc_routes, and recipes_list."""
    path = virtual_doc.split("/")[1:-1]
    title = doc_title_from_path(virtual_doc)
    title2 = to_title_case(title)
    route = doc_route_from_path(virtual_doc)

    build_nested_namespace(
        docs_ns, path, title, Route(path=route, title=title2, component=lambda: "")
    )

    if comp is not None:
        if isinstance(comp, tuple):
            doc_routes.extend(comp)
        else:
            doc_routes.append(comp)

    if "recipes" in virtual_doc:
        recipes_list[virtual_doc.split("/")[2]].append(virtual_doc)


# Alias needed by sidebar — the library page route object.
library_: Route = library  # type: ignore[assignment]


# Process all docs via reflex_docgen pipeline.
for _virtual, _actual in sorted(all_docs.items()):
    register_doc(
        _virtual,
        get_component_docgen(_virtual, _actual, doc_title_from_path(_virtual)),
    )

for name, ns in docs_ns.__dict__.items():
    globals()[name] = ns
