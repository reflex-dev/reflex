"""Compare login denial source in published enterprise a1 and installed a2."""

import ast
import hashlib
import importlib.metadata
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import reflex_enterprise

ROOT = Path(__file__).resolve().parent


def login_guard(source: str) -> dict:
    """Extract the login guard with its original one-based source position.

    Args:
        source: Published app module source.

    Returns:
        Guard source, positions, and whether denial calls exit without a code.
    """
    tree = ast.parse(source)
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_check_login"
    )
    calls = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "exit"
    ]
    return {
        "first_line": method.lineno,
        "last_line": method.end_lineno,
        "source": "\n".join(source.splitlines()[method.lineno - 1 : method.end_lineno]),
        "exit_without_status": any(not node.args and not node.keywords for node in calls),
    }


def main() -> None:
    """Read the official a1 wheel without installing it and compare the guard."""
    inventory = ROOT.parent.parent / "inventory" / "superseded-enterprise-alpha.json"
    release = json.loads(inventory.read_text())
    wheel = next(item for item in release["files"] if item["filename"].endswith(".whl"))
    with urllib.request.urlopen(wheel["url"], timeout=45) as response:
        payload = response.read()
    actual_digest = hashlib.sha256(payload).hexdigest()
    assert actual_digest == wheel["sha256"]
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        old_source = archive.read("reflex_enterprise/app.py").decode()
    installed_path = Path(reflex_enterprise.__file__).parent / "app.py"
    current_source = installed_path.read_text()
    result = {
        "a1": {
            "version": release["version"],
            "wheel_url": wheel["url"],
            "wheel_sha256": actual_digest,
            "guard": login_guard(old_source),
        },
        "a2": {
            "version": importlib.metadata.version("reflex-enterprise"),
            "installed_path": str(installed_path),
            "module_sha256": hashlib.sha256(current_source.encode()).hexdigest(),
            "guard": login_guard(current_source),
        },
        "a1_executed": False,
        "classification": "Denial exit without a status already existed in published a1 source.",
    }
    (ROOT / "logs" / "guard-source-comparison.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(result["classification"])


if __name__ == "__main__":
    main()
