"""The pyi generator module."""

from _ast import ClassDef, FunctionDef, Import, ImportFrom
import ast
import importlib
import inspect
import os
import re
import subprocess
import sys
from inspect import getfullargspec
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Literal, Optional, Set, Type, Union, get_args  # NOQA

import black

from reflex.components.component import Component

# NOQA
from reflex.components.graphing.recharts.recharts import (
    LiteralAnimationEasing,
    LiteralAreaType,
    LiteralComposedChartBaseValue,
    LiteralDirection,
    LiteralGridType,
    LiteralIconType,
    LiteralIfOverflow,
    LiteralInterval,
    LiteralLayout,
    LiteralLegendAlign,
    LiteralLineType,
    LiteralOrientationTopBottom,
    LiteralOrientationTopBottomLeftRight,
    LiteralPolarRadiusType,
    LiteralPosition,
    LiteralScale,
    LiteralShape,
    LiteralStackOffset,
    LiteralSyncMethod,
    LiteralVerticalAlign,
)
from reflex.components.libs.chakra import (
    LiteralAlertDialogSize,
    LiteralAvatarSize,
    LiteralChakraDirection,
    LiteralColorScheme,
    LiteralDrawerSize,
    LiteralImageLoading,
    LiteralInputVariant,
    LiteralMenuOption,
    LiteralMenuStrategy,
    LiteralTagSize,
)
from reflex.components.radix.themes.base import (
    LiteralAccentColor,
    LiteralAlign,
    LiteralAppearance,
    LiteralGrayColor,
    LiteralJustify,
    LiteralPanelBackground,
    LiteralRadius,
    LiteralScaling,
    LiteralSize,
    LiteralVariant,
)
from reflex.components.radix.themes.components import (
    LiteralButtonSize,
    LiteralSwitchSize,
)
from reflex.components.radix.themes.layout import (
    LiteralBoolNumber,
    LiteralContainerSize,
    LiteralFlexDirection,
    LiteralFlexDisplay,
    LiteralFlexWrap,
    LiteralGridDisplay,
    LiteralGridFlow,
    LiteralSectionSize,
)
from reflex.components.radix.themes.typography import (
    LiteralLinkUnderline,
    LiteralTextAlign,
    LiteralTextSize,
    LiteralTextTrim,
    LiteralTextWeight,
)

# NOQA
from reflex.event import EventChain
from reflex.style import Style
from reflex.utils import format
from reflex.utils import types as rx_types
from reflex.vars import Var

ruff_dont_remove = [
    Var,
    Optional,
    Dict,
    List,
    EventChain,
    Style,
    LiteralInputVariant,
    LiteralColorScheme,
    LiteralChakraDirection,
    LiteralTagSize,
    LiteralDrawerSize,
    LiteralMenuStrategy,
    LiteralMenuOption,
    LiteralAlertDialogSize,
    LiteralAvatarSize,
    LiteralImageLoading,
    LiteralLayout,
    LiteralAnimationEasing,
    LiteralGridType,
    LiteralPolarRadiusType,
    LiteralScale,
    LiteralSyncMethod,
    LiteralStackOffset,
    LiteralComposedChartBaseValue,
    LiteralOrientationTopBottom,
    LiteralAreaType,
    LiteralShape,
    LiteralLineType,
    LiteralDirection,
    LiteralIfOverflow,
    LiteralOrientationTopBottomLeftRight,
    LiteralInterval,
    LiteralLegendAlign,
    LiteralVerticalAlign,
    LiteralIconType,
    LiteralPosition,
    LiteralAccentColor,
    LiteralAlign,
    LiteralAppearance,
    LiteralBoolNumber,
    LiteralButtonSize,
    LiteralContainerSize,
    LiteralFlexDirection,
    LiteralFlexDisplay,
    LiteralFlexWrap,
    LiteralGrayColor,
    LiteralGridDisplay,
    LiteralGridFlow,
    LiteralJustify,
    LiteralLinkUnderline,
    LiteralPanelBackground,
    LiteralRadius,
    LiteralScaling,
    LiteralSectionSize,
    LiteralSize,
    LiteralSwitchSize,
    LiteralTextAlign,
    LiteralTextSize,
    LiteralTextTrim,
    LiteralTextWeight,
    LiteralVariant,
]

EXCLUDED_FILES = [
    "__init__.py",
    "component.py",
    "bare.py",
    "foreach.py",
    "cond.py",
    "multiselect.py",
]

# These props exist on the base component, but should not be exposed in create methods.
EXCLUDED_PROPS = [
    "alias",
    "children",
    "event_triggers",
    "invalid_children",
    "library",
    "lib_dependencies",
    "tag",
    "is_default",
    "special_props",
    "valid_children",
]

DEFAULT_TYPING_IMPORTS = {"overload", "Any", "Dict", "List", "Optional", "Union"}

STUBS_FOLDER = "stubs"


def _get_type_hint(value, top_level=True, no_union=False):
    res = ""
    args = get_args(value)
    if args:
        inner_container_type_args = (
            [format.wrap(arg, '"') for arg in args]
            if rx_types.is_literal(value)
            else [
                _get_type_hint(arg, top_level=False)
                for arg in args
                if arg is not type(None)
            ]
        )
        res = f"{value.__name__}[{', '.join(inner_container_type_args)}]"

        if value.__name__ == "Var":
            types = [res] + [
                _get_type_hint(arg, top_level=False)
                for arg in args
                if arg is not type(None)
            ]
            if len(types) > 1 and not no_union:
                res = ", ".join(types)
                res = f"Union[{res}]"
    elif isinstance(value, str):
        ev = eval(value)
        res = _get_type_hint(ev, top_level=False) if ev.__name__ == "Var" else value
    else:
        res = value.__name__
    if top_level and not res.startswith("Optional"):
        res = f"Optional[{res}]"
    return res


def _get_typing_import(_module):
    # should not be needed any more

    src = [
        line
        for line in inspect.getsource(_module).split("\n")
        if line.startswith("from typing")
    ]
    if len(src):
        return set(src[0].rpartition("from typing import ")[-1].split(", "))
    return set()


class StubGenerator(ast.NodeTransformer):
    def __init__(self, module: ModuleType, classes: dict[str, Type], *args, **kwargs):
        self.classes = classes
        self.current_class = None
        self.inserted_imports = False
        self.typing_imports = DEFAULT_TYPING_IMPORTS | _get_typing_import(module)
        super().__init__(*args, **kwargs)

    def visit_Import(self, node: Import) -> Any:
        if not self.inserted_imports:
            self.inserted_imports = True
            return self._generate_imports(self.typing_imports) + [node]
        return node

    def visit_ImportFrom(self, node: ImportFrom) -> Any:
        if node.module == "__future__":
            return None  # ignore __future__ imports
        return self.visit_Import(node)

    def visit_ClassDef(self, node: ClassDef) -> Any:
        self.current_class = node.name
        for child in node.body[:]:
            # Remove all assignments in the class body
            if isinstance(child, (ast.AnnAssign, ast.Assign)):
                node.body.remove(child)
        if not any(isinstance(child, ast.FunctionDef) and child.name == "create" for child in node.body):
            node.body.append(
                self._generate_pyi_class(None, self.classes[self.current_class])
            )
        else:
            self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: FunctionDef) -> Any:
        if node.name == "create":
            node = self._generate_pyi_class(node, self.classes[self.current_class])
        else:
            # blank out the function body
            if isinstance(node.body[0], ast.Expr):
                node.body = node.body[:1]  # only keep the docstring
            else:
                node.body = [ast.Ellipsis()]
        self.generic_visit(node)
        return node

    def _generate_pyi_class(self, node: ast.FunctionDef, _class: type[Component]):
        create_spec = getfullargspec(_class.create)

        kwargs = [
            (
                ast.arg(
                    arg=kwarg,
                    annotation=_get_type_hint(create_spec.annotations[kwarg]),
                ),
                None,
            )
            if kwarg in create_spec.annotations
            else (ast.arg(kwarg), None)
            for kwarg in create_spec.kwonlyargs
        ]

        all_classes = [c for c in _class.__mro__ if issubclass(c, Component)]
        all_props = []
        for target_class in all_classes:
            for name, value in target_class.__annotations__.items():
                if (
                    name in create_spec.kwonlyargs
                    or name in EXCLUDED_PROPS
                    or name in all_props
                ):
                    continue
                all_props.append(name)

                kwargs.append(
                    (
                        ast.arg(
                            arg=name, annotation=ast.Name(id=_get_type_hint(value))
                        ),
                        ast.Constant(value=None),
                    )
                )
        kwargs.extend(
            [
                (
                    ast.arg(
                        arg=trigger,
                        annotation=ast.Name(
                            id="Optional[Union[EventHandler, EventSpec, List, function, BaseVar]]"
                        ),
                    ),
                    ast.Constant(value=None),
                )
                for trigger in sorted(_class().get_event_triggers().keys())
            ]
        )
        create_args = ast.arguments(
            args=[ast.arg(arg="cls")],
            posonlyargs=[],
            vararg=ast.arg(arg="children"),
            kwonlyargs=[arg[0] for arg in kwargs],
            kw_defaults=[arg[1] for arg in kwargs],
            kwarg=ast.arg(arg="props"),
            defaults=[],
        )
        definition = ast.FunctionDef(
            name="create",
            args=create_args,
            body=[
                ast.Expr(value=ast.Constant(value=self._generate_docstrings(all_classes, all_props))),
            ],
            decorator_list=[ast.Name(id="overload"), *(node.decorator_list if node is not None else [ast.Name(id="classmethod")])],
            lineno=node.lineno if node is not None else None,
            returns=ast.Constant(value=_class.__name__),
        )
        return definition

    def _generate_docstrings(self, _classes, _props):
        props_comments = {}
        comments = []
        for _class in _classes:
            for _i, line in enumerate(inspect.getsource(_class).splitlines()):
                reached_functions = re.search("def ", line)
                if reached_functions:
                    # We've reached the functions, so stop.
                    break

                # Get comments for prop
                if line.strip().startswith("#"):
                    comments.append(line)
                    continue

                # Check if this line has a prop.
                match = re.search("\\w+:", line)
                if match is None:
                    # This line doesn't have a var, so continue.
                    continue

                # Get the prop.
                prop = match.group(0).strip(":")
                if prop in _props:
                    if not comments:  # do not include undocumented props
                        continue
                    props_comments[prop] = "\n".join(
                        [comment.strip().strip("#") for comment in comments]
                    )
                    comments.clear()
                    continue
                if prop in EXCLUDED_PROPS:
                    comments.clear()  # throw away comments for excluded props
        _class = _classes[0]
        new_docstring = []
        for i, line in enumerate(_class.create.__doc__.splitlines()):
            new_docstring.append(line)
            if "*children" in line:
                for nline in [
                    f"{line.split('*')[0]}{n}:{c}" for n, c in props_comments.items()
                ]:
                    new_docstring.append(nline)
        return "\n".join(new_docstring)

    def _generate_imports(self, typing_imports):
        return [
            ast.ImportFrom(
                module="typing",
                names=[
                    ast.alias(name=imp)
                    for imp in typing_imports
                ]
            ),
            ast.ImportFrom(
                module="reflex.vars",
                names=[
                    ast.alias(name="Var"),
                    ast.alias(name="BaseVar"),
                    ast.alias(name="ComputedVar"),
                ],
            ),
            ast.ImportFrom(
                module="reflex.event",
                names=[
                    ast.alias(name="EventHandler"),
                    ast.alias(name="EventChain"),
                    ast.alias(name="EventSpec"),
                ],
            ),
            ast.ImportFrom(
                module="reflex.style",
                names=[
                    ast.alias(name="Style"),
                ],
            ),
        ]


class PyiGenerator:
    """A .pyi file generator that will scan all defined Component in Reflex and
    generate the approriate stub.
    """

    modules: list = []
    root: str = ""
    current_module: Any = {}
    default_typing_imports: set = DEFAULT_TYPING_IMPORTS

    def _write_pyi_file(self, module_path: Path, source: str):
        pyi_content = [
            f'"""Stub file for {module_path}"""',
            "# ------------------- DO NOT EDIT ----------------------",
            "# This file was generated by `scripts/pyi_generator.py`!",
            "# ------------------------------------------------------",
            "",
            source,
        ]

        pyi_path = module_path.with_suffix(".pyi")
        pyi_path.write_text("\n".join(pyi_content))

        black.format_file_in_place(
            src=pyi_path,
            fast=True,
            mode=black.FileMode(),
            write_back=black.WriteBack.YES,
        )
        # TODO: need a way to add `type: ignore` comments on the `def create` line

    def _scan_file(self, module_path: Path):
        module_import = str(module_path.with_suffix("")).replace("/", ".")
        module = importlib.import_module(module_import)

        class_names = {
            name: obj
            for name, obj in vars(module).items()
            if inspect.isclass(obj)
            and issubclass(obj, Component)
            and obj != Component
            and inspect.getmodule(obj) == module
        }
        if not class_names:
            return

        new_tree = StubGenerator(module, class_names).visit(ast.parse(inspect.getsource(module)))
        self._write_pyi_file(module_path, ast.unparse(new_tree))

    def _scan_folder(self, folder):
        for root, _, files in os.walk(folder):
            for file in files:
                if file in EXCLUDED_FILES:
                    continue
                if file.endswith(".py"):
                    self._scan_file(Path(root) / file)

    def scan_all(self, targets):
        """Scan all targets for class inheriting Component and generate the .pyi files.

        Args:
            targets: the list of file/folders to scan.
        """
        for target in targets:
            if target.endswith(".py"):
                file = target.rpartition("/")[2]
                self._scan_file(file)
            else:
                self._scan_folder(target)


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["reflex/components"]
    print(f"Running .pyi generator for {targets}")
    gen = PyiGenerator()
    gen.scan_all(targets)
