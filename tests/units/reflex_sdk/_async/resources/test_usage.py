from __future__ import annotations

import datetime
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import pytest
from reflex_sdk import AsyncReflexCloud
from reflex_sdk.transports import Request, Response
from reflex_sdk.types import UsageBalance, UsageEntry

from tests.units.reflex_sdk.conftest import AsyncMockTransport, MockAPI, reply

UTC = datetime.timezone.utc


@pytest.fixture
async def client(mock_api: MockAPI) -> AsyncIterator[AsyncReflexCloud]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    async with AsyncReflexCloud(
        token="test-token", transport=AsyncMockTransport(mock_api)
    ) as client:
        yield client


async def test_balance(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        "/api/v1/user/usage/balance",
        reply(
            200,
            json={
                "has_allowance": True,
                "used_pct": "37.50",
                "remaining_pct": "62.50",
                "refresh_eligible": True,
                "next_refresh_at": "2026-09-16T18:00:00+00:00",
                "next_refresh_pct": "100.00",
            },
        ),
    )
    assert await client.usage.balance() == UsageBalance(
        has_allowance=True,
        used_pct="37.50",
        remaining_pct="62.50",
        refresh_eligible=True,
        next_refresh_at=datetime.datetime(2026, 9, 16, 18, tzinfo=UTC),
        next_refresh_pct="100.00",
    )


def _entry(kind: str) -> dict:
    return {
        "timestamp": "2026-09-15T13:00:00+00:00",
        "amount_pct": "-0.0125",
        "kind": kind,
        "description": None,
    }


async def test_history_follows_the_cursor_header(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    cursor = "2026-08-16T00:00:00+00:00|2026-09-15T13:00:00+00:00|6f1c"

    def first_page(request: Request) -> Response:
        return reply(
            200, json=[_entry("compute_debit")], headers={"x-next-cursor": cursor}
        )(request)

    mock_api.add(
        "GET",
        "/api/v1/user/usage/history",
        first_page,
        reply(200, json=[_entry("task_debit")]),
    )
    entries = [
        entry
        async for entry in client.usage.history(
            start=datetime.date(2026, 8, 16),
            end=datetime.datetime(2026, 9, 16, 12, tzinfo=UTC),
        )
    ]
    assert entries == [
        UsageEntry(
            timestamp=datetime.datetime(2026, 9, 15, 13, tzinfo=UTC),
            amount_pct="-0.0125",
            kind=kind,
            description=None,
        )
        for kind in ("compute_debit", "task_debit")
    ]
    first, second = (parse_qs(urlsplit(r.url).query) for r in mock_api.requests)
    assert first == {
        "start_date": ["2026-08-16"],
        "end_date": ["2026-09-16T12:00:00+00:00"],
    }
    assert second == {**first, "cursor": [cursor]}
    # The cursor's "+" and "|" are encoded; an unencoded "+" would read as a space.
    assert "%2B" in mock_api.requests[1].url
    assert "%7C" in mock_api.requests[1].url


async def test_history_rejects_naive_datetimes(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    with pytest.raises(ValueError, match="timezone-aware"):
        async for _ in client.usage.history(start=datetime.datetime(2026, 9, 1)):
            pass
    assert not mock_api.requests
