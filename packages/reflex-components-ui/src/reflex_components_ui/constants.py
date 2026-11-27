"""Constants of the reflex-components-ui package."""

from pathlib import Path


def _js_src_dir(root_dir: Path) -> Path:
    """Locate the javascript the components are compiled against.

    A built distribution embeds it under ``js/src``. A source checkout has
    nothing there and reads the package's ``js/src`` in place, so an edit to
    the javascript is never shadowed by a stale copy.

    Args:
        root_dir: The root directory of the reflex_components_ui package.

    Returns:
        The directory holding the javascript files.
    """
    embedded = root_dir / "js" / "src"
    if embedded.is_dir():
        return embedded
    return root_dir.parents[1] / "js" / "src"


# The javascript package's source, copied into the web directory of a project.
JS_SRC = _js_src_dir(Path(__file__).parent)
