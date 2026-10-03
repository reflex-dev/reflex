"""Inferred types for `reflex.model` that are part of the public contract."""

import sqlmodel
from sqlalchemy import Engine, MetaData
from sqlalchemy.orm import Session
from sqlmodel.ext.asyncio.session import AsyncSession
from typing_extensions import assert_type

import reflex as rx
from reflex.model import ModelRegistry, get_engine, migrate, sqla_session

# The db helpers are only defined when the db extra is installed, and fall back to
# stand-ins that point at it otherwise. A checker has to see the real definitions:
# ty used to union in the stand-ins, so `rx.session()` was `Session | Unknown` and
# `ModelRegistry.register` did not exist on `_ClassThatErrorsOnInit`.
assert_type(ModelRegistry.get_metadata(), MetaData)
assert_type(get_engine(), Engine)
assert_type(sqla_session(), Session)
assert_type(migrate(), bool | None)
assert_type(rx.session(), sqlmodel.Session)
assert_type(rx.asession(), AsyncSession)
