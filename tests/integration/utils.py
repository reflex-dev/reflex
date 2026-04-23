"""Helper utilities for integration tests."""

from __future__ import annotations

from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager

from playwright.sync_api import Page

from reflex.testing import AppHarness, TimeoutType


def poll_for_token(page: Page, timeout: TimeoutType = None) -> str:
    """Wait for the backend connection to send the token and return it.

    Args:
        page: Playwright page showing a hydrated app page with a ``#token`` input.
        timeout: Optional timeout (seconds) to wait for the token to appear.

    Returns:
        The client token as displayed in the ``#token`` input.
    """
    token_input = page.locator("#token")

    def _get_token() -> str | None:
        value = token_input.input_value()
        return value or None

    token = AppHarness.poll_for_or_raise_timeout(_get_token, timeout=timeout)
    assert token is not None
    return token


@contextmanager
def poll_for_navigation(
    page: Page, timeout: float = 5.0
) -> Generator[None, None, None]:
    """Wait for the page URL to change after an action inside the ``with`` block.

    Args:
        page: Playwright page to observe.
        timeout: Time (seconds) to wait for the URL to change.

    Yields:
        None
    """
    prev_url = page.url
    yield
    AppHarness.expect(lambda: prev_url != page.url, timeout=timeout)


def n_expected_events(exp_event_order: Sequence[str | set[str]]) -> int:
    """Calculate the number of expected events, accounting for sets in the expected order.

    Args:
        exp_event_order: the expected events recorded in the State, where some entries may be sets of events that can occur in any order.

    Returns:
        The total number of expected events.
    """
    return sum(
        len(events) if isinstance(events, set) else 1 for events in exp_event_order
    )


def assert_event_order(
    actual_event_order: list[str], exp_event_order: Sequence[str | set[str]]
) -> None:
    """Verify that the actual event order matches the expected event order, accounting for sets in the expected order.

    Args:
        actual_event_order: the actual events recorded in the State.
        exp_event_order: the expected events recorded in the State, where some entries may be sets of events that can occur in any order.

    Raises:
        AssertionError: if the actual event order does not match the expected event order.
    """
    actual_idx = 0
    for expected in exp_event_order:
        if isinstance(expected, str):
            assert actual_event_order[actual_idx] == expected, (
                f"Expected event '{expected}' at position {actual_idx}, but got '{actual_event_order[actual_idx]}'."
            )
            actual_idx += 1
        else:  # expected is a set of events that can occur in any order
            expected_events = set(expected)
            actual_events = set(
                actual_event_order[actual_idx : actual_idx + len(expected_events)]
            )
            assert actual_events == expected_events, (
                f"Expected events {expected_events} at positions {actual_idx} to {actual_idx + len(expected_events) - 1}, but got {actual_events}."
            )
            actual_idx += len(expected_events)
    assert actual_idx == len(actual_event_order), (
        f"Expected {actual_idx} events, but got {len(actual_event_order)}: {actual_event_order[actual_idx:]} remain."
    )


def poll_assert_event_order(
    page: Page,
    exp_event_order: Sequence[str | set[str]],
    selector: str = '//*[@id="event_order"]/p',
) -> None:
    """Poll until the actual event order matches the expected event order, accounting for sets in the expected order.

    Args:
        page: Playwright page to query.
        exp_event_order: the expected events recorded in the State, where some entries may be sets of events that can occur in any order.
        selector: CSS or XPath selector for the event-order elements.

    Raises:
        AssertionError: if the actual event order does not match the expected event order after polling.
    """
    n_exp_events = n_expected_events(exp_event_order)
    locator = page.locator(selector)

    AppHarness._poll_for(lambda: locator.count() == n_exp_events)

    actual = [item.text_content() or "" for item in locator.all()]
    assert_event_order(actual, exp_event_order)


OrderingRule = tuple[tuple[str, int], tuple[str, int]]


def assert_relative_event_order(
    actual: list[str],
    expected_counts: dict[str, int],
    ordering_rules: list[OrderingRule],
) -> None:
    """Assert that events satisfy relative ordering constraints.

    Instead of requiring an exact event sequence, this checks that:
    1. Each event appears the expected number of times.
    2. Specific occurrences of events appear before other specific occurrences.

    Args:
        actual: the actual events recorded.
        expected_counts: mapping of event name to expected occurrence count.
        ordering_rules: list of ((event_a, occ_a), (event_b, occ_b)) meaning
            the occ_a-th occurrence (0-indexed) of event_a must appear before
            the occ_b-th occurrence (0-indexed) of event_b in the actual list.

    Raises:
        AssertionError: if any constraint is violated.
    """
    from collections import Counter

    actual_counts = Counter(actual)
    for event, count in expected_counts.items():
        assert actual_counts[event] == count, (
            f"Expected {count} occurrences of '{event}', got {actual_counts[event]}. Actual: {actual}"
        )
    assert sum(expected_counts.values()) == len(actual), (
        f"Expected {sum(expected_counts.values())} total events, got {len(actual)}. Actual: {actual}"
    )

    occurrence_indices: dict[tuple[str, int], int] = {}
    event_counters: dict[str, int] = {}
    for i, event in enumerate(actual):
        occ = event_counters.get(event, 0)
        occurrence_indices[event, occ] = i
        event_counters[event] = occ + 1

    for (event_a, occ_a), (event_b, occ_b) in ordering_rules:
        idx_a = occurrence_indices[event_a, occ_a]
        idx_b = occurrence_indices[event_b, occ_b]
        assert idx_a < idx_b, (
            f"Expected '{event_a}'[{occ_a}] (pos {idx_a}) before "
            f"'{event_b}'[{occ_b}] (pos {idx_b}). Actual: {actual}"
        )


def poll_assert_relative_event_order(
    page: Page,
    expected_counts: dict[str, int],
    ordering_rules: list[OrderingRule],
    selector: str = '//*[@id="event_order"]/p',
) -> None:
    """Poll until the expected number of events appear, then assert relative ordering.

    Args:
        page: Playwright page to query.
        expected_counts: mapping of event name to expected occurrence count.
        ordering_rules: ordering constraints (see assert_relative_event_order).
        selector: CSS or XPath selector for the event-order elements.
    """
    n_exp = sum(expected_counts.values())
    locator = page.locator(selector)

    AppHarness._poll_for(lambda: locator.count() == n_exp)

    actual = [item.text_content() or "" for item in locator.all()]
    assert_relative_event_order(actual, expected_counts, ordering_rules)


class LocalStorage:
    """Helper for interacting with ``window.localStorage`` via a Playwright page.

    https://stackoverflow.com/a/46361900
    """

    storage_key = "localStorage"

    def __init__(self, page: Page):
        """Initialize the class.

        Args:
            page: Playwright page bound to the app.
        """
        self.page = page

    def __len__(self) -> int:
        """Get the number of items in the storage.

        Returns:
            The number of items in the storage.
        """
        return int(self.page.evaluate(f"window.{self.storage_key}.length"))

    def items(self) -> dict[str, str]:
        """Get all items in the storage.

        Returns:
            A dict mapping keys to values.
        """
        return self.page.evaluate(
            f"() => {{"
            f"  const ls = window.{self.storage_key};"
            f"  const items = {{}};"
            f"  for (let i = 0; i < ls.length; ++i) {{"
            f"    const k = ls.key(i);"
            f"    items[k] = ls.getItem(k);"
            f"  }}"
            f"  return items;"
            f"}}"
        )

    def keys(self) -> list[str]:
        """Get all keys in the storage.

        Returns:
            A list of keys.
        """
        return self.page.evaluate(
            f"() => {{"
            f"  const ls = window.{self.storage_key};"
            f"  const keys = [];"
            f"  for (let i = 0; i < ls.length; ++i) keys.push(ls.key(i));"
            f"  return keys;"
            f"}}"
        )

    def get(self, key: str) -> str | None:
        """Get a key from the storage.

        Args:
            key: The key to get.

        Returns:
            The value of the key, or None if not present.
        """
        return self.page.evaluate(f"(k) => window.{self.storage_key}.getItem(k)", key)

    def set(self, key: str, value: str) -> None:
        """Set a key in the storage.

        Args:
            key: The key to set.
            value: The value to set the key to.
        """
        self.page.evaluate(
            f"([k, v]) => window.{self.storage_key}.setItem(k, v)", [key, value]
        )

    def has(self, key: str) -> bool:
        """Check if ``key`` is in the storage.

        Args:
            key: The key to check.

        Returns:
            True if ``key`` is in the storage, False otherwise.
        """
        return self.get(key) is not None

    def remove(self, key: str) -> None:
        """Remove a key from the storage.

        Args:
            key: The key to remove.
        """
        self.page.evaluate(f"(k) => window.{self.storage_key}.removeItem(k)", key)

    def clear(self) -> None:
        """Clear all items in the storage."""
        self.page.evaluate(f"() => window.{self.storage_key}.clear()")

    def __getitem__(self, key: str) -> str:
        """Get a key from the storage.

        Args:
            key: The key to get.

        Returns:
            The value of the key.

        Raises:
            KeyError: If ``key`` is not in the storage.
        """
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: str) -> None:
        """Set a key in the storage.

        Args:
            key: The key to set.
            value: The value to set the key to.
        """
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """Check if ``key`` is in the storage.

        Args:
            key: The key to check.

        Returns:
            True if ``key`` is in the storage, False otherwise.
        """
        return self.has(key)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the keys in the storage.

        Returns:
            An iterator over the keys in the storage.
        """
        return iter(self.keys())


class SessionStorage(LocalStorage):
    """Helper for interacting with ``window.sessionStorage`` via a Playwright page.

    https://stackoverflow.com/a/46361900
    """

    storage_key = "sessionStorage"
