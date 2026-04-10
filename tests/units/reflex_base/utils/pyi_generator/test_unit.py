"""Unit tests for individual pyi_generator translation functions.

Tests smaller functions in isolation using "code in -> expected code out"
patterns. These complement the golden file regression tests by testing
edge cases in type resolution and AST generation directly.
"""

from __future__ import annotations

import ast
import linecache
import sys
import types as builtin_types
import typing
from types import SimpleNamespace
from typing import Any, Literal, Optional, Union

import pytest
from reflex_base.components.component import Component
from reflex_base.utils.pyi_generator import (
    StubGenerator,
    _get_type_hint,
    _is_literal,
    _is_optional,
    _is_union,
    _safe_issubclass,
    type_to_ast,
)
from reflex_base.vars.base import Var


def test_is_union_typing_union():
    assert _is_union(Union[str, int]) is True  # noqa: UP007


def test_is_union_pipe_union():
    assert _is_union(str | int) is True


def test_is_union_optional_is_union():
    assert _is_union(Optional[str]) is True  # noqa: UP045


def test_is_union_plain_type():
    assert _is_union(str) is False


def test_is_union_none():
    assert _is_union(None) is False


def test_is_union_var():
    assert _is_union(Var[str]) is False


def test_is_optional_none_value():
    assert _is_optional(None) is True


def test_is_optional_none_type():
    assert _is_optional(type(None)) is True


def test_is_optional_optional_type():
    assert _is_optional(Optional[str]) is True  # noqa: UP045


def test_is_optional_union_with_none():
    assert _is_optional(str | None) is True


def test_is_optional_plain_type():
    assert _is_optional(str) is False


def test_is_optional_union_without_none():
    assert _is_optional(str | int) is False


def test_is_literal_literal_type():
    assert _is_literal(Literal["a", "b"]) is True


def test_is_literal_plain_type():
    assert _is_literal(str) is False


def test_is_literal_none():
    assert _is_literal(None) is False


def test_safe_issubclass_true():
    assert _safe_issubclass(bool, int) is True


def test_safe_issubclass_false():
    assert _safe_issubclass(str, int) is False


def test_safe_issubclass_non_type():
    assert _safe_issubclass("not a type", int) is False


def test_safe_issubclass_none():
    assert _safe_issubclass(None, int) is False


@pytest.fixture
def type_hint_globals():
    """Provide a type_hint_globals dict with common types.

    Returns:
        A dict mapping type names to their corresponding types, including built-ins, typing constructs, and
        custom types.
    """
    return {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "Var": Var,
        "Any": Any,
        "Literal": Literal,
        "Optional": Optional,
        "Union": Union,
        **{name: getattr(typing, name) for name in ["Sequence", "Mapping"]},
    }


def test_get_type_hint_none_value(type_hint_globals):
    assert _get_type_hint(None, type_hint_globals) == "None"


def test_get_type_hint_none_type(type_hint_globals):
    assert _get_type_hint(type(None), type_hint_globals) == "None"


def test_get_type_hint_simple_optional(type_hint_globals):
    assert _get_type_hint(str, type_hint_globals, is_optional=True) == "str | None"


def test_get_type_hint_simple_not_optional(type_hint_globals):
    assert _get_type_hint(str, type_hint_globals, is_optional=False) == "str"


def test_get_type_hint_optional_union(type_hint_globals):
    assert _get_type_hint(Optional[str], type_hint_globals) == "str | None"  # noqa: UP045


def test_get_type_hint_union_without_none(type_hint_globals):
    result = _get_type_hint(Union[str, int], type_hint_globals, is_optional=False)  # noqa: UP007
    assert result == "int | str"


def test_get_type_hint_union_with_none(type_hint_globals):
    result = _get_type_hint(Union[str, int, None], type_hint_globals)  # noqa: UP007
    assert result == "int | str | None"


def test_get_type_hint_var_expansion(type_hint_globals):
    """Var[str] should expand to Var[str] | str."""
    result = _get_type_hint(Var[str], type_hint_globals, is_optional=False)
    assert result == "Var[str] | str"


def test_get_type_hint_var_union_expansion(type_hint_globals):
    """Var[str | int] should expand to include Var, str, and int."""
    result = _get_type_hint(Var[str | int], type_hint_globals, is_optional=False)
    parts = {p.strip() for p in result.split("|")}
    assert "str" in parts
    assert "int" in parts
    assert any("Var[" in p for p in parts)


def test_get_type_hint_literal(type_hint_globals):
    result = _get_type_hint(
        Literal["a", "b", "c"], type_hint_globals, is_optional=False
    )
    assert result == "Literal['a', 'b', 'c']"


def test_type_to_ast_none_type():
    node = type_to_ast(type(None), Component)
    assert isinstance(node, ast.Name)
    assert node.id == "None"


def test_type_to_ast_none_value():
    node = type_to_ast(None, Component)
    assert isinstance(node, ast.Name)
    assert node.id == "None"


def test_type_to_ast_simple_type():
    node = type_to_ast(str, Component)
    assert isinstance(node, ast.Name)
    assert node.id == "str"


def test_type_to_ast_literal():
    node = type_to_ast(Literal["x", "y"], Component)
    assert isinstance(node, ast.Subscript)
    unparsed = ast.unparse(node)
    assert "Literal" in unparsed
    assert "'x'" in unparsed
    assert "'y'" in unparsed


def test_type_to_ast_union():
    node = type_to_ast(Union[str, int], Component)  # noqa: UP007
    assert isinstance(node, ast.Subscript)
    unparsed = ast.unparse(node)
    assert "str" in unparsed
    assert "int" in unparsed


def test_type_to_ast_generic():
    node = type_to_ast(list[str], Component)
    unparsed = ast.unparse(node)
    assert "list" in unparsed
    assert "str" in unparsed


def test_type_to_ast_nested_generic():
    node = type_to_ast(dict[str, list[int]], Component)
    unparsed = ast.unparse(node)
    assert "dict" in unparsed
    assert "str" in unparsed
    assert "list" in unparsed
    assert "int" in unparsed


_stub_gen_counter = 0


def _generate_stub_from_source(source: str) -> str:
    """Parse source, run StubGenerator, return unparsed result.

    Args:
        source: The Python source code to generate a stub from.

    Returns:
        The generated stub code as a string.
    """
    global _stub_gen_counter
    _stub_gen_counter += 1
    module_name = f"_pyi_test_mod_{_stub_gen_counter}"
    filename = f"{module_name}.py"

    linecache.cache[filename] = (
        len(source),
        None,
        source.splitlines(keepends=True),
        filename,
    )

    mod = builtin_types.ModuleType(module_name)
    mod.__file__ = filename
    sys.modules[module_name] = mod
    try:
        exec(compile(source, filename, "exec"), mod.__dict__)

        for obj in vars(mod).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, Component)
                and obj is not Component
            ):
                obj.__module__ = module_name

        classes: dict[str, type[Component] | type[SimpleNamespace]] = {
            name: obj
            for name, obj in vars(mod).items()
            if isinstance(obj, type)
            and issubclass(obj, Component)
            and obj is not Component
        }

        tree = ast.parse(source)
        generator = StubGenerator(mod, classes)
        new_tree = generator.visit(tree)
        return ast.unparse(new_tree)
    finally:
        sys.modules.pop(module_name, None)
        linecache.cache.pop(filename, None)


def test_stub_private_method_removed():
    source = """
from reflex_base.components.component import Component
from reflex_base.vars.base import Var

class Foo(Component):
    x: Var[str]
    def _hidden(self): pass
    def visible(self): return 1
"""
    result = _generate_stub_from_source(source)
    assert "def _hidden" not in result
    assert "def visible" in result
    # Public method body should be blanked to ellipsis.
    assert "return 1" not in result


def test_stub_module_docstring_removed():
    source = '''"""This is a module docstring."""
from reflex_base.components.component import Component
from reflex_base.vars.base import Var

class Bar(Component):
    y: Var[int]
'''
    result = _generate_stub_from_source(source)
    assert "This is a module docstring" not in result
    # Should still have the class and create method.
    assert "class Bar" in result
    assert "def create" in result


def test_stub_future_import_removed():
    source = """from __future__ import annotations
from reflex_base.components.component import Component
from reflex_base.vars.base import Var

class Baz(Component):
    z: Var[bool]
"""
    result = _generate_stub_from_source(source)
    assert "__future__" not in result
    # Default imports should be injected instead.
    assert "from reflex_base.event import" in result


def test_stub_class_docstring_removed():
    source = '''
from reflex_base.components.component import Component
from reflex_base.vars.base import Var

class DocComponent(Component):
    """This class docstring should be removed."""
    val: Var[str]
'''
    result = _generate_stub_from_source(source)
    assert "This class docstring should be removed" not in result
    assert "class DocComponent" in result


def test_stub_non_annotated_assignment_removed():
    source = """
from reflex_base.components.component import Component
from reflex_base.vars.base import Var

class AssignComp(Component):
    some_const = "hello"
    val: Var[str]
"""
    result = _generate_stub_from_source(source)
    assert "some_const" not in result
    assert "hello" not in result


def test_stub_any_assignment_preserved():
    source = """
from typing import Any
from reflex_base.components.component import Component
from reflex_base.vars.base import Var

SomeAlias = Any

class AnyComp(Component):
    val: Var[str]
"""
    result = _generate_stub_from_source(source)
    assert "SomeAlias = Any" in result


def test_stub_annotated_assignment_value_blanked():
    source = """
from reflex_base.components.component import Component
from reflex_base.vars.base import Var

mode: str = "default"

class ModeComp(Component):
    val: Var[str]
"""
    result = _generate_stub_from_source(source)
    assert "mode: str" in result
    # Value should be stripped — only the annotation remains.
    assert '"default"' not in result
    assert "mode: str =" not in result


def test_stub_classvar_preserved():
    source = """
from typing import ClassVar
from reflex_base.components.component import Component
from reflex_base.vars.base import Var

class CVComp(Component):
    allowed_types: ClassVar[list[str]] = ["A"]
    val: Var[str]
"""
    result = _generate_stub_from_source(source)
    assert "ClassVar[list[str]]" in result
    # ClassVar props should NOT appear as create() kwargs.
    assert "allowed_types" not in result.split("def create")[1]


def test_stub_private_classvar_removed():
    source = """
from typing import ClassVar
from reflex_base.components.component import Component
from reflex_base.vars.base import Var

class PVComp(Component):
    _valid_children: ClassVar[list[str]] = ["A"]
    val: Var[str]
"""
    result = _generate_stub_from_source(source)
    # Private ClassVar annotations are stripped entirely.
    assert "_valid_children" not in result


def test_stub_public_function_body_blanked():
    source = """
from reflex_base.components.component import Component
from reflex_base.vars.base import Var

class FuncComp(Component):
    val: Var[str]
    def helper(self) -> str:
        x = 1
        y = 2
        return str(x + y)
"""
    result = _generate_stub_from_source(source)
    assert "def helper(self) -> str:" in result
    assert "x = 1" not in result
    assert "x + y" not in result


def test_stub_create_method_generated():
    source = """
from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var

class CreateComp(Component):
    name: Var[str] = field(doc="The name.")
"""
    result = _generate_stub_from_source(source)
    assert "@classmethod" in result
    assert "def create(cls, *children" in result
    # name prop should appear as a keyword arg with Var expansion.
    assert "name:" in result
    assert "**props" in result
    # Return type should reference the class.
    assert "CreateComp" in result
