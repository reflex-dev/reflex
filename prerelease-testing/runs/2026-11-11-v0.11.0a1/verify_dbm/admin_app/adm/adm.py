import reflex as rx
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
from sqlmodel import Field, SQLModel
from starlette.applications import Starlette
from starlette_admin.contrib.sqla import Admin, ModelView

from reflex.model import get_engine


class Base(MappedAsDataclass, DeclarativeBase):
    pass


rx.ModelRegistry.register(Base)


class Tag(Base):
    __tablename__ = "tag"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str]


class Label(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


admin_app = Starlette()
admin = Admin(get_engine(), title="My Admin")  # no auth: test only
admin.add_view(ModelView(Tag))
admin.add_view(ModelView(Label))
admin.mount_to(admin_app)


def index():
    return rx.text("hi")


app = rx.App(api_transformer=admin_app)
app.add_page(index)
