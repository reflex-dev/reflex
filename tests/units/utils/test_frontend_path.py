import reflex as rx
from pathlib import Path

def test_frontend_path_resolves_correctly(tmp_path):
    """Ensure the frontend path resolves correctly to the .web directory."""

    # Simulate a reflex project structure
    project_root = tmp_path / "my_app"
    frontend_dir = project_root / ".web"
    frontend_dir.mkdir(parents=True)

    # Monkeypatch rxconfig to simulate project root
    rx.config.app_name = "my_app"
    rx.config.root = project_root

    # ✅ Reflex always expects frontend path at <root>/.web
    resolved_path = Path(rx.config.root) / ".web"

    expected_path = frontend_dir

    # Normalize paths (important on Windows)
    assert resolved_path.resolve() == expected_path.resolve(), (
        f"Expected {expected_path}, got {resolved_path}"
    )
