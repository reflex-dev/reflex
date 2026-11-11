import reflex as rx
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class MainBase(DeclarativeBase):
    pass

class OtherBase(DeclarativeBase):  # meant for another database
    pass

class Namespace:
    class NestedBase(DeclarativeBase):
        pass

class A(MainBase):
    __tablename__ = "a"
    id: Mapped[int] = mapped_column(primary_key=True)

class B(OtherBase):
    __tablename__ = "b"
    id: Mapped[int] = mapped_column(primary_key=True)

class C(Namespace.NestedBase):
    __tablename__ = "c"
    id: Mapped[int] = mapped_column(primary_key=True)

rx.ModelRegistry.register(MainBase)
def index():
    return rx.text("hi")
app = rx.App()
app.add_page(index)
