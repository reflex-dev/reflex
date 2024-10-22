"""Client-side storage classes for reflex state variables."""

from __future__ import annotations

from typing import Any

from reflex.utils import format


class ClientStorageBase:
    """Base class for client-side storage."""

    def options(self) -> dict[str, Any]:
        """Get the options for the storage.

        Returns:
            All set options for the storage (not None).
        """
        return {
            format.to_camel_case(k): v for k, v in vars(self).items() if v is not None
        }


class Cookie(ClientStorageBase, str):
    """Represents a state Var that is stored as a cookie in the browser."""

    name: str | None
    path: str
    max_age: int | None
    domain: str | None
    secure: bool | None
    same_site: str

    def __new__(
        cls,
        object: Any = "",
        encoding: str | None = None,
        errors: str | None = None,
        /,
        name: str | None = None,
        path: str = "/",
        max_age: int | None = None,
        domain: str | None = None,
        secure: bool | None = None,
        same_site: str = "lax",
    ):
        """Create a client-side Cookie (str).

        Args:
            object: The initial object.
            encoding: The encoding to use.
            errors: The error handling scheme to use.
            name: The name of the cookie on the client side.
            path: Cookie path. Use / as the path if the cookie should be accessible on all pages.
            max_age: Relative max age of the cookie in seconds from when the client receives it.
            domain: Domain for the cookie (sub.domain.com or .allsubdomains.com).
            secure: Is the cookie only accessible through HTTPS?
            same_site: Whether the cookie is sent with third party requests.
                One of (true|false|none|lax|strict)

        Returns:
            The client-side Cookie object.

        Note: expires (absolute Date) is not supported at this time.
        """
        if encoding or errors:
            inst = super().__new__(cls, object, encoding or "utf-8", errors or "strict")
        else:
            inst = super().__new__(cls, object)
        inst.name = name
        inst.path = path
        inst.max_age = max_age
        inst.domain = domain
        inst.secure = secure
        inst.same_site = same_site
        return inst


class LocalStorage(ClientStorageBase, str):
    """Represents a state Var that is stored in localStorage in the browser."""

    name: str | None
    sync: bool = False

    def __new__(
        cls,
        object: Any = "",
        encoding: str | None = None,
        errors: str | None = None,
        /,
        name: str | None = None,
        sync: bool = False,
    ) -> "LocalStorage":
        """Create a client-side localStorage (str).

        Args:
            object: The initial object.
            encoding: The encoding to use.
            errors: The error handling scheme to use.
            name: The name of the storage key on the client side.
            sync: Whether changes should be propagated to other tabs.

        Returns:
            The client-side localStorage object.
        """
        if encoding or errors:
            inst = super().__new__(cls, object, encoding or "utf-8", errors or "strict")
        else:
            inst = super().__new__(cls, object)
        inst.name = name
        inst.sync = sync
        return inst


class SessionStorage(ClientStorageBase, str):
    """Represents a state Var that is stored in sessionStorage in the browser."""

    name: str | None

    def __new__(
        cls,
        object: Any = "",
        encoding: str | None = None,
        errors: str | None = None,
        /,
        name: str | None = None,
    ) -> "SessionStorage":
        """Create a client-side sessionStorage (str).

        Args:
            object: The initial object.
            encoding: The encoding to use.
            errors: The error handling scheme to use
            name: The name of the storage on the client side

        Returns:
            The client-side sessionStorage object.
        """
        if encoding or errors:
            inst = super().__new__(cls, object, encoding or "utf-8", errors or "strict")
        else:
            inst = super().__new__(cls, object)
        inst.name = name
        return inst
