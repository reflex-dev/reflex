"""Every module in the docs app must be reachable from the app or its content."""

import ast
import re
import textwrap
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = APP_ROOT / "reflex_docs"
DOCS_ROOT = APP_ROOT.parent
PYTHON_BLOCK = re.compile(
    r"^([ \t]*)(`{3,})python[^\n]*\n(.*?)^\1\2(?!`)", re.MULTILINE | re.DOTALL
)


def _module_name(path: Path) -> str:
    """Return the dotted module name of a file in the docs app package.

    Args:
        path: A Python file under the package.

    Returns:
        The module name, naming a package by its directory.
    """
    parts = path.relative_to(APP_ROOT).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imported_names(source: str, module: str, is_package: bool) -> set[str]:
    """Collect every dotted name an import statement in the source may refer to.

    Args:
        source: The Python source.
        module: The importing module's name, used to resolve relative imports.
        is_package: Whether the importing module is a package's ``__init__``.

    Returns:
        Imported module names and ``module.attribute`` names.
    """
    package = module.split(".") if is_package else module.split(".")[:-1]
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - node.level + 1] if node.level else []
            target = ".".join([*base, *([node.module] if node.module else [])])
            names.add(target)
            names.update(f"{target}.{alias.name}" for alias in node.names)
    return names


def _markdown_imported_names(markdown: str) -> set[str]:
    """Collect the names a Markdown file's Python code blocks import.

    Blocks that are not valid Python are display-only snippets and are skipped.

    Args:
        markdown: The Markdown source.

    Returns:
        Imported module names and ``module.attribute`` names.
    """
    names = set()
    for _, _, code in PYTHON_BLOCK.findall(markdown):
        try:
            names |= _imported_names(textwrap.dedent(code), "markdown", False)
        except SyntaxError:
            continue
    return names


def _reachable(modules: dict[str, set[str]], roots: set[str]) -> set[str]:
    """Walk the import graph from the roots, including each module's parents.

    Args:
        modules: Each module's imported names.
        roots: Names imported by the entry points.

    Returns:
        The names of every reachable module.
    """
    seen: set[str] = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        parts = name.split(".")
        for end in range(1, len(parts) + 1):
            prefix = ".".join(parts[:end])
            if prefix in modules and prefix not in seen:
                seen.add(prefix)
                pending.extend(modules[prefix])
    return seen


def test_markdown_imports_include_every_import_form():
    """Every import form in a Markdown code block keeps its docs modules reachable."""
    markdown = (
        "```python exec\n"
        "import os, reflex_docs.views\n"
        "from reflex_docs.pages import gallery as g, landing\n"
        "from reflex_docs.components import (\n"
        "    hint,\n"
        "    button,\n"
        ")\n"
        "```\n"
        "- Indented block:\n"
        "  ```python\n"
        "  from reflex_docs.utils import *\n"
        "  ```\n"
        "```python\n"
        "from reflex_docs.models import (\n"
        "```\n"
        "````python demo\n"
        "from reflex_docs.templates import docpage\n"
        'rx.markdown("""```python\nprint()\n```""")\n'
        "````\n"
    )
    assert _markdown_imported_names(markdown) == {
        "os",
        "reflex_docs.views",
        "reflex_docs.pages",
        "reflex_docs.pages.gallery",
        "reflex_docs.pages.landing",
        "reflex_docs.components",
        "reflex_docs.components.hint",
        "reflex_docs.components.button",
        "reflex_docs.utils",
        "reflex_docs.utils.*",
        "reflex_docs.templates",
        "reflex_docs.templates.docpage",
    }


def test_every_docs_app_module_is_reachable():
    """Unimported modules are dead code; delete them instead of shipping them."""
    modules = {
        _module_name(path): _imported_names(
            path.read_text(encoding="utf-8"),
            _module_name(path),
            path.name == "__init__.py",
        )
        for path in PACKAGE.rglob("*.py")
    }
    roots = {"reflex_docs.reflex_docs"}
    for entry in [APP_ROOT / "rxconfig.py", *(APP_ROOT / "agent_files").rglob("*.py")]:
        roots |= _imported_names(
            entry.read_text(encoding="utf-8"),
            _module_name(entry),
            entry.name == "__init__.py",
        )
    for markdown in DOCS_ROOT.rglob("*.md"):
        roots |= _markdown_imported_names(markdown.read_text(encoding="utf-8"))
    assert sorted(set(modules) - _reachable(modules, roots)) == []
