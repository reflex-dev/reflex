"""Summarize saved repetitions without rerunning any benchmark."""

import argparse
import gzip
import json
import re
import statistics
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
args = parser.parse_args()
root = args.root


def read_log_json(path):
    """Read the JSON result after uv's non-JSON preamble.

    Args:
        path: Saved probe output.

    Returns:
        The probe's result object.
    """
    text = path.read_text()
    return json.JSONDecoder().raw_decode(text[text.index("{") :])[0]


def distribution(values):
    """Retain repetitions alongside their median and range.

    Args:
        values: Same-unit sample values.

    Returns:
        A compact descriptive distribution.
    """
    return {
        "samples": values,
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


result = {
    "isolated": {},
    "compile": {},
    "browser": {},
    "comparison": [],
    "warnings": [],
    "cancellations": [],
    "errors": [],
}
for train in ("stable", "alpha2"):
    result["isolated"][train] = {}
    for mode in ("dev", "prod"):
        samples = [
            read_log_json(root / f"logs/{train}-{mode}-direct-{repeat}.log")
            for repeat in range(3)
        ]
        assert all(row["samples"][0]["checksum"] == 200000 for row in samples)
        for operation in ("read", "write"):
            result["isolated"][train][f"{mode}_{operation}_ns_per_op"] = distribution(
                [row[f"median_{operation}_ns_per_op"] for row in samples]
            )
    rows = [
        read_log_json(root / f"logs/{train}-vars-{repeat}.log") for repeat in range(3)
    ]
    assert all(row["samples"][0]["semantic_js_evaluation"] == "pass" for row in rows)
    result["isolated"][train]["var_construction_ms"] = distribution(
        [row["median_ns"] / 1e6 for row in rows]
    )

commands = json.loads((root / "runs/commands.json").read_text())
for train in ("stable", "alpha2"):
    result["compile"][train] = {}
    for command_type in ("compile", "python-compile"):
        rows = [
            next(
                row
                for row in commands
                if row["label"] == f"{train}-{command_type}-{repeat}"
            )
            for repeat in range(3)
        ]
        assert all(row["returncode"] == 0 for row in rows)
        result["compile"][train][f"{command_type}_process_seconds"] = distribution(
            [row["wall_ns"] / 1e9 for row in rows]
        )
        result["compile"][train][f"{command_type}_pages_seconds"] = distribution(
            [float(row["compile_pages_seconds"][0]) for row in rows]
        )
        if command_type == "python-compile":
            result["compile"][train]["full_python_internal_seconds"] = distribution(
                [float(row["full_python_compile_seconds"][0]) for row in rows]
            )
        install = []
        for repeat in range(3):
            text = (root / f"logs/{train}-{command_type}-{repeat}.log").read_text()
            install.append(
                {
                    "repeat": repeat,
                    "reported_install_seconds": re.findall(
                        r"Install Frontend Packages: ([0-9.]+)s", text
                    ),
                    "bun_install_invoked": bool(re.search(r"bun install v", text)),
                    "install_lines": [
                        line
                        for line in text.splitlines()
                        if any(
                            marker in line.lower()
                            for marker in (
                                "bun install",
                                "checked ",
                                "install frontend packages",
                                "skipping frontend",
                            )
                        )
                    ],
                }
            )
        result["compile"][train][f"{command_type}_install_evidence"] = install

for shared in (0, 1):
    for train in ("stable", "alpha2"):
        case = f"{train}-shared{shared}"
        runs = []
        for repeat in range(3):
            with gzip.open(
                root / f"runs/{case}-browser-{repeat}.json.gz", "rt"
            ) as handle:
                row = json.load(handle)
            assert not row["errors"], (case, repeat, row["errors"])
            assert all(check["pass"] for check in row["checks"])
            assert len(row["runs"][0]["samples"]) == 50
            for key in ("warnings", "cancellations", "errors"):
                result[key].extend(row[key])
            runs.append(row)
        metrics = {}
        for metric in (
            "handler_cpu_ns",
            "handler_wall_ns",
            "ws_roundtrip_ns",
            "click_to_dom_ms",
        ):
            scale = 1e6 if metric.endswith("_ns") else 1
            name = (
                metric.removesuffix("_ns") + "_ms" if metric.endswith("_ns") else metric
            )
            metrics[name] = distribution(
                [row["runs"][0]["medians"][metric] / scale for row in runs]
            )
        result["browser"][case] = {
            "repeat_medians": metrics,
            "measured_clicks": 150,
            "warmup_clicks": 15,
            "preflight_checks_passed": 6,
            "load_1m_before_after": [
                [row["load_average_before"][0], row["load_average_after"][0]]
                for row in runs
            ],
        }

for category, metrics in [
    ("isolated", list(result["isolated"]["stable"])),
    (
        "compile",
        [
            key
            for key, value in result["compile"]["stable"].items()
            if isinstance(value, dict)
        ],
    ),
]:
    for metric in metrics:
        stable = result[category]["stable"][metric]["median"]
        alpha2 = result[category]["alpha2"][metric]["median"]
        result["comparison"].append(
            {
                "category": category,
                "metric": metric,
                "stable": stable,
                "alpha2": alpha2,
                "stable_over_alpha2": stable / alpha2 if alpha2 else None,
                "alpha2_change_percent": (alpha2 / stable - 1) * 100
                if stable
                else None,
            }
        )
for shared in (0, 1):
    for metric in result["browser"][f"stable-shared{shared}"]["repeat_medians"]:
        stable = result["browser"][f"stable-shared{shared}"]["repeat_medians"][metric][
            "median"
        ]
        alpha2 = result["browser"][f"alpha2-shared{shared}"]["repeat_medians"][metric][
            "median"
        ]
        result["comparison"].append(
            {
                "category": f"browser-shared{shared}",
                "metric": metric,
                "stable": stable,
                "alpha2": alpha2,
                "stable_over_alpha2": stable / alpha2,
                "alpha2_change_percent": (alpha2 / stable - 1) * 100,
            }
        )
result["slowdowns_over_20_percent"] = [
    row
    for row in result["comparison"]
    if row["alpha2_change_percent"] is not None and row["alpha2_change_percent"] > 20
]
(root / "comparison.json").write_text(json.dumps(result, indent=2))
print(
    json.dumps(
        {
            "comparison": result["comparison"],
            "slowdowns_over_20_percent": result["slowdowns_over_20_percent"],
            "diagnostic_counts": {
                key: len(result[key]) for key in ("warnings", "cancellations", "errors")
            },
        },
        indent=2,
    )
)
