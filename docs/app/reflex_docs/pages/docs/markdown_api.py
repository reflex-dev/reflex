"""Write per-doc raw Markdown files under ``.web/public`` for ``<route>.md`` URLs."""

from pathlib import Path

from reflex.constants import Dirs

from reflex_docs.pages.docs import doc_markdown_sources

PUBLIC_DIR = Path.cwd() / Dirs.WEB / Dirs.PUBLIC


def generate_markdown_files() -> None:
    for route, source_path in doc_markdown_sources.items():
        resolved = Path(source_path)
        if not resolved.is_absolute():
            resolved = Path.cwd() / resolved
        if not resolved.is_file():
            continue

        dest = PUBLIC_DIR / (route.strip("/") + ".md")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(resolved.read_text(encoding="utf-8"), encoding="utf-8")
