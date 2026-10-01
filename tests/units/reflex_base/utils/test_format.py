"""Unit tests for reflex_base.utils.format."""

import json
import subprocess
import sys

from reflex_base import constants
from reflex_base.utils import format

import reflex as rx


def test_format_queue_events_dispatches_through_add_events():
    """The formatted callback calls addEvents and carries its imports."""
    var = format.format_queue_events(rx.console_log("hello"))
    js = str(var)
    assert js.startswith("() => {addEvents([")
    assert "queueEvents" not in js

    var_data = var._get_all_var_data()
    assert var_data is not None
    imports = dict(var_data.imports)
    context_imports = imports[f"$/{constants.Dirs.CONTEXTS_PATH}"]
    assert any(imp.tag == "addEvents" for imp in context_imports)
    state_imports = imports[f"$/{constants.Dirs.STATE_PATH}"]
    assert any(imp.tag == "ReflexEvent" for imp in state_imports)


def test_format_queue_events_empty():
    """No events formats to a null callback."""
    assert str(format.format_queue_events(None)) == "(() => null)"


def test_format_queue_events_args_spec():
    """The args spec names the callback parameters."""
    var = format.format_queue_events(
        rx.console_log("hello"),
        args_spec=lambda result: [result],
    )
    assert str(var).startswith("(_result) => {addEvents([")


def test_json_dumps_compact_imports_orjson_on_first_use():
    """Importing format leaves orjson unloaded until a payload is encoded."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, sys; from reflex_base.utils import format; "
                "loaded = ['orjson' in sys.modules]; "
                "encoded = format.json_dumps_compact({'a': [1, 'b']}); "
                "loaded.append('orjson' in sys.modules); "
                "print(json.dumps([loaded, encoded]))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == [[False, True], '{"a":[1,"b"]}']
