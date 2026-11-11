"""Is the /admin -> /admin/ redirect lost when the Starlette app goes through api_transformer?"""
import sys
import reflex
assert sys.argv[1] in reflex.__file__
import reflex as rx
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

inner = Starlette()
inner.add_route("/", lambda r: PlainTextResponse("admin index"))
outer = Starlette(routes=[Mount("/admin", app=inner)])
c = TestClient(outer)
r = c.get("/admin", follow_redirects=False)
print("plain Starlette /admin ->", r.status_code, r.headers.get("location"))

inner2 = Starlette()
inner2.add_route("/", lambda r: PlainTextResponse("admin index"))
outer2 = Starlette()
outer2.mount("/admin", inner2)
app = rx.App(api_transformer=outer2)
app.add_page(lambda: rx.text("x"), route="/")
asgi = app()
c2 = TestClient(asgi)
r = c2.get("/admin", follow_redirects=False)
print("through rx.App(api_transformer=...) /admin ->", r.status_code, r.headers.get("location"))
r = c2.get("/admin/", follow_redirects=False)
print("through rx.App /admin/ ->", r.status_code, r.text[:30])
