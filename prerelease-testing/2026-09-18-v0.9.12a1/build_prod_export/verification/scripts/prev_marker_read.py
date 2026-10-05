"""Replay the 0.9.11.post1 marker-read lines against a non-UTF-8 marker."""
import json, sys, pathlib, reflex
assert "/envs/prev/" in reflex.__file__, reflex.__file__
print("reflex from:", reflex.__file__)
p = pathlib.Path(sys.argv[1])
try:
    with p.open("r") as file:       # compiler.py:1228 in 0.9.11.post1
        data = json.load(file)      # compiler.py:1229
    print("OK", data)
except Exception as e:
    print("RAISED", type(e).__name__, e)
