# keep the old rx.Model models (all 4 tables) and add a NEW table on a Base with a naming_convention
import shutil
SB = "/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad"
shutil.copy(f"{SB}/apps/db_models/blog_0101_models.py", "blog/models.py")
shutil.copy(f"{SB}/apps/db_models/blog_0101_app.py", "blog/blog.py")
s = open("blog/models.py").read()
s = s.replace("    # MIGRATION2\n", "    bio: str | None = None\n").replace("    # MIGRATION2B\n", "    views: int = 0\n")
s += '''

from sqlalchemy import ForeignKey, MetaData, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

NAMING = {"ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s"}


class Base(MappedAsDataclass, DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


rx.ModelRegistry.register(Base)


class Comment(Base):
    __tablename__ = "comment"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"))
    text: Mapped[str] = mapped_column(unique=True)
'''
open("blog/models.py", "w").write(s)
