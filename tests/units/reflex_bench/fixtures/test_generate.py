"""Tests for reflex_bench.fixtures.generate."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from reflex_bench.fixtures import generate
from reflex_bench.fixtures.generate import GenParams

PRAGMA = re.compile(r'^\w+ = "m-initial-[\w-]+"  # bench:hmr-target [\w-]+$')


def _tree(root: Path) -> dict[str, bytes]:
    """Read every file under a directory.

    Returns:
        File contents by POSIX path relative to ``root``.
    """
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _manifest(root: Path) -> list[dict[str, object]]:
    return json.loads((root / generate.MANIFEST).read_text(encoding="utf-8"))["targets"]


def test_equal_params_give_byte_identical_trees(tmp_path: Path):
    params = GenParams(pages=12, seed=7)
    first = generate.generate(tmp_path / "one", params)
    second = generate.generate(tmp_path / "two", GenParams(pages=12, seed=7))
    assert first == second == generate.describe(params)
    assert _tree(tmp_path / "one") == _tree(tmp_path / "two")


def test_describe():
    doc = generate.describe(GenParams(pages=10))
    assert doc["name"] == "gen"
    assert doc["params"] == {
        "pages": 10,
        "components_per_page": 20,
        "state_vars": 20,
        "substate_depth": 2,
        "computed_vars": 5,
        "seed": 42,
    }
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", doc["content_hash"])


@pytest.mark.parametrize(
    "other",
    [
        GenParams(pages=11),
        GenParams(pages=10, components_per_page=21),
        GenParams(pages=10, state_vars=19),
        GenParams(pages=10, substate_depth=3),
        GenParams(pages=10, computed_vars=4),
        GenParams(pages=10, seed=43),
    ],
)
def test_the_hash_changes_with_every_param(other: GenParams):
    base = generate.describe(GenParams(pages=10))["content_hash"]
    assert generate.describe(other)["content_hash"] != base


def test_the_hash_changes_with_the_generator_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    params = GenParams(pages=10)
    before = generate.describe(params)["content_hash"]
    edited = tmp_path / "generate.py"
    edited.write_bytes(generate._SOURCE.read_bytes() + b"\n# a change\n")
    monkeypatch.setattr(generate, "_SOURCE", edited)
    assert generate.describe(params)["content_hash"] != before


@pytest.mark.parametrize("pages", [1, 3, 12])
def test_pages_and_routes(tmp_path: Path, pages: int):
    generate.generate(tmp_path, GenParams(pages=pages, components_per_page=5))
    files = sorted(
        path.name for path in (tmp_path / "genapp" / "pages").glob("page_*.py")
    )
    assert files == sorted(f"page_{index}.py" for index in range(pages))
    module = ast.parse((tmp_path / "genapp" / "genapp.py").read_text(encoding="utf-8"))
    routes = {
        call.args[0].id: next(k.value.value for k in call.keywords if k.arg == "route")  # pyright: ignore[reportAttributeAccessIssue]
        for call in ast.walk(module)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "add_page"
    }
    assert routes == {
        "page_0": "/",
        **{f"page_{index}": f"/page-{index}" for index in range(1, pages)},
    }


def test_every_page_has_its_components(tmp_path: Path):
    generate.generate(tmp_path, GenParams(pages=4, components_per_page=9))
    for index in range(4):
        page = ast.parse(
            (tmp_path / "genapp" / "pages" / f"page_{index}.py").read_text(
                encoding="utf-8"
            )
        )
        (stack,) = [
            node
            for node in ast.walk(page)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "vstack"
        ]
        # A heading, then the components, then the page's leaf marker if it has one.
        assert len(stack.args) - 1 in {9, 10}


@pytest.mark.parametrize(("pages", "leaves"), [(1, 1), (7, 7), (10, 10), (1000, 10)])
def test_targets(tmp_path: Path, pages: int, leaves: int):
    params = GenParams(pages=pages, components_per_page=2, state_vars=3)
    generate.generate(tmp_path, params)
    targets = _manifest(tmp_path)
    assert targets[0] == {
        "name": "root",
        "path": "genapp/components/shared.py",
        "route": "/",
        "depth": 2,
    }
    names = [target["name"] for target in targets[1:]]
    assert len(set(names)) == len(names) == leaves
    for target in targets:
        text = (tmp_path / str(target["path"])).read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if "bench:hmr-target" in line]
        assert lines == [
            (
                f'{lines[0].split(" = ")[0]} = "m-initial-{target["name"]}"'
                f"  # bench:hmr-target {target['name']}"
            )
        ]
        assert f'id="bench-marker-{target["name"]}"' in text
    for target in targets[1:]:
        index = int(str(target["name"]).removeprefix("leaf-"))
        assert target["path"] == f"genapp/pages/page_{index}.py"
        assert target["route"] == ("/" if index == 0 else f"/page-{index}")
        assert target["depth"] == 1


def test_targets_are_picked_by_the_seed(tmp_path: Path):
    def leaves(seed: int, dest: str) -> list[object]:
        params = GenParams(pages=100, components_per_page=1, seed=seed)
        generate.generate(tmp_path / dest, params)
        return [target["name"] for target in _manifest(tmp_path / dest)[1:]]

    assert leaves(1, "one") == leaves(1, "again")
    assert leaves(1, "one-more") != leaves(2, "two")


def test_every_pragma_line_has_the_contract_form(tmp_path: Path):
    generate.generate(tmp_path, GenParams(pages=30))
    pragma_lines = [
        line
        for path in tmp_path.rglob("*.py")
        for line in path.read_text(encoding="utf-8").splitlines()
        if "bench:hmr-target" in line
    ]
    assert len(pragma_lines) == 11
    for line in pragma_lines:
        assert PRAGMA.fullmatch(line), line


def test_the_output_imports_only_reflex(tmp_path: Path):
    generate.generate(tmp_path, GenParams(pages=5, substate_depth=3))
    imported = set()
    for path in tmp_path.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0
                imported.add(node.module)
    assert "reflex" in imported
    # Besides reflex, only the app's own modules.
    assert {name for name in imported if name.split(".")[0] != "genapp"} == {"reflex"}


def test_rxconfig_has_only_the_radix_guard(tmp_path: Path):
    generate.generate(tmp_path, GenParams(pages=1))
    text = (tmp_path / "rxconfig.py").read_text(encoding="utf-8")
    assert 'app_name="genapp"' in text
    assert 'if hasattr(rx.plugins, "RadixThemesPlugin"):' in text
    assert "SitemapPlugin" not in text


def test_the_state_tree(tmp_path: Path):
    generate.generate(
        tmp_path, GenParams(pages=1, state_vars=7, substate_depth=3, computed_vars=4)
    )
    module = ast.parse((tmp_path / "genapp" / "state.py").read_text(encoding="utf-8"))
    classes = {
        node.name: node for node in module.body if isinstance(node, ast.ClassDef)
    }
    assert [ast.unparse(base) for base in classes["GenState"].bases] == ["rx.State"]
    assert [ast.unparse(classes[f"Sub{level}"].bases[0]) for level in (1, 2, 3)] == [
        "GenState",
        "Sub1",
        "Sub2",
    ]

    def members(name: str) -> tuple[list[str], list[str], list[str]]:
        body = classes[name].body
        fields = [node.target.id for node in body if isinstance(node, ast.AnnAssign)]  # pyright: ignore[reportAttributeAccessIssue]
        functions = [node for node in body if isinstance(node, ast.FunctionDef)]
        by_decorator = {
            decorator: [
                node.name
                for node in functions
                if [ast.unparse(d) for d in node.decorator_list] == [decorator]
            ]
            for decorator in ("rx.var", "rx.event")
        }
        return fields, by_decorator["rx.var"], by_decorator["rx.event"]

    fields, computed, handlers = members("GenState")
    assert fields == [f"v{index}" for index in range(7)]
    assert computed == [f"c{index}" for index in range(4)]
    assert len(handlers) == 1
    for level in (1, 2, 3):
        fields, computed, handlers = members(f"Sub{level}")
        assert fields
        assert computed == []
        assert len(handlers) == 1


@pytest.mark.parametrize(
    "params",
    [
        GenParams(
            pages=3,
            components_per_page=1,
            state_vars=1,
            substate_depth=0,
            computed_vars=0,
        ),
        GenParams(
            pages=2,
            components_per_page=40,
            state_vars=40,
            substate_depth=12,
            computed_vars=9,
        ),
    ],
)
def test_every_generated_module_is_valid_python(tmp_path: Path, params: GenParams):
    generate.generate(tmp_path, params)
    for path in tmp_path.rglob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


@pytest.mark.parametrize(
    "fields",
    [
        {"pages": 0},
        {"pages": 1, "components_per_page": 0},
        {"pages": 1, "state_vars": 0},
        {"pages": 1, "substate_depth": -1},
        {"pages": 1, "computed_vars": -1},
    ],
)
def test_params_that_make_no_app_are_rejected(fields: dict[str, int]):
    with pytest.raises(ValueError, match="GenParams"):
        GenParams(**fields)


def test_generate_refuses_a_directory_with_files(tmp_path: Path):
    (tmp_path / "stray.py").write_text("", encoding="utf-8")
    with pytest.raises(FileExistsError, match="not empty"):
        generate.generate(tmp_path, GenParams(pages=1))


def test_main_writes_a_tree(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    dest = tmp_path / "app"
    assert generate.main(["--pages", "3", "--components-per-page", "4", str(dest)]) == 0
    assert len(list((dest / "genapp" / "pages").glob("page_*.py"))) == 3
    expected = generate.describe(GenParams(pages=3, components_per_page=4))
    assert expected["content_hash"] in capsys.readouterr().out
