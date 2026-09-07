"""String operation code generation and JavaScript semantics."""

import json
import shutil
import subprocess

import pytest
from pytest_mock import MockerFixture
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.sequence import ArraySliceOperation


@pytest.mark.parametrize("step", [None, 1])
def test_string_slice_preserves_metadata(step: int | None) -> None:
    """Direct slices retain source and dynamic-bound imports and hooks."""
    source_data = VarData(imports={"source": [ImportVar(tag="text")]})
    start_data = VarData(hooks={"const start = useStart()": None})
    stop_data = VarData(imports={"bounds": [ImportVar(tag="stop")]})
    source = Var(_js_expr="text", _var_data=source_data).to(str)
    start = Var(_js_expr="start", _var_data=start_data).to(int)
    stop = Var(_js_expr="stop", _var_data=stop_data).to(int)

    result = source[start:stop:step]

    assert str(result) == "text.slice(start, stop)"
    assert result._var_type is str
    assert result._get_all_var_data() == VarData.merge(
        source_data, start_data, stop_data
    )
    assert str(source.length()) == "text.length"
    assert source.length()._var_type is int
    assert source.length()._get_all_var_data() == source_data


@pytest.mark.parametrize("step", [2, -1, -2, 0, Var(_js_expr="step").to(int)])
def test_string_slice_other_steps_keep_array_path(
    step: int | Var, mocker: MockerFixture
) -> None:
    """Non-unit and dynamic steps still delegate to the existing array slicer."""
    source = Var(_js_expr="text").to(str)
    array_slice = mocker.patch.object(
        ArraySliceOperation, "create", return_value=Var(_js_expr="sliced").to(list[str])
    )
    index = slice(1, 8, step)

    source[index]

    array_slice.assert_called_once()
    assert str(array_slice.call_args.args[0]) == 'text.split("")'
    assert array_slice.call_args.args[1] is index


def test_string_length_and_slices_preserve_utf16() -> None:
    """Generated operations preserve code-unit semantics in JavaScript."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute generated string operations")
    source = Var(_js_expr="text").to(str)
    start = Var(_js_expr="start").to(int)
    stop = Var(_js_expr="stop").to(int)
    expressions = [str(source[start:stop]), str(source[start:stop:1])]
    values = ["", "abc", "😎abc\ud800", "a\u0301bc", "\0\n\r"]
    script = f"""const strings = {json.dumps(values)};
const slices = {json.dumps(expressions)}.map(
  expression => new Function("text", "start", "stop", `return ${{expression}}`)
);
const length = new Function("text", {json.dumps(f"return {source.length()!s}")});
for (const text of strings) {{
  if (length(text) !== text.split("").length) throw Error("length mismatch");
  for (const start of [undefined, -100, -3, 0, 1, 2, 100]) {{
    for (const stop of [undefined, -100, -3, 0, 1, 2, 100]) {{
      const expected = text.split("").slice(start, stop).join("");
      for (const slice of slices) {{
        if (slice(text, start, stop) !== expected) throw Error("slice mismatch");
      }}
    }}
  }}
}}
"""
    subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
