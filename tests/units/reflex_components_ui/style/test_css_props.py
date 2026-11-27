"""Tests for what a type checker makes of the generated style types."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _pyright(tmp_path: Path, fixture: str) -> list[tuple[int, str, str]]:
    """Run pyright over a fixture, outside the configuration of the repository.

    The fixtures are kept as text so that no other tool checks them.

    Args:
        tmp_path: A directory to copy the fixture to.
        fixture: The name of the fixture, without its extension.

    Returns:
        The line, rule and whole message of every diagnostic.
    """
    target = tmp_path / f"{fixture}.py"
    shutil.copy(FIXTURES / f"{fixture}.py.txt", target)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pyright",
            "--outputjson",
            "--pythonpath",
            sys.executable,
            str(target),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    diagnostics = json.loads(result.stdout)["generalDiagnostics"]
    assert {diagnostic["file"] for diagnostic in diagnostics} <= {str(target)}
    return [
        (
            diagnostic["range"]["start"]["line"] + 1,
            diagnostic["rule"],
            diagnostic["message"],
        )
        for diagnostic in diagnostics
    ]


def test_valid_styles_type_check(tmp_path: Path):
    """What Reflex users write today, and a style table, raise nothing."""
    assert _pyright(tmp_path, "style_valid") == []


def test_invalid_styles_are_type_errors(tmp_path: Path):
    """A misspelt property, keyword or table key is caught before compiling."""
    assert _pyright(tmp_path, "style_errors") == EXPECTED_ERRORS


EXPECTED_ERRORS: list[tuple[int, str, str]] = [
    (
        6,
        "reportAssignmentType",
        (
            'Type "dict[str, str]" is not assignable to declared type "StyleProps"\n'
            '\xa0\xa0"paddng" is an undefined item in type "StyleProps"'
        ),
    ),
    (
        8,
        "reportAssignmentType",
        (
            'Type "dict[str, str]" is not assignable to declared type "StyleProps"\n'
            '\xa0\xa0Type "Literal[\'flx\']" is not assignable to type "_Value[_Display | '
            '_StrVar]"\n'
            '\xa0\xa0\xa0\xa0"Literal[\'flx\']" is not assignable to "Var[str]"\n'
            '\xa0\xa0\xa0\xa0"Literal[\'flx\']" is not assignable to "Sequence[_Display | '
            '_StrVar]"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0Type parameter "_T_co@Sequence" is covariant, but "str" is '
            'not a subtype of "_Display | _StrVar"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0Type "str" is not assignable to type "_Display | '
            '_StrVar"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to "Var[str]"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to type '
            "\"Literal['-webkit-box']\"\n"
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to type '
            "\"Literal['block']\""
        ),
    ),
    (
        10,
        "reportAssignmentType",
        (
            'Type "dict[str, int]" is not assignable to declared type "StyleProps"\n'
            '\xa0\xa0Type "Literal[1]" is not assignable to type "_Value[_Position | _StrVar]"\n'
            '\xa0\xa0\xa0\xa0"Literal[1]" is not assignable to "Var[str]"\n'
            '\xa0\xa0\xa0\xa0"Literal[1]" is not assignable to "Sequence[_Position | _StrVar]"\n'
            '\xa0\xa0\xa0\xa0"Literal[1]" is not assignable to "Breakpoints[Any, Any]"\n'
            '\xa0\xa0\xa0\xa0"Literal[1]" is not assignable to "Mapping[str, _Position | _StrVar '
            '| Mapping[str, _Position | _StrVar]]"\n'
            '\xa0\xa0\xa0\xa0"Literal[1]" is not assignable to "Literal[\'absolute\']"\n'
            '\xa0\xa0\xa0\xa0"Literal[1]" is not assignable to "Literal[\'fixed\']"\n'
            '\xa0\xa0\xa0\xa0"Literal[1]" is not assignable to "Literal[\'inherit\']"'
        ),
    ),
    (
        12,
        "reportAssignmentType",
        (
            'Type "dict[str, dict[str, str]]" is not assignable to declared type "StyleProps"\n'
            '\xa0\xa0Type "dict[str, str]" is not assignable to type "_Value[_Display | '
            '_StrVar]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "Var[str]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "Sequence[_Display | '
            '_StrVar]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "Breakpoints[Any, Any]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "Mapping[str, _Display | '
            '_StrVar | Mapping[str, _Display | _StrVar]]"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0Type parameter "_VT_co@Mapping" is covariant, but "str" is '
            'not a subtype of "_Display | _StrVar | Mapping[str, _Display | _StrVar]"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0Type "str" is not assignable to type "_Display | '
            '_StrVar | Mapping[str, _Display | _StrVar]"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to "Var[str]"'
        ),
    ),
    (
        14,
        "reportAssignmentType",
        (
            'Type "dict[str, list[str]]" is not assignable to declared type "StyleProps"\n'
            '\xa0\xa0Type "Literal[\'flx\']" is not assignable to type "_Display | _StrVar"\n'
            '\xa0\xa0\xa0\xa0"Literal[\'flx\']" is not assignable to "Var[str]"\n'
            "\xa0\xa0\xa0\xa0\"Literal['flx']\" is not assignable to type "
            "\"Literal['-webkit-box']\"\n"
            "\xa0\xa0\xa0\xa0\"Literal['flx']\" is not assignable to type \"Literal['block']\"\n"
            "\xa0\xa0\xa0\xa0\"Literal['flx']\" is not assignable to type "
            "\"Literal['contents']\"\n"
            "\xa0\xa0\xa0\xa0\"Literal['flx']\" is not assignable to type \"Literal['flex']\"\n"
            "\xa0\xa0\xa0\xa0\"Literal['flx']\" is not assignable to type "
            "\"Literal['flow-root']\"\n"
            "\xa0\xa0\xa0\xa0\"Literal['flx']\" is not assignable to type \"Literal['grid']\""
        ),
    ),
    (
        16,
        "reportAssignmentType",
        (
            'Type "dict[str, dict[str, str]]" is not assignable to declared type "StyleProps"\n'
            '\xa0\xa0"colr" is an undefined item in type "StyleProps"'
        ),
    ),
    (
        18,
        "reportAssignmentType",
        (
            'Type "dict[str, dict[str, str]]" is not assignable to declared type "StyleProps"\n'
            '\xa0\xa0"_hovr" is an undefined item in type "StyleProps"'
        ),
    ),
    (
        20,
        "reportAssignmentType",
        (
            'Type "dict[str, Text]" is not assignable to declared type "StyleProps"\n'
            '\xa0\xa0Type "Text" is not assignable to type "_Value[_Color]"\n'
            '\xa0\xa0\xa0\xa0"Text" is not assignable to "str"\n'
            '\xa0\xa0\xa0\xa0"Text" is not assignable to "Color"\n'
            '\xa0\xa0\xa0\xa0"Text" is not assignable to "Var[str]"\n'
            '\xa0\xa0\xa0\xa0"Text" is not assignable to "Var[Color]"\n'
            '\xa0\xa0\xa0\xa0"Text" is not assignable to "Sequence[_Color]"\n'
            '\xa0\xa0\xa0\xa0"Text" is not assignable to "Breakpoints[Any, Any]"\n'
            '\xa0\xa0\xa0\xa0"Text" is not assignable to "Mapping[str, _Color | Mapping[str, '
            '_Color]]"'
        ),
    ),
    (
        22,
        "reportAssignmentType",
        (
            'Type "dict[str, dict[str, dict[str, dict[str, str]]]]" is not assignable to '
            'declared type "ComponentStyles"\n'
            '\xa0\xa0"variant" is an undefined item in type "ComponentStyles"'
        ),
    ),
    (
        25,
        "reportAssignmentType",
        (
            'Type "dict[str, dict[str, dict[str, dict[str, str]]]]" is not assignable to '
            'declared type "ComponentStyles"\n'
            '\xa0\xa0"heght" is an undefined item in type "StyleProps"'
        ),
    ),
    (
        29,
        "reportAssignmentType",
        (
            'Type "dict[str, dict[str, dict[str, dict[str, str]]]]" is not assignable to '
            'declared type "ComponentStyles"\n'
            '\xa0\xa0Type "Literal[\'invisible\']" is not assignable to type "_Value[_Visibility '
            '| _StrVar]"\n'
            '\xa0\xa0\xa0\xa0"Literal[\'invisible\']" is not assignable to "Var[str]"\n'
            '\xa0\xa0\xa0\xa0"Literal[\'invisible\']" is not assignable to "Sequence[_Visibility '
            '| _StrVar]"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0Type parameter "_T_co@Sequence" is covariant, but "str" is '
            'not a subtype of "_Visibility | _StrVar"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0Type "str" is not assignable to type "_Visibility | '
            '_StrVar"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to "Var[str]"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to type '
            "\"Literal['collapse']\"\n"
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to type '
            "\"Literal['hidden']\""
        ),
    ),
    (
        32,
        "reportAssignmentType",
        (
            'Type "dict[str, StyleProps]" is not assignable to declared type "CompoundStyle"\n'
            '\xa0\xa0"props" is required in "CompoundStyle"'
        ),
    ),
]
