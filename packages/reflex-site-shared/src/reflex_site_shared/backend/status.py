"""Checkly-backed service status state and polling utilities."""

import asyncio
import contextlib
from enum import StrEnum

import httpx

import reflex as rx
from reflex_site_shared.constants import (
    CHECKLY_ACCOUNT_ID,
    CHECKLY_API_BASE_URL,
    CHECKLY_API_KEY,
    CHECKLY_CHECK_GROUP_ID,
)


class ServiceStatus(StrEnum):
    """Supported service health states exposed in the UI."""

    SUCCESS = "Success"
    WARNING = "Warning"
    CRITICAL = "Critical"


CURRENT_STATUS = ServiceStatus.SUCCESS.value


# Check status of each check in parallel
async def check_status(check_id: str) -> dict:
    """Fetch status flags for a single Checkly check.

    Returns:
        A dictionary with failure and degraded flags.
    """
    status_url = f"{CHECKLY_API_BASE_URL}/check-statuses/{check_id}"
    async with httpx.AsyncClient() as client:
        status_response = await client.get(
            status_url,
            headers={
                "Authorization": f"Bearer {CHECKLY_API_KEY}",
                "X-Checkly-Account": CHECKLY_ACCOUNT_ID,
            },
        )
    if status_response.status_code == 200:
        status_data = status_response.json()
        return {
            "has_failures": status_data.get("hasFailures", False),
            "is_degraded": status_data.get("isDegraded", False),
        }

    return {"has_failures": False, "is_degraded": False}


async def monitor_checkly_status() -> None:
    """Continuously monitor Checkly check group status.

    Updates the global STATUS variable every 60 seconds.
    - Critical: if any check has failures
    - Warning: if no failures but some checks are degraded
    - Success: all checks are healthy

    """
    if not all((CHECKLY_API_KEY, CHECKLY_ACCOUNT_ID, CHECKLY_CHECK_GROUP_ID)):
        return

    headers = {
        "Authorization": f"Bearer {CHECKLY_API_KEY}",
        "X-Checkly-Account": CHECKLY_ACCOUNT_ID,
    }

    try:
        while True:
            with contextlib.suppress(Exception):
                global CURRENT_STATUS

                # Get checks in this group
                checks_url = f"{CHECKLY_API_BASE_URL}/check-groups/{CHECKLY_CHECK_GROUP_ID}/checks"
                async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
                    checks_response = await client.get(checks_url, headers=headers)
                if checks_response.status_code == 200:
                    checks = checks_response.json()

                    check_ids = [check.get("id") for check in checks if check.get("id")]
                    results = await asyncio.gather(*[
                        check_status(check_id) for check_id in check_ids
                    ])

                    # Determine overall status
                    has_any_failures = any(r["has_failures"] for r in results)
                    has_any_degraded = any(r["is_degraded"] for r in results)

                    if has_any_failures:
                        CURRENT_STATUS = ServiceStatus.CRITICAL.value
                    elif has_any_degraded:
                        CURRENT_STATUS = ServiceStatus.WARNING.value
                    else:
                        CURRENT_STATUS = ServiceStatus.SUCCESS.value

            await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass


class StatusState(rx.State):
    """Reflex state that exposes the current service status."""

    @rx.var(interval=60)
    def status(self) -> str:
        """Return the current status value for the status pill."""
        return CURRENT_STATUS
