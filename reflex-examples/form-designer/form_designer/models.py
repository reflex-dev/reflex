import datetime
from enum import Enum
from typing import Optional

import sqlmodel

import reflex as rx
from reflex.utils.serializers import serializer

from reflex_local_auth import LocalUser


class FieldType(Enum):
    text = "text"
    number = "number"
    email = "email"
    password = "password"
    checkbox = "checkbox"
    radio = "radio"
    select = "select"
    textarea = "textarea"


@serializer
def serialize_field_type(value: FieldType) -> str:
    return value.value


class Option(rx.Model, table=True):
    label: str = ""
    value: str = ""

    field_id: int = sqlmodel.Field(foreign_key="field.id")


class Field(rx.Model, table=True):
    name: str = ""
    type_: FieldType = FieldType.text
    required: bool = False
    prompt: str = ""

    form_id: int = sqlmodel.Field(foreign_key="form.id")
    options: list[Option] = sqlmodel.Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )
    field_values: list["FieldValue"] = sqlmodel.Relationship(
        back_populates="field",
        sa_relationship_kwargs={"lazy": "noload", "cascade": "all, delete"},
    )


class Form(rx.Model, table=True):
    name: str = ""
    owner_id: int = sqlmodel.Field(foreign_key="localuser.id")

    fields: list[Field] = sqlmodel.Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )
    responses: list["Response"] = sqlmodel.Relationship(
        back_populates="form",
        sa_relationship_kwargs={"cascade": "all, delete"},
    )
    user: Optional[LocalUser] = sqlmodel.Relationship()


class FieldValue(rx.Model, table=True):
    field_id: int = sqlmodel.Field(foreign_key="field.id")
    response_id: int = sqlmodel.Field(foreign_key="response.id")
    value: str

    field: Field = sqlmodel.Relationship(sa_relationship_kwargs={"lazy": "selectin"})


class Response(rx.Model, table=True):
    client_token: str
    form_id: int = sqlmodel.Field(foreign_key="form.id")
    ts: datetime.datetime = sqlmodel.Field(
        sa_column=sqlmodel.Column(
            sqlmodel.DateTime(timezone=True),
            server_default=sqlmodel.func.now(),
        ),
    )
    hidden: bool = False
    form: Form = sqlmodel.Relationship(back_populates="responses")

    field_values: list[FieldValue] = sqlmodel.Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"}
    )
