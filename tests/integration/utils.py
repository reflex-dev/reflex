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
