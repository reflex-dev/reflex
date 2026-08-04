"""Guard against class members shadowing builtins used as annotations in the same class."""

import ast
import builtins
import pathlib

import pytest

BUILTIN_TYPES = frozenset(
    name for name in dir(builtins) if isinstance(getattr(builtins, name), type)
)

REPO_ROOT = pathlib.Path(__file__).parents[2]
SOURCE_ROOTS = ("reflex", "packages")
SKIP_PARTS = frozenset({"node_modules", ".venv", "__pycache__", "tests", ".web"})


def _annotations(body: ast.stmt) -> list[ast.expr]:
    """Collect the annotation expressions directly attached to a class-body statement.

    Args:
        body: A statement from a class body.

    Returns:
        The annotation expressions it declares.
    """
    if isinstance(body, ast.AnnAssign):
        return [body.annotation]
    if not isinstance(body, ast.FunctionDef | ast.AsyncFunctionDef):
        return []
    annotations = [body.returns] if body.returns else []
    args = body.args
    annotations.extend(
        arg.annotation
        for arg in (
            *args.posonlyargs,
            *args.args,
            *args.kwonlyargs,
            args.vararg,
            args.kwarg,
        )
        if arg is not None and arg.annotation is not None
    )
    return annotations


def _shadowed_annotations(tree: ast.Module) -> list[tuple[str, str, int]]:
    """Find annotations resolving to a class member instead of the builtin of that name.

    Args:
        tree: The parsed module.

    Returns:
        Tuples of (class name, shadowed builtin, line number).
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        members = {
            body.name
            for body in node.body
            if isinstance(body, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        members |= {
            target.id
            for body in node.body
            if isinstance(body, ast.Assign)
            for target in body.targets
            if isinstance(target, ast.Name)
        }
        shadowed = members & BUILTIN_TYPES
        if not shadowed:
            continue
        found.extend(
            (node.name, name.id, name.lineno)
            for body in node.body
            for annotation in _annotations(body)
            for name in ast.walk(annotation)
            if isinstance(name, ast.Name) and name.id in shadowed
        )
    return found


def _source_files() -> list[pathlib.Path]:
    """Collect every first-party source file in the repo.

    Returns:
        The paths to check.
    """
    return sorted(
        path
        for root in SOURCE_ROOTS
        for path in (REPO_ROOT / root).rglob("*.py")
        if not SKIP_PARTS & set(path.parts)
    )


@pytest.mark.parametrize(
    "path", _source_files(), ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_no_builtin_shadowed_in_annotations(path: pathlib.Path):
    """A class member must not shadow a builtin the same class body uses as an annotation.

    Type checkers resolve annotations against the class namespace, so `def bool(...)`
    on `Var` makes `value: bool` on a sibling overload resolve to that method rather
    than the builtin, which silently mistypes the whole overload set.

    Args:
        path: The source file to check.
    """
    shadowed = _shadowed_annotations(ast.parse(path.read_text(encoding="utf-8")))
    assert not shadowed, "\n".join(
        f"{path.relative_to(REPO_ROOT)}:{lineno}: annotation `{name}` in class "
        f"`{cls}` resolves to its own member, use `builtins.{name}`"
        for cls, name, lineno in shadowed
    )
