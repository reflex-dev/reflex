"""Record missing optional database dependency guidance in a clean wheel env."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
RESULTS = {
    "modules": {
        name: importlib.util.find_spec(name) is not None
        for name in ("sqlalchemy", "alembic", "sqlmodel", "pydantic")
    },
    "commands": [],
}
assert not any(RESULTS["modules"].values())
for command in ("init", "migrate", "makemigrations", "status"):
    process = subprocess.run(
        [
            "/Users/masenf/.local/bin/uv",
            "run",
            "--no-project",
            "--python",
            sys.executable,
            "reflex",
            "db",
            command,
        ],
        capture_output=True,
        text=True,
        env={name: value for name, value in os.environ.items() if name != "PYTHONPATH"},
        check=False,
    )
    output = process.stdout + process.stderr
    (OUT / f"no-db-{command}.log").write_text(output)
    assert process.returncode == 1, output
    assert "Database is not available" in output
    assert "reflex[db]" in output
    assert "Traceback" not in output
    RESULTS["commands"].append({
        "command": command,
        "returncode": process.returncode,
        "guidance": "reflex[db]",
        "traceback": False,
    })
RESULTS["status"] = "passed"
(OUT / "missing-db-results.json").write_text(json.dumps(RESULTS, indent=2))
