"""Verify installed reflex* distributions against their RECORD sha256. Usage: python -I verify_record.py (run with the venv's python)."""
import base64, hashlib, importlib.metadata as md, sys
bad = []
for d in md.distributions():
    n = d.metadata["Name"].lower()
    if not n.startswith("reflex"):
        continue
    for f in d.files or []:
        if not f.hash or f.hash.mode != "sha256":
            continue
        p = f.locate()
        try:
            h = base64.urlsafe_b64encode(hashlib.sha256(open(p, "rb").read()).digest()).rstrip(b"=").decode()
        except FileNotFoundError:
            bad.append(f"{n} MISSING {f}"); continue
        if h != f.hash.value:
            bad.append(f"{n}=={d.version} MODIFIED {f}")
print(sys.prefix, "OK" if not bad else "\n".join(bad))
