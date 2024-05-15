import datetime
from typing import List

from sqlmodel import Column, DateTime, Field, Relationship, func

import reflex as rx


class ReflexAuthUser(
    rx.Model,
    table=True,  # type: ignore
):
    """A local User model to correlate with external auth providers."""

    foreign_user_id: str = Field(unique=True, nullable=False, index=True)
    provider: str = Field(nullable=False, index=True)

    membership: List["ReflexAuthGroupMembership"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete"},
    )
    permissions: List["ReflexAuthPermission"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete"},
    )
    sessions: List["ReflexAuthSession"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete"},
    )


class ReflexAuthGroup(
    rx.Model,
    table=True,  # type: ignore
):
    """A local Group model"""

    name: str = Field(unique=True, nullable=False, index=True)

    membership: List["ReflexAuthGroupMembership"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"cascade": "all, delete"},
    )
    permissions: List["ReflexAuthPermission"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"cascade": "all, delete"},
    )


class ReflexAuthGroupMembership(
    rx.Model,
    table=True,  # type: ignore
):
    """A local Group membership link table"""

    group_id: int = Field(index=True, nullable=False, foreign_key="reflexauthgroup.id")
    user_id: int = Field(index=True, nullable=False, foreign_key="reflexauthuser.id")

    group: ReflexAuthGroup = Relationship(back_populates="membership")
    user: ReflexAuthUser = Relationship(back_populates="membership")


class ReflexAuthPermission(
    rx.Model,
    table=True,  # type: ignore
):
    """A local Permission model"""

    name: str = Field(index=True, nullable=False)
    user_id: int = Field(index=True, nullable=True, foreign_key="reflexauthuser.id")
    group_id: int = Field(index=True, nullable=True, foreign_key="reflexauthgroup.id")
    allow: bool = Field(nullable=True)
    deny: bool = Field(nullable=True)

    group: ReflexAuthGroup = Relationship(back_populates="permissions")
    user: ReflexAuthUser = Relationship(back_populates="permissions")


class ReflexAuthSession(
    rx.Model,
    table=True,  # type: ignore
):
    """Correlate a session_id with an arbitrary user_id."""

    user_id: int = Field(index=True, nullable=False, foreign_key="reflexauthuser.id")
    session_id: str = Field(index=True, nullable=False)
    client_ip: str = Field(nullable=False)
    expiration: datetime.datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
    )
    active: bool = Field(default=True, nullable=False, index=True)

    user: ReflexAuthUser = Relationship(back_populates="sessions")
