"""Strict JSON-lines validator for reflex --json / REFLEX_LOG_JSON output.

Usage: python check_jsonlines.py <file> [--allow-empty]

Reads a captured output file (stdout or stderr of a reflex command run in JSON
mode) and reports every line that is not a valid single JSON object. Exits 0 if
all non-empty lines parse, 1 otherwise. Prints a summary either way:
  TOTAL / JSON-OK / NON-JSON, then each offending line (repr, truncated).

ANSI escape sequences are NOT stripped: in JSON mode there should be none.
A line consisting only of whitespace is counted separately (benign) unless it
contains other characters.
"""

import json
import sys


def main() -> int:
    path = sys.argv[1]
    with open(path, "rb") as f:
        raw = f.read()
    lines = raw.decode("utf-8", errors="replace").split("\n")
    # Drop the trailing empty element from a final newline.
    if lines and lines[-1] == "":
        lines.pop()
    total = len(lines)
    ok = 0
    blank = 0
    bad: list[tuple[int, str]] = []
    keys_seen: dict[str, int] = {}
    for i, line in enumerate(lines, 1):
        if line.strip() == "":
            blank += 1
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            bad.append((i, line))
            continue
        if not isinstance(obj, dict):
            bad.append((i, line))
            continue
        ok += 1
        for k in obj:
            keys_seen[k] = keys_seen.get(k, 0) + 1
    print(f"FILE {path}: total={total} json_ok={ok} blank={blank} non_json={len(bad)}")
    if keys_seen:
        print(f"  keys: {sorted(keys_seen)}")
    for i, line in bad:
        print(f"  BAD line {i}: {line[:300]!r}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
