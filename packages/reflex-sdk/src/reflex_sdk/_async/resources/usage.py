"""The plan usage endpoints."""

from __future__ import annotations

import datetime
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from reflex_sdk._base import decode_response
from reflex_sdk.transports import Response
from reflex_sdk.types import UsageBalance, UsageEntry

if TYPE_CHECKING:
    from reflex_sdk._async._client import AsyncReflexCloud

# The response header holding the cursor of the next page of usage history.
_NEXT_CURSOR_HEADER = "x-next-cursor"


def _iso(value: datetime.date | None) -> str | None:
    if value is None:
        return None
    # The server reads a naive datetime in its database's time zone.
    if isinstance(value, datetime.datetime) and value.utcoffset() is None:
        msg = f"expected a timezone-aware datetime, got naive {value!r}"
        raise ValueError(msg)
    return value.isoformat()


class AsyncUsage:
    """Read an organization's use of its plan allowance.

    The allowance covers AI builder generations and app hosting together. Amounts
    are shares of it, never dollars. Both methods read the organization of the
    calling token.
    """

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    async def balance(self) -> UsageBalance:
        """Get how much of the allowance is used this period, and when it refills.

        Returns:
            The balance.
        """
        # Reading the balance may grant a refill that is due, which is harmless to
        # repeat.
        return await self._client._request("GET", "user/usage/balance", UsageBalance)

    async def history(
        self,
        *,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> AsyncIterator[UsageEntry]:
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
            response = await self._client._request(
                "GET", "user/usage/history", Response, params=params
            )
            for entry in decode_response(response, list[UsageEntry]):
                yield entry
            cursor = response.headers.get(_NEXT_CURSOR_HEADER)
            if cursor is None:
                return
            params["cursor"] = cursor
