"""Shared helpers for integration tests."""

from __future__ import annotations

from collections import Counter
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from http.client import HTTPConnection
from urllib.parse import urlsplit

from playwright.sync_api import Page, expect


def request_raw(
    url: str,
    path: str,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Send a raw HTTP request without client-side decompression.

    Args:
        url: The base URL to connect to.
        path: The request path.
        headers: Optional request headers.

    Returns:
        The status code, response headers, and raw body.
    """
    parsed = urlsplit(url)
    assert parsed.hostname is not None
    assert parsed.port is not None
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=10)
    conn.request("GET", path, headers=headers or {})
    response = conn.getresponse()
    body = response.read()
    response_headers = {key.lower(): value for key, value in response.getheaders()}
    status = response.status
    conn.close()
    return status, response_headers, body


@contextmanager
def poll_for_navigation(page: Page, timeout: int = 5) -> Generator[None, None, None]:
    """Wait for a client-side or document navigation to change the URL.

    Args:
        page: Playwright page whose URL should change.
        timeout: Maximum wait in seconds.

    Returns:
        Iterator yielding control to the action that triggers navigation.
    """
    previous_url = page.url
    yield
    page.wait_for_url(
        lambda url: str(url) != previous_url,
        wait_until="commit",
        timeout=timeout * 1000,
    )


def click_element(page: Page, selector: str, timeout: float | None = None) -> None:
    """Click a locator using Playwright's auto-waiting behavior.

    Args:
        page: Playwright page containing the target.
        selector: CSS selector for the target element.
        timeout: Optional maximum wait in seconds.

    Returns:
        None.
    """
    page.locator(selector).click(
        timeout=timeout * 1000 if timeout is not None else None
    )


def n_expected_events(exp_event_order: Sequence[str | set[str]]) -> int:
    """Count expected event names, including unordered event groups.

    Returns:
        Total number of events.
    """
    return sum(
        len(events) if isinstance(events, set) else 1 for events in exp_event_order
    )


def assert_event_order(
    actual_event_order: list[str], exp_event_order: Sequence[str | set[str]]
) -> None:
    """Verify exact event order while allowing explicitly unordered groups."""
    actual_idx = 0
    for expected in exp_event_order:
        if isinstance(expected, str):
            assert actual_event_order[actual_idx] == expected, (
                f"Expected event {expected!r} at position {actual_idx}, "
                f"got {actual_event_order[actual_idx]!r}."
            )
            actual_idx += 1
        else:
            expected_events = set(expected)
            actual_events = set(
                actual_event_order[actual_idx : actual_idx + len(expected_events)]
            )
            assert actual_events == expected_events, (
                f"Expected events {expected_events} at position {actual_idx}, "
                f"got {actual_events}."
            )
            actual_idx += len(expected_events)
    assert actual_idx == len(actual_event_order), (
        f"Expected {actual_idx} events, got {len(actual_event_order)}: "
        f"{actual_event_order[actual_idx:]} remain."
    )


def poll_assert_event_order(
    page: Page,
    exp_event_order: Sequence[str | set[str]],
    selector: str = "#event_order > p",
) -> None:
    """Wait for and verify the exact sequence rendered by the app.

    Args:
        page: Playwright page containing the event list.
        exp_event_order: Expected sequence; set entries may be unordered groups.
        selector: Locator for event entries.
    """
    events = page.locator(selector)
    expect(events).to_have_count(n_expected_events(exp_event_order))
    assert_event_order(events.all_text_contents(), exp_event_order)


OrderingRule = tuple[tuple[str, int], tuple[str, int]]


def assert_relative_event_order(
    actual: list[str],
    expected_counts: dict[str, int],
    ordering_rules: list[OrderingRule],
) -> None:
    """Assert event counts and selected relative ordering constraints."""
    actual_counts = Counter(actual)
    for event, count in expected_counts.items():
        assert actual_counts[event] == count, (
            f"Expected {count} occurrences of {event!r}, got {actual_counts[event]}. "
            f"Actual: {actual}"
        )
    assert sum(expected_counts.values()) == len(actual), (
        f"Expected {sum(expected_counts.values())} total events, got {len(actual)}. "
        f"Actual: {actual}"
    )

    occurrence_indices: dict[tuple[str, int], int] = {}
    event_counters: dict[str, int] = {}
    for index, event in enumerate(actual):
        occurrence = event_counters.get(event, 0)
        occurrence_indices[event, occurrence] = index
        event_counters[event] = occurrence + 1

    for (event_a, occurrence_a), (event_b, occurrence_b) in ordering_rules:
        index_a = occurrence_indices[event_a, occurrence_a]
        index_b = occurrence_indices[event_b, occurrence_b]
        assert index_a < index_b, (
            f"Expected {event_a!r}[{occurrence_a}] (pos {index_a}) before "
            f"{event_b!r}[{occurrence_b}] (pos {index_b}). Actual: {actual}"
        )


def poll_assert_relative_event_order(
    page: Page,
    expected_counts: dict[str, int],
    ordering_rules: list[OrderingRule],
    selector: str = "#event_order > p",
) -> None:
    """Wait for expected events, then assert relative ordering constraints.

    Args:
        page: Playwright page containing the event list.
        expected_counts: Expected occurrence count per event.
        ordering_rules: Required relative order for event occurrences.
        selector: Locator for event entries.
    """
    events = page.locator(selector)
    expect(events).to_have_count(sum(expected_counts.values()))
    assert_relative_event_order(
        events.all_text_contents(), expected_counts, ordering_rules
    )
