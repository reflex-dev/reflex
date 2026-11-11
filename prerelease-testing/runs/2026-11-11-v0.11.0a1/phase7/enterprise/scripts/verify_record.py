"""Check installed files of reflex* distributions against their wheel RECORD hashes.

Usage: verify_record.py <site-packages dir> [dist name prefix, default "reflex"]
Prints every file whose sha256 differs from RECORD (tampered / patched in place).
"""

import base64
import csv
import hashlib
import sys
from pathlib import Path

sp = Path(sys.argv[1])
prefix = sys.argv[2] if len(sys.argv) > 2 else "reflex"
bad = checked = 0
for rec in sorted(sp.glob(f"{prefix}*.dist-info/RECORD")):
    for row in csv.reader(rec.open()):
        if len(row) < 2 or not row[1].startswith("sha256="):
            continue
        f = sp / row[0]
        if not f.exists():
            print("MISSING", rec.parent.name, row[0])
            bad += 1
            continue
        h = base64.urlsafe_b64encode(hashlib.sha256(f.read_bytes()).digest()).rstrip(b"=").decode()
        checked += 1
        if "sha256=" + h != row[1]:
            print("MODIFIED", rec.parent.name, row[0])
            bad += 1
print(f"{sp}: checked {checked} files, {bad} mismatches")
