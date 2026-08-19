"""Guard against names imported only for type checking being used as values.

`from __future__ import annotations` makes every annotation a string, so a
name imported under `if TYPE_CHECKING:` is free to appear in a signature but
raises `NameError` the moment code evaluates it. Neither pyright nor ruff
sees the problem -- pyright resolves the import, ruff sees a used name -- and
a test can miss it entirely by calling past the function that would raise.
That combination shipped a broken `rx.workflows.force_complete`.

This walks the workflow package and fails on any such name used where it will
be evaluated at runtime.
"""

import ast
from pathlib import Path

import pytest

import reflex.workflow

PACKAGE = Path(reflex.workflow.__file__).parent
MODULES = sorted(path for path in PACKAGE.glob("*.py") if path.name != "__init__.py")


def _type_only_names(tree: ast.Module) -> set[str]:
    """Collect names bound only inside ``if TYPE_CHECKING:`` blocks.

    Args:
        tree: The parsed module.

    Returns:
        The names available to annotations but not at runtime.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        guarded = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if not guarded:
            continue
        for child in ast.walk(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                names.update(
                    alias.asname or alias.name.split(".")[0] for alias in child.names
                )
            elif isinstance(child, ast.Assign):
                names.update(
                    target.id
                    for target in child.targets
                    if isinstance(target, ast.Name)
                )
    return names


def _runtime_loads(tree: ast.Module) -> set[str]:
    """Collect names the module evaluates at runtime.

    Three things are deliberately not runtime loads, and missing any of them
    makes this test cry wolf -- which is worse than not having it, because a
    false alarm gets silenced rather than read:

    * annotations, including ``*args`` and ``**kwargs``, which postponed
      evaluation never evaluates;
    * anything inside the ``if TYPE_CHECKING:`` block itself, where building
      an alias out of type-only imports is the point;
    * names a function re-imports locally before using, which is the ordinary
      way to keep a heavy import out of module scope.

    Args:
        tree: The parsed module.

    Returns:
        The names loaded where they must exist at runtime.
    """
    skip: set[int] = set()

    def skip_subtree(node: ast.AST) -> None:
        """Exclude a node and everything under it.

        Args:
            node: The subtree to exclude.
        """
        skip.update(id(child) for child in ast.walk(node))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            for arg in [
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
                arguments.vararg,
                arguments.kwarg,
            ]:
                if arg is not None and arg.annotation is not None:
                    skip_subtree(arg.annotation)
            if node.returns is not None:
                skip_subtree(node.returns)
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            skip_subtree(node.annotation)
        elif isinstance(node, ast.If):
            test = node.test
            if (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            ):
                skip_subtree(node)

    local_imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    local_imports.update(
                        alias.asname or alias.name.split(".")[0]
                        for alias in child.names
                    )

    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and id(node) not in skip
    } - local_imports


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_type_checking_import_is_evaluated_at_runtime(path: Path):
    """A type-only import used as a value is a NameError waiting for a caller.

    Args:
        path: The workflow module to check.
    """
    tree = ast.parse(path.read_text())
    offenders = _type_only_names(tree) & _runtime_loads(tree)
    assert not offenders, (
        f"{path.name} uses {sorted(offenders)} at runtime, but imports them "
        "only under TYPE_CHECKING. Move the import to module scope."
    )
