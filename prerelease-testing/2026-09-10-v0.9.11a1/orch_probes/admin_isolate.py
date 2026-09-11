"""Isolate rx.AdminDash's 500: the same starlette-admin Admin mounted on a plain Starlette app.

Run with a venv that has starlette-admin + sqlalchemy:
    cd /tmp && <venv>/bin/python admin_isolate.py
"""
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient
from starlette_admin.contrib.sqla import Admin, ModelView
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Widget(Base):
    __tablename__ = "widget"
    id = Column(Integer, primary_key=True)
    name = Column(String)


engine = create_engine("sqlite://")
Base.metadata.create_all(engine)


def build(nested: bool):
    inner = Starlette()
    admin = Admin(engine)
    admin.add_view(ModelView(Widget))
    admin.mount_to(inner)
    return Starlette(routes=[Mount("/", app=inner)]) if nested else inner


for label, nested in (("admin on the app itself", False), ("admin on a sub-app mounted at /", True)):
    app = build(nested)
    with TestClient(app, raise_server_exceptions=False) as c:
        print(label, {p: c.get(p).status_code for p in ("/admin/", "/admin/widget/list")})
