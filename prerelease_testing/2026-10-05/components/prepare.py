"""Copy reusable test sources to a neutral temporary app and record provenance."""

import importlib
import importlib.metadata
import json
import math
import shutil
import struct
import sys
import wave
from pathlib import Path


def main() -> None:
    """Prepare the app and record installed distribution and module paths."""
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    target.mkdir(parents=True, exist_ok=True)
    (target / "component_dashboard").mkdir(exist_ok=True)
    (target / "component_dashboard" / "__init__.py").write_text("")
    shutil.copy2(
        source / "component_dashboard.py",
        target / "component_dashboard" / "component_dashboard.py",
    )
    shutil.copy2(source / "rxconfig.py", target / "rxconfig.py")
    assets = target / "assets"
    assets.mkdir(exist_ok=True)
    with wave.open(str(assets / "tone.wav"), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(
            b"".join(
                struct.pack("<h", int(5000 * math.sin(2 * math.pi * 440 * t / 8000)))
                for t in range(24000)
            )
        )
    distributions = sorted(
        (
            d
            for d in importlib.metadata.distributions()
            if d.metadata["Name"].startswith("reflex")
        ),
        key=lambda d: d.metadata["Name"],
    )
    records = []
    for dist in distributions:
        name = dist.metadata["Name"]
        module_name = name.replace("-", "_")
        if name == "reflex-hosting-cli":
            module_name = "reflex_cli"
        module = importlib.import_module(module_name)
        module_file = str(module.__file__)
        assert "/private/tmp/" in module_file, module_file
        assert "/site-packages/" in module_file, module_file
        assert dist.read_text("direct_url.json") is None, name
        records.append({
            "distribution": name,
            "version": dist.version,
            "module": module_name,
            "path": module_file,
        })
    (source / "provenance.json").write_text(
        json.dumps(
            {"executable": sys.executable, "cwd": str(Path.cwd()), "packages": records},
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
