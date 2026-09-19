"""#7131: EnvVar reads timedelta as seconds or with us/ms/s/m/h/d suffix."""
import dataclasses, json, os
from datetime import timedelta
import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
from reflex_base.environment import EnvironmentVariables, env_var, environment
from reflex_base import environment as envmod

@dataclasses.dataclass(init=False)
class MyEnv(EnvironmentVariables):
    MY_TIMEOUT: envmod.EnvVar[timedelta] = env_var(timedelta(seconds=10))
    MY_OPT: envmod.EnvVar[timedelta | None] = env_var(None)

my = MyEnv()

cases = ["30", "0", "500ms", "2m", "1.5h", "1d", "250us", "  45S ", "7H", "3.25", "1e3",
         "abc", "5x", "", "-5", "9999999999999d", "10 s", "1,000", "0.0000001us"]
out = {"has_interpret": hasattr(envmod, "interpret_timedelta_env")}
res = {}
for c in cases:
    os.environ["MY_TIMEOUT"] = c
    try:
        v = my.MY_TIMEOUT.get()
        res[repr(c)] = {"ok": True, "value": str(v), "total_seconds": v.total_seconds()}
    except Exception as e:
        res[repr(c)] = {"ok": False, "err": f"{type(e).__name__}: {e}"}
os.environ.pop("MY_TIMEOUT", None)
out["cases"] = res

# default when unset
out["default_unset"] = str(my.MY_TIMEOUT.get())
# optional union
for c in ["", "30", "bad"]:
    os.environ["MY_OPT"] = c
    try:
        out[f"optional_{c!r}"] = str(my.MY_OPT.get())
    except Exception as e:
        out[f"optional_{c!r}"] = f"{type(e).__name__}: {e}"
os.environ.pop("MY_OPT", None)

# round trip: does the env serializer emit something re-parseable?
if hasattr(envmod, "_format_env_value") or True:
    for fn_name in ("_format_env_value", "format_env_value", "env_value_to_str"):
        fn = getattr(envmod, fn_name, None)
        if fn:
            out["formatter"] = fn_name
            samples = {}
            for td in (timedelta(seconds=30), timedelta(milliseconds=500), timedelta(hours=1.5),
                       timedelta(days=1), timedelta(microseconds=250), timedelta(seconds=0)):
                s = fn(td)
                try:
                    back = envmod.interpret_timedelta_env(s, "X")
                    samples[str(td)] = {"formatted": s, "roundtrip_equal": back == td, "back": str(back)}
                except Exception as e:
                    samples[str(td)] = {"formatted": s, "err": f"{type(e).__name__}: {e}"}
            out["roundtrip"] = samples
            break
print(json.dumps(out, indent=2, default=str))
