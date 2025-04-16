"""Helper utilities for integration tests."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

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

    AppHarness._poll_for(lambda: prev_url != driver.current_url, timeout=timeout)


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
