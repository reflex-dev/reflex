"""Exercise reflex.app's origin check through engine.io 4.12.0 without importing reflex."""
import ast, pathlib, sys, urllib.parse, logging
from collections.abc import Iterable, Mapping
from typing import Any
import engineio, socketio
src = pathlib.Path(sys.argv[1]).read_text()
tree = ast.parse(src)
names = {"_DEFAULT_PORTS", "_host_authority", "_origin_matches_request", "_SocketOriginCheck"}
nodes = [n for n in tree.body if (getattr(n, "name", None) in names) or (isinstance(n, ast.Assign) and n.targets[0].id in names if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) else False)]
ns = {"urllib": urllib, "Iterable": Iterable, "Mapping": Mapping, "Any": Any, "logger": logging.getLogger("x")}
exec(compile(ast.Module(nodes, []), "app_subset", "exec"), ns)
srv = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=ns["_SocketOriginCheck"]((), True))
env = lambda o, h, **x: {"HTTP_ORIGIN": o, "HTTP_HOST": h, "wsgi.url_scheme": "http", **x}
print("engineio", engineio.__version__ if hasattr(engineio, "__version__") else "?")
print("tls-proxy same host:", srv.eio._cors_allowed_origins(env("https://h", "h")))
print("cross-site:", srv.eio._cors_allowed_origins(env("https://evil", "h")))
