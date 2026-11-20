"""MVP: import JavaScript modules from Python and call their exports as events.

``from my_app.scripts.party import celebrate`` finds ``my_app/scripts/party.js``
(or ``.ts``). Each exported function becomes a callable returning an
``EventSpec`` that runs the function in the browser by name: the compiler
copies the module into ``.web`` and ``utils/scripts.js`` re-exports it, so no
code travels over the websocket and nothing is ``eval``'d.

``generate_stub`` reads the module's types with the TypeScript compiler (JSDoc
in ``.js``, annotations in ``.ts``) and writes a ``.pyi`` next to it, so
editors and pyright check the Python call sites.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import inspect
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

from reflex_base.event import EventSpec, server_side
from reflex_base.utils import format

_EXTENSIONS = (".js", ".ts")
_EXPORT_RE = re.compile(
    r"^export\s+(?:async\s+)?(?:function\s*\*?\s*|const\s+|let\s+)([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
_CALL_JS_SIGNATURE = None

# Script modules imported by the app, by module key.
_registry: dict[str, Path] = {}


def _module_key(fullname: str) -> str:
    return fullname.replace(".", "__")


class JsFunction:
    """An exported function of a JavaScript module, called as an event."""

    def __init__(self, module_key: str, name: str):
        """Create the function handle.

        Args:
            module_key: The key the module is registered under.
            name: The exported name.
        """
        self.module_key = module_key
        self.name = name

    def __call__(self, *args: Any, callback: Any = None) -> EventSpec:
        """Build the event that calls the function in the browser.

        Args:
            *args: The arguments, values or Vars.
            callback: An event handler that receives the return value.

        Returns:
            The event.
        """
        # The callback goes as data, the handler and the argument receiving the
        # result, so the browser builds the event without evaluating code.
        callback_data = None
        if callback is not None:
            handler = getattr(callback, "handler", callback)
            params = list(inspect.signature(handler.fn).parameters)[1:]
            callback_data = {
                "name": format.format_event_handler(handler),
                "arg": params[0] if params else None,
            }

        def _call_js(module: str, function: str, args: list, callback: dict | None): ...

        return server_side(
            "_call_js",
            inspect.signature(_call_js),
            module=self.module_key,
            function=self.name,
            args=list(args),
            callback=callback_data,
        )

    def __repr__(self) -> str:
        """Represent the handle.

        Returns:
            The representation.
        """
        return f"<js function {self.module_key}.{self.name}>"


class _JsLoader(importlib.abc.Loader):
    def __init__(self, path: Path):
        self.path = path

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> None:
        return None

    def exec_module(self, module: types.ModuleType) -> None:
        key = _module_key(module.__name__)
        _registry[key] = self.path
        source = self.path.read_text(encoding="utf-8")
        exports = _EXPORT_RE.findall(source)
        for name in exports:
            setattr(module, name, JsFunction(key, name))
        module.__all__ = exports


class _JsFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Any,
        target: types.ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if path is None:
            return None
        name = fullname.rpartition(".")[2]
        for entry in path:
            for ext in _EXTENSIONS:
                file = Path(entry) / f"{name}{ext}"
                if file.is_file():
                    return importlib.machinery.ModuleSpec(
                        fullname, _JsLoader(file), origin=str(file)
                    )
        return None


def install() -> None:
    """Let ``import`` find JavaScript modules (idempotent)."""
    if not any(isinstance(f, _JsFinder) for f in sys.meta_path):
        sys.meta_path.append(_JsFinder())


def compile_scripts(web_dir: Path) -> list[tuple[str, str]]:
    """Emit the registered modules and the ``utils/scripts.js`` index.

    Args:
        web_dir: The ``.web`` directory.

    Returns:
        (output path, code) pairs for the compiler to write.
    """
    results = []
    lines = []
    for key, path in sorted(_registry.items()):
        target = f"utils/script_modules/{key}{path.suffix}"
        results.append((str(web_dir / target), path.read_text(encoding="utf-8")))
        lines.append(f'export * as {key} from "$/{target}";')
        generate_stub(path)
    results.append((
        str(web_dir / "utils" / "scripts.js"),
        "\n".join(lines) + "\n" if lines else "export {};\n",
    ))
    return results


_TS_TO_PY = {
    "number": "float",
    "string": "str",
    "boolean": "bool",
    "any": "Any",
    "unknown": "Any",
    "object": "Mapping[str, Any]",
    "void": "None",
    "undefined": "None",
    "null": "None",
}


def _split_top_level(text: str, sep: str) -> list[str]:
    parts, depth, current = [], 0, []
    for char in text:
        if char in "([{<":
            depth += 1
        elif char in ")]}>":
            depth -= 1
        if char == sep and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if "".join(current).strip():
        parts.append("".join(current).strip())
    return parts


def _py_type(ts: str) -> str:
    ts = ts.strip()
    union = _split_top_level(ts, "|")
    if len(union) > 1:
        return " | ".join(dict.fromkeys(_py_type(t) for t in union))
    if ts.endswith("[]"):
        return f"Sequence[{_py_type(ts[:-2])}]"
    if match := re.fullmatch(r"(Array|Promise)<(.+)>", ts):
        inner = _py_type(match.group(2))
        return f"Sequence[{inner}]" if match.group(1) == "Array" else inner
    if ts.startswith(("{", "Record<")):
        return "Mapping[str, Any]"
    return _TS_TO_PY.get(ts, "Any")


_DECL_RE = re.compile(
    r"^export (?:declare )?function (\w+)\((.*)\): (.+);$", re.MULTILINE
)


def _stub_from_declarations(dts: str) -> str:
    lines = [
        "# Generated by Reflex from the JavaScript module next to this file.",
        "from collections.abc import Mapping, Sequence",
        "from typing import Any",
        "",
        "from reflex_base.event import EventSpec, EventType",
        "from reflex_base.vars import Var",
        "",
    ]
    for name, params, returns in _DECL_RE.findall(dts):
        py_params = []
        for param in _split_top_level(params, ","):
            pname, _, ptype = param.partition(":")
            optional = pname.endswith("?")
            pname = pname.rstrip("?").strip()
            py = _py_type(ptype or "any")
            annotation = "Any" if py == "Any" else f"{py} | Var[{py}]"
            py_params.append(f"{pname}: {annotation}" + (" = ..." if optional else ""))
        result = _py_type(returns)
        signature = ", ".join([*py_params, "/"]) if py_params else ""
        lines.extend([
            f"def {name}({signature}{', ' if signature else ''}*, "
            f"callback: EventType[{result}] | None = None) -> EventSpec: ...",
        ])
    return "\n".join(lines) + "\n"


def generate_stub(path: Path) -> Path | None:
    """Write ``<module>.pyi`` next to a JavaScript module from its types.

    Args:
        path: The ``.js`` or ``.ts`` module.

    Returns:
        The stub path, or None if the TypeScript compiler could not run.
    """
    with tempfile.TemporaryDirectory() as out:
        proc = subprocess.run(
            [
                "npx",
                "--yes",
                "-p",
                "typescript@5",
                "tsc",
                str(path),
                "--allowJs",
                "--declaration",
                "--emitDeclarationOnly",
                "--skipLibCheck",
                "--noResolve",
                "--outDir",
                out,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        dts_files = list(Path(out).rglob("*.d.ts"))
        if not dts_files:
            print(proc.stdout, proc.stderr, file=sys.stderr)  # noqa: T201
            return None
        stub = path.with_suffix(".pyi")
        stub.write_text(_stub_from_declarations(dts_files[0].read_text()))
        return stub
