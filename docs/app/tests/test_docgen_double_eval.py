"""Test that evaluating a markdown document twice doesn't break exec blocks.

This reproduces a CI failure where Granian's worker re-evaluates stateful pages
in the same process after the initial compilation.  The module-level cache in
_exec_code causes an earlier exec-only block to pre-populate the transformer's
env with names from *all* blocks on the second pass, so
_exec_and_get_last_callable finds no "new" keys and raises RuntimeError.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


MD_WITH_TWO_EXEC_BLOCKS = """\
```python exec
import reflex as rx
```

# Demo page

```python demo exec
class MyState(rx.State):
    count: int = 0

def my_demo():
    return rx.text(MyState.count)
```
"""


@pytest.fixture(autouse=True)
def _clear_exec_caches():
    """Reset the module-level caches so each test starts clean."""
    from reflex_docs.docgen_pipeline import _executed_blocks, _file_modules

    old_blocks = _executed_blocks.copy()
    old_modules = _file_modules.copy()
    _executed_blocks.clear()
    _file_modules.clear()
    yield
    _executed_blocks.clear()
    _executed_blocks.update(old_blocks)
    _file_modules.clear()
    _file_modules.update(old_modules)


def _render_once(text: str, virtual_filepath: str = "test_double_eval.md"):
    from reflex_docgen.markdown import parse_document

    from reflex_docs.docgen_pipeline import ReflexDocTransformer

    doc = parse_document(text)
    transformer = ReflexDocTransformer(
        virtual_filepath=virtual_filepath, filename=virtual_filepath
    )
    return transformer.transform(doc)


def test_double_eval_does_not_crash():
    """Evaluating the same markdown twice must not raise 'Exec block defined nothing new'."""
    # First pass — simulates the initial compilation.
    _render_once(MD_WITH_TWO_EXEC_BLOCKS)

    # Second pass — simulates the Granian worker re-evaluating stateful pages.
    # This is the call that fails before the fix.
    _render_once(MD_WITH_TWO_EXEC_BLOCKS)


def test_double_eval_browser_javascript():
    """The actual file that triggered the CI failure."""
    filepath = (
        Path(__file__).parent.parent.parent / "api-reference" / "browser_javascript.md"
    )
    if not filepath.exists():
        pytest.skip(f"{filepath} not found")

    from reflex_docs.docgen_pipeline import render_docgen_document

    vpath = "docs/api-reference/browser-javascript"
    render_docgen_document(vpath, filepath)
    render_docgen_document(vpath, filepath)


# ---------------------------------------------------------------------------
# Parametrized test: evaluate every markdown doc file twice
# ---------------------------------------------------------------------------

_app_root = Path(__file__).resolve().parent.parent  # …/app/
_docs_dir = _app_root.parent  # …/docs/ (parent of app/)

_all_docs: dict[str, str] = {}  # virtual_path → actual_path
for _md_file in sorted(_docs_dir.rglob("*.md")):
    if _md_file.is_relative_to(_app_root):
        continue
    _virtual = "docs/" + str(_md_file.relative_to(_docs_dir)).replace("\\", "/")
    _all_docs[_virtual] = str(_md_file)


@pytest.fixture(params=list(_all_docs.keys()))
def doc_file(request) -> tuple[str, str]:
    """Yield (virtual_path, actual_path) for each discovered markdown doc."""
    virtual_path = request.param
    return virtual_path, _all_docs[virtual_path]


def test_double_eval_all_docs(doc_file: tuple[str, str]):
    """Every markdown doc must survive two evaluations without error."""
    from reflex_docs.docgen_pipeline import render_docgen_document

    virtual_path, actual_path = doc_file
    render_docgen_document(virtual_path, actual_path)
    render_docgen_document(virtual_path, actual_path)
