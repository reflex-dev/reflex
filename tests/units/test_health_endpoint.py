import json
from unittest.mock import MagicMock, Mock

import pytest
import sqlalchemy.exc
from pytest_mock import MockerFixture
from redis.exceptions import RedisError

from reflex.app import health
from reflex.model import get_db_status
from reflex.utils.prerequisites import get_redis_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mock_redis_client", "expected_status"),
    [
        # Case 1: Redis client is available and responds to ping
        (Mock(ping=lambda: None), {"redis": True}),
        # Case 2: Redis client raises RedisError
        (Mock(ping=lambda: (_ for _ in ()).throw(RedisError)), {"redis": False}),
        # Case 3: Redis client is not used
        (None, {"redis": None}),
    ],
)
async def test_get_redis_status(
    mock_redis_client, expected_status, mocker: MockerFixture
):
    # Mock the `get_redis_sync` function to return the mock Redis client
    mock_get_redis_sync = mocker.patch(
        "reflex.utils.prerequisites.get_redis_sync", return_value=mock_redis_client
    )

    # Call the function
    status = await get_redis_status()

    # Verify the result
    assert status == expected_status
    mock_get_redis_sync.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mock_engine", "execute_side_effect", "expected_status"),
    [
        # Case 1: Database is accessible
        (MagicMock(), None, {"db": True}),
        # Case 2: Database connection error (OperationalError)
        (
            MagicMock(),
            sqlalchemy.exc.OperationalError("error", "error", "error"),  # pyright: ignore[reportArgumentType]
            {"db": False},
        ),
    ],
)
async def test_get_db_status(
    mock_engine, execute_side_effect, expected_status, mocker: MockerFixture
):
    # Mock get_engine to return the mock_engine
    mock_get_engine = mocker.patch("reflex.model.get_engine", return_value=mock_engine)

    # Mock the connection and its execute method
    if mock_engine:
        mock_connection = mock_engine.connect.return_value.__enter__.return_value
        if execute_side_effect:
            # Simulate execute method raising an exception
            mock_connection.execute.side_effect = execute_side_effect
        else:
            # Simulate successful execute call
            mock_connection.execute.return_value = None

    # Call the function
    status = await get_db_status()

    # Verify the result
    assert status == expected_status
    mock_get_engine.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "db_enabled",
        "redis_enabled",
        "db_status",
        "redis_status",
        "expected_status",
        "expected_code",
    ),
    [
        # Case 1: Both services are connected
        (True, True, True, True, {"status": True, "db": True, "redis": True}, 200),
        # Case 2: Database not connected, Redis connected
        (True, True, False, True, {"status": False, "db": False, "redis": True}, 503),
        # Case 3: Database connected, Redis not connected
        (True, True, True, False, {"status": False, "db": True, "redis": False}, 503),
        # Case 4: Both services not connected
        (True, True, False, False, {"status": False, "db": False, "redis": False}, 503),
        # Case 5: Database Connected, Redis not used
        (True, False, True, None, {"status": True, "db": True}, 200),
        # Case 6: Database not used, Redis Connected
        (False, True, None, True, {"status": True, "redis": True}, 200),
        # Case 7: Both services not used
        (False, False, None, None, {"status": True}, 200),
    ],
)
async def test_health(
    db_enabled,
    redis_enabled,
    db_status,
    redis_status,
    expected_status,
    expected_code,
    mocker: MockerFixture,
):
    # Mock get_db_status and get_redis_status
    mocker.patch(
        "reflex.utils.prerequisites.check_db_used",
        return_value=db_enabled,
    )
    mocker.patch(
        "reflex.utils.prerequisites.check_redis_used",
        return_value=redis_enabled,
    )
    mocker.patch(
        "reflex.app.get_db_status",
        return_value={"db": db_status},
    )
    mocker.patch(
        "reflex.utils.prerequisites.get_redis_status",
        return_value={"redis": redis_status},
    )

    request = Mock()

    # Call the async health function
    response = await health(request)

    # Verify the response content and status code
    assert response.status_code == expected_code
    assert isinstance(response.body, bytes)
    assert json.loads(response.body) == expected_status
