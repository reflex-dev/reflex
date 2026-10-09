"""Print installed reflex / reflex-base / reflex-enterprise versions and reflex's import location (run with -I)."""
import importlib.metadata as m
import importlib.util as u

out = []
for d in ("reflex", "reflex-base", "reflex-enterprise"):
    try:
        out.append(f"{d}={m.version(d)}")
    except m.PackageNotFoundError:
        pass
out.append("reflex_from=" + u.find_spec("reflex").origin)
print(" ".join(out))
