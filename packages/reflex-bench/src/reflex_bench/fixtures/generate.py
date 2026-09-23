"""A synthetic Reflex app of any size, for the scaling benchmarks.

``generate(dest, GenParams(pages=100))`` writes an app named ``genapp``::

    rxconfig.py                   the playground's RadixThemesPlugin guard
    genapp/genapp.py              rx.App(); page 0 at /, page i at /page-<i>
    genapp/state.py               GenState: state_vars fields, computed_vars
                                  computed vars and one handler, then a chain
                                  of substate_depth substates, each with its
                                  own vars and handler
    genapp/components/shared.py   the layout every page imports: the
                                  bench-hydrated marker and the root target
    genapp/pages/page_<i>.py      components_per_page components over the
                                  state's vars and handlers
    bench-manifest.json           the hot reload targets

The output is text: this module never imports reflex, and the app imports only
``reflex`` and uses only APIs that reflex 0.8.23 has. Equal parameters give
byte-identical trees. The content hash covers this module's source and the
parameters, so a change of the generator changes every generated hash.

Hot reload targets follow the playground's contract: a module-level constant on
a line of its own, ``NAME = "m-initial-<name>"  # bench:hmr-target <name>``,
rendered in the element ``#bench-marker-<name>``. ``root`` is in the shared
layout; ``leaf-<i>`` targets are in 1 to 10 pages, picked uniformly with
``random.Random(seed)``. The manifest lists each target's name, file, the route
of a page showing it and its import depth from the app module (1 for a page, 2
for the layout), so edit targets are picked without parsing code::

    {"targets": [{"name": "root", "path": "genapp/components/shared.py",
                  "route": "/", "depth": 2},
                 {"name": "leaf-3", "path": "genapp/pages/page_3.py",
                  "route": "/page-3", "depth": 1}, ...]}

``uv run python -m reflex_bench.fixtures.generate --pages 10 DEST`` writes one.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from reflex_bench.schema import FixtureDoc
from reflex_bench.store import canonical

APP = "genapp"
MANIFEST = "bench-manifest.json"
MAX_LEAF_TARGETS = 10
# The generator's own source, part of every content hash.
_SOURCE = Path(__file__)
# The root state's field types, in turn.
_TYPES = ("int", "str", "float", "bool", "list[str]")

_RXCONFIG = '''\
"""Reflex configuration of the generated benchmark app."""

import reflex as rx

plugins: list[rx.plugins.Plugin] = []
# Reflex 0.9 moved Radix Themes into a plugin; older releases always load it.
if hasattr(rx.plugins, "RadixThemesPlugin"):
    plugins.append(rx.plugins.RadixThemesPlugin())

config = rx.Config(app_name="genapp", plugins=plugins)
'''

_SHARED = '''\
"""The layout every page of the generated app shares."""

import reflex as rx

from genapp.state import GenState

ROOT_MARKER = "m-initial-root"  # bench:hmr-target root


def item(value: rx.Var[str]) -> rx.Component:
    """Render one entry of a list var.

    Args:
        value: The entry.

    Returns:
        The entry as text.
    """
    return rx.text(value)


def layout(content: rx.Component) -> rx.Component:
    """Wrap the content of a page in the shared layout.

    Args:
        content: The content of the page.

    Returns:
        The content, the hydration marker and the root hot reload marker.
    """
    return rx.vstack(
        content,
        rx.el.footer(
            rx.cond(GenState.is_hydrated, rx.el.span(id="bench-hydrated")),
            rx.el.span(ROOT_MARKER, id="bench-marker-root"),
        ),
    )
'''


@dataclass(frozen=True)
class GenParams:
    """The size and shape of a generated app.

    Attributes:
        pages: Pages, each on its own route.
        components_per_page: Components on each page.
        state_vars: Fields of the root state.
        substate_depth: Length of the chain of substates below the root state.
        computed_vars: Computed vars of the root state.
        seed: Seeds the choice of the pages holding leaf hot reload targets.
    """

    pages: int
    components_per_page: int = 20
    state_vars: int = 20
    substate_depth: int = 2
    computed_vars: int = 5
    seed: int = 42

    def __post_init__(self) -> None:
        """Reject sizes that make no app.

        Raises:
            ValueError: When a count is below its minimum.
        """
        if (
            min(self.pages, self.components_per_page, self.state_vars) < 1
            or min(self.substate_depth, self.computed_vars) < 0
        ):
            msg = (
                "GenParams needs pages, components_per_page and state_vars >= 1 and"
                f" substate_depth and computed_vars >= 0, got {self}"
            )
            raise ValueError(msg)


def describe(params: GenParams) -> FixtureDoc:
    """Describe the app :func:`generate` writes for some parameters.

    Args:
        params: The parameters.

    Returns:
        ``{"name": "gen", "content_hash": ..., "params": ...}``; the hash is the
        SHA-256 of this module's source and the canonical parameters.
    """
    fields = dataclasses.asdict(params)
    digest = hashlib.sha256(_SOURCE.read_bytes() + canonical(fields).encode())
    return {
        "name": "gen",
        "content_hash": f"sha256:{digest.hexdigest()}",
        "params": fields,
    }


def _route(page: int) -> str:
    """Give the route of a page.

    Args:
        page: The page index.

    Returns:
        ``/`` for page 0, else ``/page-<page>``.
    """
    return "/" if page == 0 else f"/page-{page}"


def _leaf_pages(params: GenParams) -> list[int]:
    """Pick the pages holding a leaf hot reload target.

    Args:
        params: The parameters.

    Returns:
        Up to :data:`MAX_LEAF_TARGETS` distinct page indices in the order drawn.
    """
    count = min(params.pages, MAX_LEAF_TARGETS)
    return random.Random(params.seed).sample(range(params.pages), count)


def _field(index: int) -> str:
    """Declare a field of the root state.

    Args:
        index: The field index; it decides the type.

    Returns:
        E.g. ``v3: bool = False``.
    """
    kind = _TYPES[index % len(_TYPES)]
    default = {
        "int": str(index),
        "str": f'"text {index}"',
        "float": f"{index}.5",
        "bool": str(index % 2 == 0),
        "list[str]": f'["a{index}", "b{index}", "c{index}"]',
    }[kind]
    return f"v{index}: {kind} = {default}"


def _state_module(params: GenParams) -> str:
    """Write the state tree: the root state, then the chain of substates.

    Args:
        params: The parameters.

    Returns:
        The module source.
    """
    lines = [
        '"""The state tree of the generated app."""',
        "",
        "import reflex as rx",
        "",
        "",
        "class GenState(rx.State):",
        '    """The root state: typed fields, computed vars and a handler."""',
        "",
        *(f"    {_field(index)}" for index in range(params.state_vars)),
    ]
    for index in range(params.computed_vars):
        lines += [
            "",
            "    @rx.var",
            f"    def c{index}(self) -> str:",
            f'        """Computed var {index}."""',
            f'        return f"c{index}: {{self.v{index % params.state_vars}}}"',
        ]
    lines += [
        "",
        "    @rx.event",
        "    def increment(self):",
        '        """Increase v0 by one."""',
        "        self.v0 += 1",
    ]
    for level in range(1, params.substate_depth + 1):
        parent = "GenState" if level == 1 else f"Sub{level - 1}"
        lines += [
            "",
            "",
            f"class Sub{level}({parent}):",
            f'    """Substate {level} of the chain below the root state."""',
            "",
            f"    s{level}_count: int = 0",
            f'    s{level}_label: str = "substate {level}"',
            f'    s{level}_items: list[str] = ["x{level}", "y{level}"]',
            "",
            "    @rx.event",
            f"    def bump_{level}(self):",
            f'        """Increase s{level}_count by one."""',
            f"        self.s{level}_count += 1",
        ]
    return "\n".join(lines) + "\n"


def _component(page: int, slot: int, params: GenParams, used: set[str]) -> str:
    """Write one component of a page.

    Of every four components, one links to a following page, one shows a
    substate and one a computed var (when there are any); the others show a
    root field, in a component that fits its type. Consecutive pages start at
    consecutive fields, levels and computed vars, so the pages use them all.

    Args:
        page: The page index.
        slot: The component's position on the page.
        params: The parameters.
        used: Receives the names the component needs imported.

    Returns:
        The component expression.
    """
    turn, group = slot % 4, slot // 4
    if turn == 3:
        target = (page + group + 1) % params.pages
        return f'rx.link("Page {target}", href="{_route(target)}")'
    if turn == 2 and params.computed_vars:
        used.add("GenState")
        return f"rx.text(GenState.c{(page + group) % params.computed_vars})"
    if turn == 1 and params.substate_depth:
        level = 1 + (page + group) % params.substate_depth
        state = f"Sub{level}"
        used.add(state)
        return (
            f"rx.hstack(rx.text({state}.s{level}_label), rx.text({state}.s{level}_count),"
            f' rx.button("Bump", on_click={state}.bump_{level}))'
        )
    index = (page + slot) % params.state_vars
    var = f"GenState.v{index}"
    used.add("GenState")
    kind = _TYPES[index % len(_TYPES)]
    if kind == "list[str]":
        used.add("item")
        return f"rx.foreach({var}, item)"
    return {
        "int": f'rx.hstack(rx.text({var}), rx.button("+", on_click=GenState.increment))',
        "str": f'rx.heading({var}, size="3")',
        "float": f"rx.text({var})",
        "bool": f'rx.cond({var}, rx.text("on"), rx.text("off"))',
    }[kind]


def _page_module(page: int, params: GenParams, leaf: bool) -> str:
    """Write one page.

    Args:
        page: The page index.
        params: The parameters.
        leaf: Whether the page holds a leaf hot reload target.

    Returns:
        The module source.
    """
    used: set[str] = set()
    children = [
        f'rx.heading("Page {page}")',
        *(
            _component(page, slot, params, used)
            for slot in range(params.components_per_page)
        ),
    ]
    marker = []
    if leaf:
        name = f"leaf-{page}"
        marker = ["", f'LEAF_MARKER = "m-initial-{name}"  # bench:hmr-target {name}']
        children.append(f'rx.el.span(LEAF_MARKER, id="bench-marker-{name}")')
    shared = ", ".join(sorted({"layout", *(used & {"item"})}))
    states = sorted(used - {"item"})
    return "\n".join([
        f'"""Page {page} of the generated app."""',
        "",
        "import reflex as rx",
        "",
        f"from genapp.components.shared import {shared}",
        *([f"from genapp.state import {', '.join(states)}"] if states else []),
        *marker,
        "",
        "",
        f"def page_{page}() -> rx.Component:",
        f'    """Render page {page}.',
        "",
        "    Returns:",
        "        The page in the shared layout.",
        '    """',
        "    return layout(",
        "        rx.vstack(",
        *(f"            {child}," for child in children),
        "        )",
        "    )",
        "",
    ])


def _app_module(pages: int) -> str:
    """Write the app module, which adds every page.

    Args:
        pages: The number of pages.

    Returns:
        The module source.
    """
    return "\n".join([
        f'"""The generated benchmark app: {pages} pages sharing one layout and state."""',
        "",
        "import reflex as rx",
        "",
        *(f"from genapp.pages.page_{page} import page_{page}" for page in range(pages)),
        "",
        "app = rx.App()",
        *(
            f'app.add_page(page_{page}, route="{_route(page)}")'
            for page in range(pages)
        ),
        "",
    ])


def _manifest(leaf_pages: Sequence[int]) -> str:
    """List the hot reload targets.

    Args:
        leaf_pages: The pages holding a leaf target, in the order drawn.

    Returns:
        The manifest JSON.
    """
    targets = [
        {
            "name": "root",
            "path": f"{APP}/components/shared.py",
            "route": "/",
            "depth": 2,
        },
        *(
            {
                "name": f"leaf-{page}",
                "path": f"{APP}/pages/page_{page}.py",
                "route": _route(page),
                "depth": 1,
            }
            for page in leaf_pages
        ),
    ]
    return json.dumps({"targets": targets}, indent=2) + "\n"


def generate(dest: Path, params: GenParams) -> FixtureDoc:
    """Write a generated app.

    Args:
        dest: The app directory; created when missing, and it must be empty.
        params: The parameters.

    Returns:
        The app's description, as :func:`describe` gives it.

    Raises:
        FileExistsError: When ``dest`` holds files.
    """
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        msg = f"{dest} is not empty"
        raise FileExistsError(msg)
    leaf_pages = _leaf_pages(params)
    leaves = set(leaf_pages)
    files = {
        "rxconfig.py": _RXCONFIG,
        f"{APP}/__init__.py": '"""The generated benchmark app."""\n',
        f"{APP}/{APP}.py": _app_module(params.pages),
        f"{APP}/state.py": _state_module(params),
        f"{APP}/components/__init__.py": '"""Components shared by the pages."""\n',
        f"{APP}/components/shared.py": _SHARED,
        f"{APP}/pages/__init__.py": '"""The pages, one module each."""\n',
        **{
            f"{APP}/pages/page_{page}.py": _page_module(page, params, page in leaves)
            for page in range(params.pages)
        },
        MANIFEST: _manifest(leaf_pages),
    }
    for name, text in files.items():
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
    return describe(params)


def main(argv: Sequence[str] | None = None) -> int:
    """Write a generated app from the command line.

    Args:
        argv: The arguments; defaults to ``sys.argv[1:]``.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(
        prog="python -m reflex_bench.fixtures.generate",
        description="Write a synthetic Reflex app for the scaling benchmarks.",
    )
    parser.add_argument("dest", type=Path, help="An empty or missing directory.")
    fields = dataclasses.fields(GenParams)
    for field in fields:
        flag = "--" + field.name.replace("_", "-")
        if field.default is dataclasses.MISSING:
            parser.add_argument(flag, type=int, required=True)
        else:
            parser.add_argument(flag, type=int, default=field.default)
    args = parser.parse_args(argv)
    try:
        params = GenParams(**{
            field.name: getattr(args, field.name) for field in fields
        })
    except ValueError as exc:
        parser.error(str(exc))
    doc = generate(args.dest, params)
    print(f"wrote {args.dest} ({doc['content_hash']})")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
