# rewritten Base-only models, but Base gets a naming_convention, plus a NEW Comment table
s = open("blog/models.py").read()
s = s.replace('''class Base(MappedAsDataclass, DeclarativeBase):
    """Base class for the app's tables."""''', '''NAMING = {"ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s"}


class Base(MappedAsDataclass, DeclarativeBase):
    """Base class for the app's tables."""
    metadata = MetaData(naming_convention=NAMING)''')
s = s.replace("from sqlalchemy import JSON,", "from sqlalchemy import MetaData, JSON,")
s += '''

class Comment(Base):
    __tablename__ = "comment"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"))
    text: Mapped[str] = mapped_column(unique=True)
'''
open("blog/models.py", "w").write(s)
