# Generated from packages/reflex-build-sdk/src/reflex_build_sdk/_async/resources/usage.py by packages/reflex-build-sdk/scripts/unasync.py. Do not edit.
"""The plan usage endpoints."""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from reflex_build_sdk._base import decode_response
from reflex_build_sdk.transports import Response
from reflex_build_sdk.types import UsageBalance, UsageEntry

if TYPE_CHECKING:
    from reflex_build_sdk._sync._client import ReflexBuild

# The response header holding the cursor of the next page of usage history.
_NEXT_CURSOR_HEADER = "x-next-cursor"


def _iso(value: datetime.date | None) -> str | None:
    """Format a usage history bound the way the API takes it.

    Args:
        value: A date, a timezone-aware datetime, or None for the default.

    Returns:
        The ISO 8601 text, or None for the default.

    Raises:
        ValueError: If ``value`` is a naive datetime.
    """
    if value is None:
        return None
    # The server reads a naive datetime in its database's time zone.
    if isinstance(value, datetime.datetime) and value.utcoffset() is None:
        msg = f"expected a timezone-aware datetime, got naive {value!r}"
        raise ValueError(msg)
    return value.isoformat()


class Usage:
    """Read an organization's use of its plan allowance.

    The allowance covers AI builder generations and app hosting together. Amounts
    are shares of it, never dollars. Both methods read the organization of the
    calling token.
    """

    def __init__(self, client: ReflexBuild) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def balance(self) -> UsageBalance:
        """Get how much of the allowance is used this period, and when it refills.

        Returns:
            The balance.
        """
        # Reading the balance may grant a refill that is due, which is harmless to
        # repeat.
        return self._client._request("GET", "user/usage/balance", UsageBalance)

    def history(
        self,
        *,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> Iterator[UsageEntry]:
        """Iterate over the charges and credits against the allowance, newest first.

        Fetches further pages as needed.

        Args:
            start: The earliest time to include: a date, or a timezone-aware
                datetime. Defaults to 30 days ago.
            end: The time to stop before, or a date to include all of. Defaults to
                tomorrow.

        Yields:
            The entries.

        Raises:
            ValueError: If ``start`` or ``end`` is a naive datetime, when iteration
                starts.
        """
        params: dict[str, Any] = {"start_date": _iso(start), "end_date": _iso(end)}
        while True:
            response = self._client._request(
                "GET", "user/usage/history", Response, params=params
            )
            for entry in decode_response(response, list[UsageEntry]):
                yield entry
            cursor = response.headers.get(_NEXT_CURSOR_HEADER)
            if cursor is None:
                return
            params["cursor"] = cursor
