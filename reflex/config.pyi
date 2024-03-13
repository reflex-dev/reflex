""" Generated with stubgen from mypy, then manually edited, do not regen."""

from reflex import constants as constants
from reflex.base import Base as Base
from reflex.utils import console as console
from typing import Any, Dict, List, Optional, overload

class DBConfig(Base):
    engine: str
    username: Optional[str]
    password: Optional[str]
    host: Optional[str]
    port: Optional[int]
    database: str

    def __init__(
        self,
        database: str,
        engine: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ): ...
    @classmethod
    def postgresql(
        cls,
        database: str,
        username: str,
        password: str | None = ...,
        host: str | None = ...,
        port: int | None = ...,
    ) -> DBConfig: ...
    @classmethod
    def postgresql_psycopg2(
        cls,
        database: str,
        username: str,
        password: str | None = ...,
        host: str | None = ...,
        port: int | None = ...,
    ) -> DBConfig: ...
    @classmethod
    def sqlite(cls, database: str) -> DBConfig: ...
    def get_url(self) -> str: ...

class Config(Base):
    class Config:
        validate_assignment: bool
    app_name: str
    loglevel: constants.LogLevel
    frontend_port: int
    frontend_path: str
    backend_port: int
    api_url: str
    deploy_url: Optional[str]
    backend_host: str
    db_url: Optional[str]
    redis_url: Optional[str]
    telemetry_enabled: bool
    bun_path: str
    cors_allowed_origins: List[str]
    tailwind: Optional[Dict[str, Any]]
    timeout: int
    next_compression: bool
    event_namespace: Optional[str]
    frontend_packages: List[str]
    rxdeploy_url: Optional[str]
    cp_backend_url: str
    cp_web_url: str
    username: Optional[str]
    gunicorn_worker_class: str

    def __init__(
        self,
        *args,
        app_name: str,
        loglevel: Optional[constants.LogLevel] = None,
        frontend_port: Optional[int] = None,
        frontend_path: Optional[str] = None,
        backend_port: Optional[int] = None,
        api_url: Optional[str] = None,
        deploy_url: Optional[str] = None,
        backend_host: Optional[str] = None,
        db_url: Optional[str] = None,
        redis_url: Optional[str] = None,
        telemetry_enabled: Optional[bool] = None,
        bun_path: Optional[str] = None,
        cors_allowed_origins: Optional[List[str]] = None,
        tailwind: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        next_compression: Optional[bool] = None,
        event_namespace: Optional[str] = None,
        frontend_packages: Optional[List[str]] = None,
        rxdeploy_url: Optional[str] = None,
        cp_backend_url: Optional[str] = None,
        cp_web_url: Optional[str] = None,
        username: Optional[str] = None,
        gunicorn_worker_class: Optional[str] = None,
        **kwargs
    ) -> None: ...
    @property
    def module(self) -> str: ...
    @staticmethod
    def check_deprecated_values(**kwargs) -> None: ...
    def update_from_env(self) -> None: ...
    def get_event_namespace(self) -> str | None: ...
    def _set_persistent(self, **kwargs) -> None: ...

def get_config(reload: bool = ...) -> Config: ...
