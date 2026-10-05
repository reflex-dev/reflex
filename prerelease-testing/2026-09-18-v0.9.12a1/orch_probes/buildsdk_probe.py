import logging, sys, os
import reflex
assert "/envs/buildsdk/" in reflex.__file__, reflex.__file__
import reflex_build_sdk as sdk
print("reflex_build_sdk version:", getattr(sdk, "__version__", "?"), "file:", sdk.__file__)
from reflex_build_sdk import ReflexBuild, AsyncReflexBuild, ReflexBuildError
print("new names OK:", ReflexBuild, AsyncReflexBuild, ReflexBuildError)
for old in ("ReflexCloud", "AsyncReflexCloud", "ReflexCloudError", "Reflex", "AsyncReflex", "ReflexError", "Client", "AsyncClient"):
    try:
        getattr(sdk, old); print("old name still present:", old)
    except AttributeError as e:
        print("old name gone:", old, "->", str(e)[:100])
# logging routing (#7166): the sdk logger should be under the reflex logging tree / handled by reflex's logger
lg = logging.getLogger("reflex_build_sdk")
print("logger name/level/propagate/handlers:", lg.name, lg.level, lg.propagate, lg.handlers, "parent:", lg.parent.name if lg.parent else None)
for name in sorted(n for n in logging.Logger.manager.loggerDict if "reflex" in n)[:40]:
    print("  logger:", name)
# env var precedence (#7201)
os.environ["REFLEX_CLOUD_BACKEND_URL"] = "http://cloud-backend.invalid"
os.environ["REFLEX_BUILD_BACKEND_URL"] = "http://build-backend.invalid"
try:
    c = ReflexBuild(token="x") if "token" in ReflexBuild.__init__.__code__.co_varnames else ReflexBuild()
    for attr in ("backend_url", "base_url", "_backend_url", "url", "_base_url"):
        if hasattr(c, attr): print("client", attr, "=", getattr(c, attr))
    print("client dir:", [a for a in dir(c) if not a.startswith("__")][:40])
except Exception as e:
    print("construct:", type(e).__name__, str(e)[:200])
