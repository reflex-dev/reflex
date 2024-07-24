"""This module contains utility functions for checking if the current IP address is in China."""

from typing import Union

import requests


def _is_in_china() -> Union[bool, None]:
    """Check if the current IP address is in China.

    Returns:
        bool: True if the IP address is in China, False otherwise.
        None: If an error occurred.
    """
    try:
        response = requests.get(f"http://ip-api.com/json")
        data = response.json()

        if data["status"] == "success":
            return data["country"] == "China"
        else:
            print(f"Error: {data['message']}")
            return None

    except requests.RequestException as e:
        print(f"Request error: {e}")
        return None
