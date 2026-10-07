"""Record the exact published environment and enforce its import origin."""

import importlib.metadata as metadata
import json
import os
import platform
import sys

import reflex

assert f"/envs/{os.environ['REFLEX_TEST_ENV']}/" in reflex.__file__, reflex.__file__
print(
    json.dumps(
        {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "reflex_file": reflex.__file__,
            "requires_python": metadata.metadata("reflex")["Requires-Python"],
            "packages": {
                d.metadata["Name"]: d.version for d in metadata.distributions()
            },
        },
        indent=2,
    )
)
