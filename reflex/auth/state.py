from __future__ import annotations

import datetime
from typing import ClassVar

import sqlalchemy
from sqlmodel import or_, select

import reflex as rx

from .models import (
    ReflexAuthGroup,
    ReflexAuthGroupMembership,
    ReflexAuthPermission,
    ReflexAuthSession,
    ReflexAuthUser,
)

AUTH_TOKEN_LOCAL_STORAGE_KEY = "_auth_token"
DEFAULT_AUTH_SESSION_EXPIRATION_DELTA = datetime.timedelta(days=7)


class ReflexAuthProvider(rx.State):
    """Subclass this to implement a custom authentication provider."""

    _reflex_auth_provider: ClassVar[str] = "base"

    async def _validate_user(self) -> bool:
        """Check that the currently authenticated user is still valid."""
        return False

    @classmethod
    def get_login_component(cls) -> rx.Component:
        return rx.fragment()


class ReflexAuthState(rx.State):
    # The auth_token is stored in local storage to persist across tab and browser sessions.
    auth_token: str = rx.LocalStorage(name=AUTH_TOKEN_LOCAL_STORAGE_KEY)

    @rx.cached_var
    def authenticated_user(self) -> ReflexAuthUser:
        """The currently authenticated user, or a dummy user if not authenticated.

        Returns:
            A ReflexAuthUser instance with id=-1 if not authenticated, or the ReflexAuthUser instance
            corresponding to the currently authenticated user.
        """
        with rx.session() as session:
            result = session.exec(
                select(ReflexAuthUser, ReflexAuthSession).where(
                    ReflexAuthSession.active == True,  # type: ignore
                    ReflexAuthSession.session_id == self.auth_token,
                    ReflexAuthSession.expiration
                    >= datetime.datetime.now(datetime.timezone.utc),
                    ReflexAuthUser.id == ReflexAuthSession.user_id,
                ),
            ).first()
            if result:
                user, session = result
                return user
        return ReflexAuthUser(id=-1)  # type: ignore

    @rx.cached_var
    def is_authenticated(self) -> bool:
        """Whether the current user is authenticated.

        Returns:
            True if the authenticated user has a positive user ID, False otherwise.
        """
        return self.authenticated_user.id >= 0

    def do_logout(self) -> None:
        """Destroy ReflexAuthSessions associated with the auth_token."""
        with rx.session() as session:
            for auth_session in session.exec(
                select(ReflexAuthSession).where(
                    ReflexAuthSession.session_id == self.auth_token,
                    ReflexAuthSession.active == True,  # type: ignore
                )
            ).all():
                auth_session.active = False
            session.commit()
        self.auth_token = self.auth_token

    def _login(
        self,
        foreign_user_id: str,
        provider: str,
        expiration_delta: datetime.timedelta = DEFAULT_AUTH_SESSION_EXPIRATION_DELTA,
    ) -> None:
        """Create an ReflexAuthSession for the given user_id.

        If the auth_token is already associated with an ReflexAuthSession, it will be
        logged out first.

        Args:
            user_id: The user ID to associate with the ReflexAuthSession.
            expiration_delta: The amount of time before the ReflexAuthSession expires.
        """
        if self.is_authenticated:
            self.do_logout()
        # Find the user_id for the given foreign_user_id and provider.
        with rx.session() as session:
            user_id_row = session.exec(
                select(ReflexAuthUser.id)
                .where(ReflexAuthUser.foreign_user_id == foreign_user_id)
                .where(ReflexAuthUser.provider == provider)
            ).first()
            if user_id_row is None:
                user = ReflexAuthUser(
                    foreign_user_id=foreign_user_id, provider=provider
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                user_id = user.id
                if user_id == 1:
                    # The first user to login becomes the admin for this app
                    self._update_permission(
                        permission_name="admin",
                        user=user,
                        allow=True,
                    )
                    session.commit()
            else:
                user_id = user_id_row
        self.auth_token = self.auth_token or self.router.session.client_token
        client_ip = getattr(
            self.router.headers,
            "x_forwarded_for",
            self.router.session.client_ip,
        )
        with rx.session() as session:
            session.add(
                ReflexAuthSession(  # type: ignore
                    user_id=user_id,
                    session_id=self.auth_token,
                    client_ip=client_ip,
                    expiration=datetime.datetime.now(datetime.timezone.utc)
                    + expiration_delta,
                )
            )
            session.commit()

    async def _validate_user(self) -> bool:
        """Check that the currently authenticated user is still valid."""
        ReflexAuthState.authenticated_user.mark_dirty(self)
        ReflexAuthState.is_authenticated.mark_dirty(self)
        valid = self.is_authenticated
        # Find the provider and call into _validate_user
        for substate_clz in ReflexAuthProvider.class_subclasses:
            if (
                substate_clz._reflex_auth_provider
                == self.authenticated_user.provider
            ):
                provider_state = await self.get_state(substate_clz)
                valid = valid and await provider_state._validate_user()
                break
        else:
            # Provider class not found, cannot validate
            return False
        return valid

    def _get_user_by_id(self, user_id: int) -> ReflexAuthUser:
        """Get the user by ID."""
        with rx.session() as session:
            return session.exec(
                select(ReflexAuthUser).where(ReflexAuthUser.id == user_id)
            ).first() or ReflexAuthUser(id=-1)

    async def _has_permission(self, permission_name) -> bool | None:
        """Check if the currently authenticated user has permission.

        Returns:
            True if permission is granted, False if permission is denied, and None if unspecified.
        """
        if not await self._validate_user():
            return False
        with rx.session() as session:
            result = session.exec(
                select(ReflexAuthPermission).where(
                    ReflexAuthPermission.name == permission_name,
                    or_(
                        ReflexAuthPermission.user_id == self.authenticated_user.id,
                        ReflexAuthPermission.group_id.in_(
                            select(ReflexAuthGroupMembership.group_id).where(
                                ReflexAuthGroupMembership.user_id
                                == self.authenticated_user.id
                            )
                        ),
                    ),
                )
            ).all()
            if any(permission.deny for permission in result):
                return False
            if any(permission.allow for permission in result):
                return True

    def _add_group(self, group_name: str) -> ReflexAuthGroup:
        """Create a new group with the given name."""
        with rx.session() as session:
            group = session.exec(
                select(ReflexAuthGroup).where(ReflexAuthGroup.name == group_name)
            ).first()
            if group is not None:
                return group
            group = ReflexAuthGroup(name=group_name)
            session.add(group)
            session.commit()
            session.refresh(group)
            return group

    def _remove_group(self, group_name: str):
        """Remove the group with the given name."""
        with rx.session() as session:
            for group in session.exec(
                select(ReflexAuthGroup).where(ReflexAuthGroup.name == group_name)
            ).all():
                session.delete(group)
            session.commit()

    def _add_user_to_group(self, group_name: str, user: ReflexAuthUser):
        """Add the user to the group with the given name."""
        with rx.session() as session:
            group = session.exec(
                select(ReflexAuthGroup).where(ReflexAuthGroup.name == group_name)
            ).first()
            if group is None:
                return
            membership = session.exec(
                select(ReflexAuthGroupMembership).where(
                    ReflexAuthGroupMembership.group_id == group.id,
                    ReflexAuthGroupMembership.user_id == user.id,
                )
            ).first()
            if membership:
                return
            membership = ReflexAuthGroupMembership(group_id=group.id, user_id=user.id)
            session.add(membership)
            session.commit()

    def _remove_user_from_group(self, group_name: str, user: ReflexAuthUser):
        """Remove the user from the group with the given name."""
        with rx.session() as session:
            group = session.exec(
                select(ReflexAuthGroup).where(ReflexAuthGroup.name == group_name)
            ).first()
            if group is None:
                return
            for group_membership in session.exec(
                select(ReflexAuthGroupMembership).where(
                    ReflexAuthGroupMembership.group_id == group.id,
                    ReflexAuthGroupMembership.user_id == user.id,
                )
            ).all():
                session.delete(group_membership)
            session.commit()

    def _enum_groups(self, user_id: int | None = None) -> list[ReflexAuthGroup]:
        """Get a list of all groups."""
        query = select(ReflexAuthGroup).options(
            sqlalchemy.orm.selectinload(ReflexAuthGroup.permissions)
        )
        if user_id is not None:
            query = query.where(
                ReflexAuthGroup.id.in_(
                    select(ReflexAuthGroupMembership.group_id).where(
                        ReflexAuthGroupMembership.user_id == user_id
                    )
                )
            )
        with rx.session() as session:
            return session.exec(query).all()

    def _update_permission(
        self,
        permission_name: str,
        user: ReflexAuthUser | None = None,
        group_name: str | None = None,
        allow: bool | None = None,
        deny: bool | None = None,
        remove: bool = False,
    ):
        """Grant the permission to the user or group."""
        user_id = group_id = None
        if user is not None:
            user_id = user.id
        if group_name is not None:
            with rx.session() as session:
                group = session.exec(
                    select(ReflexAuthGroup).where(ReflexAuthGroup.name == group_name)
                ).first()
                if group is not None:
                    group_id = group.id

        if user_id is None and group_id is None:
            return  # No valid principal found

        with rx.session() as session:
            if remove:
                for permission in session.exec(
                    select(ReflexAuthPermission).where(
                        ReflexAuthPermission.name == permission_name,
                        ReflexAuthPermission.user_id == user_id,
                        ReflexAuthPermission.group_id == group_id,
                    )
                ).all():
                    session.delete(permission)
                session.commit()
                return
            permission = ReflexAuthPermission(
                name=permission_name,
                user_id=user_id,
                group_id=group_id,
                allow=allow,
                deny=deny,
            )
            session.add(permission)
            session.commit()

    def _get_permissions(self) -> list[str]:
        """Get a list of all permissions the user has."""
        permissions: dict[str, bool] = {}
        with rx.session() as session:
            for permission in session.exec(
                select(ReflexAuthPermission).where(
                    or_(
                        ReflexAuthPermission.user_id == self.authenticated_user.id,
                        ReflexAuthPermission.group_id.in_(
                            select(ReflexAuthGroupMembership.group_id).where(
                                ReflexAuthGroupMembership.user_id
                                == self.authenticated_user.id
                            )
                        ),
                    )
                )
            ).all():
                if permission.allow and permission.name not in permissions:
                    permissions[permission.name] = True
                if permission.deny:
                    permissions[permission.name] = False
        return [permission for permission, granted in permissions.items() if granted]

    @classmethod
    def get_login_page(
        cls, header: rx.Component | None = None, footer: rx.Component | None = None
    ) -> rx.Component:
        """Get the login page for all authentication providers."""
        if header is None:
            header = rx.heading("Login")
        if footer is None:
            footer = rx.fragment()
        providers = [
            provider.get_login_component()
            for provider in ReflexAuthProvider.class_subclasses
        ]
        if not providers:
            providers = [
                rx.text(
                    "No auth providers detected. Did you import the provider in your app?"
                )
            ]
        return rx.vstack(
            header,
            *providers,
            footer,
            align="center",
        )


def require_login(page: rx.app.ComponentCallable) -> rx.app.ComponentCallable:
    """Decorator to require authentication before rendering a page.

    If the user is not authenticated, then render the multi-login form.

    Args:
        page: The page to wrap.

    Returns:
        The wrapped page component.
    """

    def protected_page():
        return rx.fragment(
            rx.cond(
                ReflexAuthState.is_authenticated,  # type: ignore
                page(),
                rx.cond(
                    rx.State.is_hydrated,
                    ReflexAuthState.get_login_page(),
                ),
            )
        )

    protected_page.__name__ = page.__name__
    return protected_page
