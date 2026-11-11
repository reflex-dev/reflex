import os
import secrets

import reflex as rx
from sqlmodel import Field, SQLModel
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette_admin.auth import AdminUser, AuthProvider, LoginFailed
from starlette_admin.contrib.sqla import Admin, ModelView

from reflex.model import get_engine


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str
    email: str


class MyAuthProvider(AuthProvider):
    async def login(
        self, username: str, password: str, remember_me: bool, request: Request
    ) -> None:
        if not (
            secrets.compare_digest(
                username.encode(), os.environ["ADMIN_USERNAME"].encode()
            )
            and secrets.compare_digest(
                password.encode(), os.environ["ADMIN_PASSWORD"].encode()
            )
        ):
            raise LoginFailed("Invalid username or password")
        request.session["admin_user"] = username

    async def authenticate(self, request: Request) -> AdminUser | None:
        if username := request.session.get("admin_user"):
            return AdminUser(username=username)
        return None

    async def logout(self, request: Request) -> None:
        request.session.clear()


secret_key = os.environ["ADMIN_SECRET_KEY"]

admin_app = Starlette()
admin = Admin(
    get_engine(),
    title="My Admin",
    auth_provider=MyAuthProvider(),
    secret_key=secret_key,
    middlewares=[Middleware(SessionMiddleware, secret_key=secret_key)],
)
admin.add_view(ModelView(User))


# phase7 additions, not in the guide: MappedAsDataclass models per the guide's "New" form note
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class TagOk(Base):  # every constructor field has a default -> "New" should work
    __tablename__ = "tagok"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str] = mapped_column(default="")


class TagReq(Base):  # required field -> guide says "New" fails with 500
    __tablename__ = "tagreq"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str]


admin.add_view(ModelView(TagOk))
admin.add_view(ModelView(TagReq))
admin.mount_to(admin_app)

app = rx.App(api_transformer=admin_app)


def index():
    return rx.text("hi")


app.add_page(index)
