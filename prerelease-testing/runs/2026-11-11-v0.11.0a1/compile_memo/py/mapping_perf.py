"""#7057: figure_out_type / LiteralVar.create on a large dict. Usage: <venv python> mapping_perf.py <venv-name>"""
import sys, time
import reflex
assert sys.argv[1] in reflex.__file__, reflex.__file__
from reflex.vars.base import figure_out_type
import reflex as rx
d = {f"k{i}": i for i in range(2_000_000)}
d["zzz"] = "str-after-sample"  # heterogeneous value past the 100-entry sample
t = time.perf_counter(); ty = figure_out_type(d); t1 = time.perf_counter() - t
print(f"{reflex.__version__ if hasattr(reflex,'__version__') else ''} figure_out_type 2M dict: {t1*1000:.1f} ms -> {ty}")
