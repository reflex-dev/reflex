"""Isolated Var construction measurements, separate from CLI/export wall time."""

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import statistics
import time
from pathlib import Path
import reflex as rx

assert str(Path(os.environ["REFLEX_EXPECT_ENV"]) / "lib") in rx.__file__, rx.__file__


class VarSource(rx.State):
    """Dynamic source prevents constant folding of the expression workload."""

    seed: int = 7


parser = argparse.ArgumentParser()
parser.add_argument("--smoke", action="store_true")
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
assert args.smoke or os.environ.get("PERF_QUIET_CONFIRMED") == "1", (
    "Timing requires explicit quiet authorization."
)
samples = []
for repeat in range(1 if args.smoke else args.repeats):
    started = time.perf_counter_ns() if not args.smoke else 0
    expressions = [
        rx.cond(
            (VarSource.seed + offset) % 3 == 0,
            (VarSource.seed + offset) * (offset + 1),
            (VarSource.seed - offset) * (offset + 2),
        )
        for offset in range(2 if args.smoke else 2000)
    ]
    elapsed = time.perf_counter_ns() - started if not args.smoke else None
    assert len(expressions) == (2 if args.smoke else 2000)
    source = [str(value) for value in expressions]
    state_name, field = str(VarSource.seed).split(".", 1)
    node = shutil.which("node")
    assert node, (
        "Node is required to independently check generated arithmetic/conditional JS."
    )
    program = 'const data=JSON.parse(require("fs").readFileSync(0,"utf8")); const fn=new Function(data.name,"return ["+data.expressions.join(",")+"];"); process.stdout.write(JSON.stringify(fn({[data.field]:7})));'
    evaluated = subprocess.run(
        [node, "-e", program],
        input=json.dumps({"name": state_name, "field": field, "expressions": source}),
        capture_output=True,
        text=True,
        check=True,
    )
    actual = json.loads(evaluated.stdout)
    expected = [
        (7 + offset) * (offset + 1)
        if (7 + offset) % 3 == 0
        else (7 - offset) * (offset + 2)
        for offset in range(len(expressions))
    ]
    assert actual == expected, (actual[:3], actual[-3:])
    samples.append(
        {
            "repeat": repeat,
            "count": len(expressions),
            "nanoseconds": elapsed,
            "output_chars": sum(map(len, source)),
            "semantic_js_evaluation": "pass",
            "semantic_checksum": sum(actual),
        }
    )
result = {
    "reflex": importlib.metadata.version("reflex"),
    "smoke": args.smoke,
    "samples": samples,
}
if not args.smoke:
    result["median_ns"] = statistics.median(x["nanoseconds"] for x in samples)
print(json.dumps(result, indent=1))
