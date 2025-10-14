import reflex as rx
from pathlib import Path
from reflex.utils.prerequisites import get_web_dir


def test_frontend_path_resolves_correctly(tmp_path):
    """Ensure get_web_dir() resolves relative to the Reflex package root."""

    # Get what Reflex actually considers its root
    reflex_root = Path(rx.__file__).parent.parent  # reflex/reflex/... -> project root
    expected_path = reflex_root / ".web"

    # Ensure the returned path is correct
    resolved_path = get_web_dir()

    assert Path(resolved_path).resolve() == expected_path.resolve(), (
        f"Expected {expected_path}, got {resolved_path}"
    )
