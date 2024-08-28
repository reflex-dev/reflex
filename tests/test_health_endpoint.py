from unittest.mock import MagicMock, Mock

import pytest
import sqlalchemy
from redis.exceptions import RedisError

from reflex.model import get_db_status
from reflex.utils.prerequisites import get_redis_status


@pytest.mark.parametrize(
    "mock_redis_client, expected_status",
    [
        # Case 1: Redis client is available and responds to ping
        (Mock(ping=lambda: None), True),
        # Case 2: Redis client raises RedisError
        (Mock(ping=lambda: (_ for _ in ()).throw(RedisError)), False),
        # Case 3: Redis client is not used
        (None, None),
    ],
)
def test_get_redis_status(mock_redis_client, expected_status, mocker):
    # Mock the `get_redis_sync` function to return the mock Redis client
    mock_get_redis_sync = mocker.patch(
        "reflex.utils.prerequisites.get_redis_sync", return_value=mock_redis_client
    )

    # Call the function
    status = get_redis_status()

    # Verify the result
    assert status == expected_status
    mock_get_redis_sync.assert_called_once()


@pytest.mark.parametrize(
    "mock_engine, execute_side_effect, expected_status",
    [
        # Case 1: Database is accessible
        (MagicMock(), None, True),
        # Case 2: Database connection error (OperationalError)
        (
            MagicMock(),
            sqlalchemy.exc.OperationalError("error", "error", "error"),
            False,
        ),
    ],
)
def test_get_db_status(mock_engine, execute_side_effect, expected_status, mocker):
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
    status = get_db_status()

    # Verify the result
    assert status == expected_status

    if mock_engine:
        mock_get_engine.assert_called_once()
    else:
        mock_get_engine.assert_called_once()
