"""Helper utilities for integration tests."""

from __future__ import annotations

from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from reflex.testing import AppHarness


@contextmanager
def poll_for_navigation(
    driver: WebDriver, timeout: int = 5
) -> Generator[None, None, None]:
    """Wait for driver url to change.

    Use as a contextmanager, and apply the navigation event inside the context
    block, polling will occur after the context block exits.

    Args:
        driver: WebDriver instance.
        timeout: Time to wait for url to change.

    Yields:
        None
    """
    prev_url = driver.current_url

    yield

    AppHarness.expect(lambda: prev_url != driver.current_url, timeout=timeout)


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
    driver: WebDriver,
    exp_event_order: Sequence[str | set[str]],
    xpath: str = '//*[@id="event_order"]/p',
) -> None:
    """Poll until the actual event order matches the expected event order, accounting for sets in the expected order.

    Args:
        driver: WebDriver instance.
        exp_event_order: the expected events recorded in the State, where some entries may be sets of events that can occur in any order.
        xpath: The XPath to the event order elements.

    Raises:
        AssertionError: if the actual event order does not match the expected event order after polling.
    """
    n_exp_events = n_expected_events(exp_event_order)

    def _has_number_of_expected_events():
        event_elements = driver.find_elements(By.XPATH, xpath)
        return len(event_elements) == n_exp_events

    AppHarness._poll_for(_has_number_of_expected_events)

    event_elements = driver.find_elements(By.XPATH, xpath)
    assert_event_order([elem.text for elem in event_elements], exp_event_order)


# Type alias for an ordering rule: ((event_a, occurrence_a), (event_b, occurrence_b)).
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

    # Build occurrence index: (event, occ) -> position in actual list
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
    driver: WebDriver,
    expected_counts: dict[str, int],
    ordering_rules: list[OrderingRule],
    xpath: str = '//*[@id="event_order"]/p',
) -> None:
    """Poll until the expected number of events appear, then assert relative ordering.

    Args:
        driver: WebDriver instance.
        expected_counts: mapping of event name to expected occurrence count.
        ordering_rules: ordering constraints (see assert_relative_event_order).
        xpath: The XPath to the event order elements.
    """
    n_exp = sum(expected_counts.values())

    def _has_number_of_expected_events():
        return len(driver.find_elements(By.XPATH, xpath)) == n_exp

    AppHarness._poll_for(_has_number_of_expected_events)

    event_elements = driver.find_elements(By.XPATH, xpath)
    assert_relative_event_order(
        [elem.text for elem in event_elements], expected_counts, ordering_rules
    )


class LocalStorage:
    """Class to access local storage.

    https://stackoverflow.com/a/46361900
    """

    storage_key = "localStorage"

    def __init__(self, driver: WebDriver):
        """Initialize the class.

        Args:
            driver: WebDriver instance.
        """
        self.driver = driver

    def __len__(self) -> int:
        """Get the number of items in local storage.

        Returns:
            The number of items in local storage.
        """
        return int(
            self.driver.execute_script(f"return window.{self.storage_key}.length;")
        )

    def items(self) -> dict[str, str]:
        """Get all items in local storage.

        Returns:
            A dict mapping keys to values.
        """
        return self.driver.execute_script(
            f"var ls = window.{self.storage_key}, items = {{}}; "
            "for (var i = 0, k; i < ls.length; ++i) "
            "  items[k = ls.key(i)] = ls.getItem(k); "
            "return items; "
        )

    def keys(self) -> list[str]:
        """Get all keys in local storage.

        Returns:
            A list of keys.
        """
        return self.driver.execute_script(
            f"var ls = window.{self.storage_key}, keys = []; "
            "for (var i = 0; i < ls.length; ++i) "
            "  keys[i] = ls.key(i); "
            "return keys; "
        )

    def get(self, key) -> str:
        """Get a key from local storage.

        Args:
            key: The key to get.

        Returns:
            The value of the key.
        """
        return self.driver.execute_script(
            f"return window.{self.storage_key}.getItem(arguments[0]);", key
        )

    def set(self, key, value) -> None:
        """Set a key in local storage.

        Args:
            key: The key to set.
            value: The value to set the key to.
        """
        self.driver.execute_script(
            f"window.{self.storage_key}.setItem(arguments[0], arguments[1]);",
            key,
            value,
        )

    def has(self, key) -> bool:
        """Check if key is in local storage.

        Args:
            key: The key to check.

        Returns:
            True if key is in local storage, False otherwise.
        """
        return key in self

    def remove(self, key) -> None:
        """Remove a key from local storage.

        Args:
            key: The key to remove.
        """
        self.driver.execute_script(
            f"window.{self.storage_key}.removeItem(arguments[0]);", key
        )

    def clear(self) -> None:
        """Clear all local storage."""
        self.driver.execute_script(f"window.{self.storage_key}.clear();")

    def __getitem__(self, key) -> str:
        """Get a key from local storage.

        Args:
            key: The key to get.

        Returns:
            The value of the key.

        Raises:
            KeyError: If key is not in local storage.
        """
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key, value) -> None:
        """Set a key in local storage.

        Args:
            key: The key to set.
            value: The value to set the key to.
        """
        self.set(key, value)

    def __contains__(self, key) -> bool:
        """Check if key is in local storage.

        Args:
            key: The key to check.

        Returns:
            True if key is in local storage, False otherwise.
        """
        return self.has(key)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the keys in local storage.

        Returns:
            An iterator over the items in local storage.
        """
        return iter(self.keys())


class SessionStorage(LocalStorage):
    """Class to access session storage.

    https://stackoverflow.com/a/46361900
    """

    storage_key = "sessionStorage"
