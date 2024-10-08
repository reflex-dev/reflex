import urllib.parse

import pytest

from reflex.config import DBConfig


@pytest.mark.parametrize(
    "engine,username,password,host,port,database,expected_url",
    [
        (
            "postgresql",
            "user",
            "pass",
            "localhost",
            5432,
            "db",
            "postgresql://user:pass@localhost:5432/db",
        ),
        (
            "postgresql",
            "user",
            "pass",
            "localhost",
            None,
            "db",
            "postgresql://user:pass@localhost/db",
        ),
        (
            "postgresql",
            "user",
            None,
            "localhost",
            None,
            "db",
            "postgresql://user@localhost/db",
        ),
        ("postgresql", "user", None, None, None, "db", "postgresql://user@/db"),
        ("postgresql", "user", None, None, 5432, "db", "postgresql://user@/db"),
        (
            "postgresql",
            None,
            None,
            "localhost",
            5432,
            "db",
            "postgresql://localhost:5432/db",
        ),
        ("sqlite", None, None, None, None, "db.sqlite", "sqlite:///db.sqlite"),
    ],
)
def test_get_url(engine, username, password, host, port, database, expected_url):
    """Test generation of URL.

    Args:
        engine: Database engine.
        username: Database username.
        password: Database password.
        host: Database host.
        port: Database port.
        database: Database name.
        expected_url: Expected database URL generated.
    """
    db_config = DBConfig(
        engine=engine,
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    )
    assert db_config.get_url() == expected_url


def test_url_encode():
    """Test username and password are urlencoded when database URL is generated."""
    username = "user@user"
    password = "pass@pass"
    database = "db"
    username_encoded = urllib.parse.quote_plus(username)
    password_encoded = urllib.parse.quote_plus(password)
    engine = "postgresql"

    db_config = DBConfig(
        engine=engine, username=username, password=password, database=database
    )
    assert (
        db_config.get_url()
        == f"{engine}://{username_encoded}:{password_encoded}@/{database}"
    )


def test_url_encode_database_name():
    """Test database name is not URL encoded."""
    username = "user"
    password = "pass"
    database = "db@prod"
    engine = "postgresql"

    db_config = DBConfig(
        engine=engine, username=username, password=password, database=database
    )
    assert db_config.get_url() == f"{engine}://{username}:{password}@/{database}"


def test_constructor_sqlite():
    """Test DBConfig.sqlite constructor create the instance correctly."""
    db_config = DBConfig.sqlite(database="app.db")
    assert db_config.engine == "sqlite"
    assert db_config.username == ""
    assert db_config.password == ""
    assert db_config.host == ""
    assert db_config.port is None
    assert db_config.database == "app.db"
    assert db_config.get_url() == "sqlite:///app.db"


@pytest.mark.parametrize(
    "username,password,host,port,database,expected_url",
    [
        (
            "user",
            "pass",
            "localhost",
            5432,
            "db",
            "postgresql://user:pass@localhost:5432/db",
        ),
        ("user", "", "localhost", None, "db", "postgresql://user@localhost/db"),
        ("user", "", "", None, "db", "postgresql://user@/db"),
        ("", "", "localhost", 5432, "db", "postgresql://localhost:5432/db"),
        ("", "", "", None, "db", "postgresql:///db"),
    ],
)
def test_constructor_postgresql(username, password, host, port, database, expected_url):
    """Test DBConfig.postgresql constructor creates the instance correctly.

    Args:
        username: Database username.
        password: Database password.
        host: Database host.
        port: Database port.
        database: Database name.
        expected_url: Expected database URL generated.
    """
    db_config = DBConfig.postgresql(
        username=username, password=password, host=host, port=port, database=database
    )
    assert db_config.engine == "postgresql"
    assert db_config.username == username
    assert db_config.password == password
    assert db_config.host == host
    assert db_config.port == port
    assert db_config.database == database
    assert db_config.get_url() == expected_url


@pytest.mark.parametrize(
    "username,password,host,port,database,expected_url",
    [
        (
            "user",
            "pass",
            "localhost",
            5432,
            "db",
            "postgresql+psycopg2://user:pass@localhost:5432/db",
        ),
        (
            "user",
            "",
            "localhost",
            None,
            "db",
            "postgresql+psycopg2://user@localhost/db",
        ),
        ("user", "", "", None, "db", "postgresql+psycopg2://user@/db"),
        ("", "", "localhost", 5432, "db", "postgresql+psycopg2://localhost:5432/db"),
        ("", "", "", None, "db", "postgresql+psycopg2:///db"),
    ],
)
def test_constructor_postgresql_psycopg2(
    username, password, host, port, database, expected_url
):
    """Test DBConfig.postgresql_psycopg2 constructor creates the instance correctly.

    Args:
        username: Database username.
        password: Database password.
        host: Database host.
        port: Database port.
        database: Database name.
        expected_url: Expected database URL generated.
    """
    db_config = DBConfig.postgresql_psycopg2(
        username=username, password=password, host=host, port=port, database=database
    )
    assert db_config.engine == "postgresql+psycopg2"
    assert db_config.username == username
    assert db_config.password == password
    assert db_config.host == host
    assert db_config.port == port
    assert db_config.database == database
    assert db_config.get_url() == expected_url
