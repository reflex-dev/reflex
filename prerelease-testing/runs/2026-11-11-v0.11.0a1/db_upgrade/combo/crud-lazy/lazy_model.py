"""QA: a model that only a page function imports."""

from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    message: str = ""
