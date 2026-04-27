import os
from collections import defaultdict, namedtuple
from pathlib import Path
from types import SimpleNamespace

import reflex as rx
from reflex_docgen.markdown import parse_document

# External Components
from reflex_pyplot import pyplot as pyplot
from reflex_site_shared.route import Route

from reflex_docs.docgen_pipeline import get_docgen_toc, render_docgen_document
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


def make_docpage(route: str, title: str, doc_virtual: str, render_fn):
    """Wrap a render function as a docpage, setting module metadata."""
    doc_path = Path(doc_virtual)
    render_fn.__module__ = ".".join(doc_path.parts[:-1])
    render_fn.__name__ = doc_path.stem
    render_fn.__qualname__ = doc_path.stem
    return docpage(set_path=route, t=title)(render_fn)


def handle_library_doc(
    doc: str,
    actual_path: str,
    title: str,
    resolved: ResolvedDoc,
):
    """Handle docs/library/** docs — component API reference via multi_docs."""
    clist = [title, *get_components_from_frontmatter(actual_path)]
    previews = get_previews_from_frontmatter(actual_path)
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
    )


def get_component_docgen(virtual_doc: str, actual_path: str, title: str):
    """Build a page component for a doc via reflex_docgen."""
    resolved = resolve_doc_route(virtual_doc, title)
    if resolved is None:
        return None

    if virtual_doc.startswith("docs/library"):
        return handle_library_doc(virtual_doc, actual_path, title, resolved)

    def comp(_actual=actual_path, _virtual=virtual_doc):
        toc = get_docgen_toc(_actual)
        doc_content = Path(_actual).read_text(encoding="utf-8")
        rendered = render_docgen_document(
            virtual_filepath=_virtual, actual_filepath=_actual
        )
        return ((toc, doc_content), rendered)

    return make_docpage(resolved.route, resolved.display_title, virtual_doc, comp)


# Build doc_markdown_sources mapping
for _virtual, _actual in all_docs.items():
    if _virtual.endswith("-style.md") or _virtual.endswith("-ll.md"):
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
