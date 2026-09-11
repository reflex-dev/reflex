"""bundle_library() argument handling and registration persistence."""

import json
import sys

import reflex as rx
from reflex_base.components.dynamic import bundle_library

try:
    from reflex_base.registry import RegistrationContext
except Exception:  # noqa: BLE001
    RegistrationContext = None

res = {"reflex": rx.__file__}


def bundled():
    """Currently registered libraries."""
    ctx = RegistrationContext.ensure_context()
    return sorted(getattr(ctx, "bundled_libraries", []))


cases = {
    "library_string": "d3-format",
    "exact_subpath_string": "lucide-react/dist/esm/icons/apple.mjs",
    "component_instance": rx.text(),
    "component_class_not_instance": rx.text,
    "integer": 7,
    "none": None,
    "list": ["d3-format"],
}
res["cases"] = {}
for name, arg in cases.items():
    try:
        bundle_library(arg)
        res["cases"][name] = "accepted"
    except TypeError as e:
        res["cases"][name] = f"TypeError: {str(e)[:140]}"
    except Exception as e:  # noqa: BLE001
        res["cases"][name] = f"{type(e).__name__}: {str(e)[:140]}"

res["after_cases"] = bundled()

# duplicate explicit registration must not duplicate
before = bundled()
bundle_library("d3-format")
bundle_library("d3-format")
res["duplicate_registration_stable"] = bundled() == before
res["final"] = bundled()
print(json.dumps(res, indent=1))
