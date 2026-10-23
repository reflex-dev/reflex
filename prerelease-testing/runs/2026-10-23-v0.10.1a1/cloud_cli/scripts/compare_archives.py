"""Compare two deploy archives (backend.zip / frontend.zip) entry by entry.

Usage: python -I compare_archives.py <dir_new> <dir_prev>
Prints, per archive: entry counts, entries only on one side, per-entry compression method/size differences,
duplicate entry names, and the compression method used for pre-compressed sidecars (.gz/.br/.zst).
"""

from __future__ import annotations

import sys
import zipfile
from collections import Counter
from pathlib import Path

METHODS = {zipfile.ZIP_STORED: "STORED", zipfile.ZIP_DEFLATED: "DEFLATED"}


def entries(path: Path) -> tuple[dict, list[str]]:
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
    names = [i.filename for i in infos]
    table = {}
    for i in infos:
        table[i.filename] = (METHODS.get(i.compress_type, i.compress_type), i.file_size, i.compress_size, i.CRC)
    return table, names


def report(name: str, new_dir: Path, prev_dir: Path) -> None:
    new, new_names = entries(new_dir / name)
    prev, prev_names = entries(prev_dir / name)
    print(f"=== {name}: new {len(new_names)} entries ({(new_dir / name).stat().st_size} B), "
          f"prev {len(prev_names)} entries ({(prev_dir / name).stat().st_size} B)")
    for label, names in (("new", new_names), ("prev", prev_names)):
        dupes = [n for n, c in Counter(names).items() if c > 1]
        if dupes:
            print(f"  DUPLICATE entry names in {label}: {dupes}")
    only_new = sorted(set(new) - set(prev))
    only_prev = sorted(set(prev) - set(new))
    if only_new:
        print(f"  only in new ({len(only_new)}): {only_new[:40]}")
    if only_prev:
        print(f"  only in prev ({len(only_prev)}): {only_prev[:40]}")
    method_changes = []
    content_changes = []
    for n in sorted(set(new) & set(prev)):
        (m1, s1, c1, crc1), (m2, s2, c2, crc2) = new[n], prev[n]
        if m1 != m2:
            method_changes.append((n, m2, m1, s1, c2, c1))
        if crc1 != crc2 or s1 != s2:
            content_changes.append((n, s2, s1))
    print(f"  compression method changed on {len(method_changes)} entries (prev -> new):")
    for n, m2, m1, size, c2, c1 in method_changes[:60]:
        print(f"    {n}: {m2} -> {m1}  (size {size}, stored {c2} -> {c1})")
    print(f"  content differs on {len(content_changes)} entries (expected for built JS/CSS): "
          f"{[n for n, _, _ in content_changes][:12]}{' ...' if len(content_changes) > 12 else ''}")
    for label, table in (("new", new), ("prev", prev)):
        sidecars = {n: v[0] for n, v in table.items() if n.endswith((".gz", ".br", ".zst"))}
        by_method = Counter(sidecars.values())
        print(f"  {label}: {len(sidecars)} pre-compressed sidecars, methods {dict(by_method)}")
        odd = [n for n in sidecars if n.endswith((".gz.gz", ".gz.br", ".br.gz", ".br.br"))]
        if odd:
            print(f"    double-compressed sidecars in {label}: {odd}")


if __name__ == "__main__":
    new_dir, prev_dir = Path(sys.argv[1]), Path(sys.argv[2])
    for archive in ("backend.zip", "frontend.zip"):
        report(archive, new_dir, prev_dir)
    print("=== backend.zip full entry list (new):")
    table, names = entries(new_dir / "backend.zip")
    for n in names:
        print(f"  {table[n][0]:8} {table[n][1]:>8}  {n}")
