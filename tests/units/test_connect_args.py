"""Test connecting to the database with custom arguments."""
from unittest import mock

from reflex.model import get_engine_args


def test_get_engine_args_connect_args():
    """Test that connect_args are correctly retrieved from config."""
    with mock.patch("reflex.model.get_config") as mock_get_config:
        # Case 1: Postgres with connect_args
        mock_conf = mock.Mock()
        mock_conf.db_url = "postgresql://user:pass@localhost/db"
        mock_conf.connect_args = {"application_name": "test_app"}
        mock_get_config.return_value = mock_conf

        args = get_engine_args()
        assert "connect_args" in args
        assert args["connect_args"]["application_name"] == "test_app"

        # Case 2: Sqlite with connect_args
        mock_conf.db_url = "sqlite:///test.db"
        mock_conf.connect_args = {"timeout": 10}

        args = get_engine_args()
        assert "connect_args" in args
        assert args["connect_args"]["timeout"] == 10
        # Ensure sqlite specific check_same_thread is set
        assert args["connect_args"]["check_same_thread"] is False

        # Case 3: Sqlite without connect_args
        mock_conf.connect_args = {}
        args = get_engine_args()
        assert "connect_args" in args
        assert args["connect_args"]["check_same_thread"] is False
