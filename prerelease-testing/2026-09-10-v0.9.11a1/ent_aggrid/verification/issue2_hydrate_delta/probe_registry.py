"""Print bundled_libraries as seen by (a) a full compile and (b) the backend-only path."""

import json
import os
import sys

mode = sys.argv[1]  # "compile" | "backend"
if mode == "backend":
    os.environ["__REFLEX_SKIP_COMPILE"] = "true"
os.environ["CI"] = "1"
os.environ["REFLEX_TELEMETRY_ENABLED"] = "false"

import reflex  # noqa: E402

print("reflex from", reflex.__file__, file=sys.stderr)

from reflex.utils import prerequisites  # noqa: E402
from reflex_base.registry import RegistrationContext  # noqa: E402

app_module = prerequisites.get_and_validate_app(reload=False)
app = app_module.app
from reflex.compiler.compiler import compile_app  # noqa: E402

ran = compile_app(app, dry_run=(mode == "compile"), use_rich=False)
print(
    json.dumps(
        {
            "mode": mode,
            "real_compile_ran": ran,
            "bundled_libraries": list(
                RegistrationContext.ensure_context().bundled_libraries
            ),
        },
        indent=2,
    )
)
