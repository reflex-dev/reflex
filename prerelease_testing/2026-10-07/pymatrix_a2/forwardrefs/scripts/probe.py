"""Import one real-file fixture and retain full exception diagnostics."""

import argparse
import importlib
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fixtures.origin import check_origin

parser = argparse.ArgumentParser()
parser.add_argument("case")
parser.add_argument("output", type=Path)
args = parser.parse_args()
metadata = check_origin()
result = {"case": args.case, "metadata": metadata, "imported": False, "accepted": False}
phase = "module_import"
try:
    module = importlib.import_module(f"fixtures.{args.case}")
    result["imported"] = True
    if hasattr(module, "verify"):
        result["control"] = module.verify()
    if hasattr(module, "build_page"):
        phase = "component_build"
        component = module.build_page()
        result["component"] = {
            "class": type(component).__name__,
            "render": repr(component.render()),
        }
    result["accepted"] = True
except Exception as error:
    result["exception_phase"] = phase
    result["exception_type"] = f"{type(error).__module__}.{type(error).__qualname__}"
    result["exception_message"] = str(error)
    result["exception_repr"] = repr(error)
    result["traceback"] = "".join(traceback.format_exception(error))
    result["cause"] = repr(error.__cause__)
    result["context"] = repr(error.__context__)
    result["suppress_context"] = error.__suppress_context__
expected_import = args.case.endswith("_valid")
result["fixture_expectation_pass"] = result["accepted"] == expected_import
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2))
if "traceback" in result:
    args.output.with_suffix(".traceback.txt").write_text(result["traceback"])
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["fixture_expectation_pass"] else 1)
