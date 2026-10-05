"""#6930: lazy imports cache resolved attrs on the package; __getattr__ still errors helpfully."""
import json, sys, time
import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
out = {"python": sys.version.split()[0], "reflex": rx.constants.Reflex.VERSION}

# first access resolves; is it cached in the module dict?
out["text_in_dict_before"] = "text" in vars(rx)
_ = rx.text
out["text_in_dict_after"] = "text" in vars(rx)
_ = rx.cond
out["cond_in_dict_after"] = "cond" in vars(rx)

N = 1_000_000
t0 = time.perf_counter()
for _i in range(N):
    rx.text
out["sec_per_1e6_attr_access"] = round(time.perf_counter() - t0, 4)

# bad name handling
for bad in ("definitely_not_a_thing", "_private_missing", "Text"):
    try:
        getattr(rx, bad)
        out[f"bad_{bad}"] = "NO ERROR"
    except Exception as e:
        out[f"bad_{bad}"] = f"{type(e).__name__}: {e}"

# dir() still lists the lazy names
d = dir(rx)
out["dir_has_text"] = "text" in d
out["dir_len"] = len(d)

# submodule access
try:
    out["submodule_rx_el_div"] = str(type(rx.el.div))
except Exception as e:
    out["submodule_rx_el_div"] = f"{type(e).__name__}: {e}"
try:
    out["rx_x"] = str(type(rx._x.client_state))
except Exception as e:
    out["rx_x"] = f"{type(e).__name__}: {e}"
print(json.dumps(out, indent=2, default=str))
