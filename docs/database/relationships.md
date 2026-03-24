# Relationships

Foreign key relationships are used to link two tables together. For example,
the `Post` model may have a field, `user_id`, with a foreign key of `user.id`,
referencing a `User` model. This would allow us to automatically query the `Post` objects
associated with a user, or find the `User` object associated with a `Post`.

To establish bidirectional relationships a model must correctly set the
`back_populates` keyword argument on the `Relationship` to the relationship
attribute in the _other_ model.

## Foreign Key Relationships

To create a relationship, first add a field to the model that references the
primary key of the related table, then add a `sqlmodel.Relationship` attribute
which can be used to access the related objects.

Defining relationships like this requires the use of `sqlmodel` objects as
seen in the example.

```python
from typing import List, Optional

import sqlmodel

import reflex as rx


class Post(rx.Model, table=True):
    title: str
    body: str
    user_id: int = sqlmodel.Field(foreign_key="user.id")

    user: Optional["User"] = sqlmodel.Relationship(back_populates="posts")
    flags: Optional[List["Flag"]] = sqlmodel.Relationship(back_populates="post")


class User(rx.Model, table=True):
    username: str
    email: str

    posts: List[Post] = sqlmodel.Relationship(back_populates="user")
    flags: List["Flag"] = sqlmodel.Relationship(back_populates="user")


class Flag(rx.Model, table=True):
    post_id: int = sqlmodel.Field(foreign_key="post.id")
    user_id: int = sqlmodel.Field(foreign_key="user.id")
    message: str

    post: Optional[Post] = sqlmodel.Relationship(back_populates="flags")
    user: Optional[User] = sqlmodel.Relationship(back_populates="flags")
```

See the [SQLModel Relationship Docs](https://sqlmodel.tiangolo.com/tutorial/relationship-attributes/define-relationships-attributes/) for more details.

## Querying Relationships

### Inserting Linked Objects

The following example assumes that the flagging user is stored in the state as a
`User` instance and that the post `id` is provided in the data submitted in the
form.

```python
class FlagPostForm(rx.State):
    user: User

    @rx.event
    def flag_post(self, form_data: dict[str, Any]):
        with rx.session() as session:
            post = session.get(Post, int(form_data.pop("post_id")))
            flag = Flag(message=form_data.pop("message"), post=post, user=self.user)
            session.add(flag)
            session.commit()
```

### How are Relationships Dereferenced?

By default, the relationship attributes are in **lazy loading** or `"select"`
mode, which generates a query _on access_ to the relationship attribute. Lazy
loading is generally fine for single object lookups and manipulation, but can be
inefficient when accessing many linked objects for serialization purposes.

There are several alternative loading mechanisms available that can be set on
the relationship object or when performing the query.

* "joined" or `joinload` - generates a single query to load all related objects
  at once.
* "subquery" or `subqueryload` - generates a single query to load all related
  objects at once, but uses a subquery to do the join, instead of a join in the
  main query.
* "selectin" or `selectinload` - emits a second (or more) SELECT statement which
  assembles the primary key identifiers of the parent objects into an IN clause,
  so that all members of related collections / scalar references are loaded at
  once by primary key

There are also non-loading mechanisms, "raise" and "noload" which are used to
specifically avoid loading a relationship.

Each loading method comes with tradeoffs and some are better suited for different
data access patterns.
See [SQLAlchemy: Relationship Loading Techniques](https://docs.sqlalchemy.org/en/14/orm/loading_relationships.html)
for more detail.

### Querying Linked Objects

To query the `Post` table and include all `User` and `Flag` objects up front,
the `.options` interface will be used to specify `selectinload` for the required
relationships. Using this method, the linked objects will be available for
rendering in frontend code without additional steps.

```python
import sqlalchemy


class PostState(rx.State):
    posts: List[Post]

    @rx.event
    def load_posts(self):
        with rx.session() as session:
            self.posts = session.exec(
                Post.select
                .options(
                    sqlalchemy.orm.selectinload(Post.user),
                    sqlalchemy.orm.selectinload(Post.flags).options(
                        sqlalchemy.orm.selectinload(Flag.user),
                    ),
                )
                .limit(15)
            ).all()
```

The loading methods create new query objects and thus may be linked if the
relationship itself has other relationships that need to be loaded. In this
example, since `Flag` references `User`, the `Flag.user` relationship must be
chain loaded from the `Post.flags` relationship.

### Specifying the Loading Mechanism on the Relationship

Alternatively, the loading mechanism can be specified on the relationship by
passing `sa_relationship_kwargs=\{"lazy": method}` to `sqlmodel.Relationship`,
which will use the given loading mechanism in all queries by default.

```python
from typing import List, Optional

import sqlmodel

import reflex as rx


class Post(rx.Model, table=True):
    ...
    user: Optional["User"] = sqlmodel.Relationship(
        back_populates="posts",
        sa_relationship_kwargs=\{"lazy": "selectin"},
    )
    flags: Optional[List["Flag"]] = sqlmodel.Relationship(
        back_populates="post",
        sa_relationship_kwargs=\{"lazy": "selectin"},
    )
```
