"""Every module in the docs app must be reachable from the app or its content."""

import ast
import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = APP_ROOT / "reflex_docs"
DOCS_ROOT = APP_ROOT.parent
MARKDOWN_IMPORT = re.compile(r"^\s*(?:from|import)\s+(reflex_docs[\w.]*)", re.MULTILINE)


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
        roots.update(MARKDOWN_IMPORT.findall(markdown.read_text(encoding="utf-8")))
    assert sorted(set(modules) - _reachable(modules, roots)) == []
