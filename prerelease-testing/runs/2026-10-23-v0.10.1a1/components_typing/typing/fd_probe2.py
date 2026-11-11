"""Root cause of the rx.form typing change and ty's view of rx.Field[rx.Model | None]."""
from typing import reveal_type

import reflex as rx
from reflex_base.components.component import ComponentNamespace
from reflex_components_radix.primitives.form import FormNamespace, FormRoot, form


class User(rx.Model, table=True):
    name: str


class Plain(rx.Model):
    name: str


class S(rx.State):
    opt: rx.Field[User | None] = rx.field(None)
    req: rx.Field[User] = rx.field(default_factory=lambda: User(name=""))
    plain_opt: rx.Field[Plain | None] = rx.field(None)
    plain_req: rx.Field[Plain] = rx.field(default_factory=lambda: Plain(name=""))


reveal_type(S.opt)
reveal_type(S.req)
reveal_type(S.plain_opt)
reveal_type(S.plain_req)
reveal_type(form)
reveal_type(FormNamespace)
reveal_type(FormNamespace.root)
reveal_type(form.root)
reveal_type(FormRoot.create)
reveal_type(FormRoot.create(rx.input()))
reveal_type(form(rx.input()))
reveal_type(ComponentNamespace.__call__)
