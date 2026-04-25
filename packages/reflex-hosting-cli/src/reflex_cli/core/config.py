"""Module for the Config class."""

from __future__ import annotations

import dataclasses
import typing
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_origin

from reflex_cli import constants
from reflex_cli.utils.exceptions import ConfigError, ConfigInvalidFieldValueError

RegionOption = Literal[
    "ams",
    "arn",
    "bog",
    "cdg",
    "dfw",
    "ewr",
    "fra",
    "gru",
    "iad",
    "jnb",
    "lax",
    "lhr",
    "nrt",
    "ord",
    "sjc",
    "sin",
    "syd",
    "yyz",
]

VmType = Literal[
    "c1m.5",
    "c1m1",
    "c1m2",
    "c2m2",
    "c2m4",
    "c4m4",
    "c4m8",
    "pc1m2",
    "pc2m4",
    "pc2m8",
    "pc4m8",
]


def _validate_type(value: Any, _type: type, key: str = ""):
    if not isinstance(value, _type):
        raise (
            ConfigInvalidFieldValueError(
                f"Invalid value for {key}. Expected a {_type}, got {value} of type {type(value).__name__}."
            )
            if key
            else ConfigInvalidFieldValueError(
                f"Invalid value. Expected a {_type}, got {value} of type {type(value).__name__}."
            )
        )


def _validate_literal(value: Any, key: str = "", valid_values: Sequence[str] = ()):
    _validate_type(value, str, key)
    if value not in valid_values:
        raise (
            ConfigInvalidFieldValueError(
                f"Invalid value for {key}. Expected one of {valid_values}, got {value}."
            )
            if key
            else ConfigInvalidFieldValueError(
                f"Invalid value. Expected one of {valid_values}, got {value}."
            )
        )


def _validate_list(value: Any, item_type: type, key: str = ""):
    _validate_type(value, list, key)
    for item in value:
        _validate_dispatch(item, item_type, key=f"{key} item" if key else "")


def _validate_dict(value: Any, key_type: type, value_type: type, key: str = ""):
    _validate_type(value, dict, key)
    for key, val in value.items():
        _validate_dispatch(key, key_type, key=f"{key} key" if key else "")
        _validate_dispatch(val, value_type, key=f"{key} value" if key else "")


def _validate_optional(value: Any, non_optional_type: type, key: str = ""):
    if value is not None:
        _validate_dispatch(value, non_optional_type, key)


def _validate_dispatch(
    value: Any,
    _type: Any,
    key: str = "",
):
    if _type in [str, int, float, bool]:
        _validate_type(value, _type, key)
    origin = get_origin(_type)
    if origin is typing.Union:
        args = typing.get_args(_type)
        if len(args) == 2 and type(None) in args:
            non_optional_type = next(arg for arg in args if arg is not type(None))
            _validate_optional(value, non_optional_type, key)
        return
    if origin is list:
        item_type = typing.get_args(_type)[0]
        _validate_list(value, item_type, key)
    if origin is typing.Literal:
        _validate_literal(value, key, typing.get_args(_type))
    if origin is dict:
        key_type, value_type = typing.get_args(_type)
        _validate_dict(value, key_type, value_type, key)


@dataclass
class Config:
    """Configuration class for the CLI."""

    name: str | None = dataclasses.field(default=None)
    description: str | None = dataclasses.field(default=None)
    vmtype: VmType | None = dataclasses.field(default=None)
    regions: dict[RegionOption, int] | None = dataclasses.field(default=None)
    hostname: str | None = dataclasses.field(default=None)
    envfile: str | None = dataclasses.field(default=None)
    project: str | None = dataclasses.field(default=None)
    packages: list[str] = dataclasses.field(default_factory=list)
    appid: str | None = dataclasses.field(default=None)
    strategy: str | None = dataclasses.field(default=None)
    include_db: bool = dataclasses.field(default=False)

    _cloud_config_path: Path | None = dataclasses.field(default=None)

    def __post_init__(self):
        """Post-initialization validation for the Config class.

        Raises:
            ConfigInvalidFieldValueError: If any field value is invalid.

        # noqa: DAR401

        """
        evaluated_type = typing.get_type_hints(Config)
        for field in dataclasses.fields(self):
            if field.name.startswith("_"):
                continue
            field_type = evaluated_type.get(field.name)
            if field_type is None:
                raise ConfigInvalidFieldValueError(f"Invalid field: {field}")
            try:
                _validate_dispatch(
                    getattr(self, field.name), field_type, key=field.name
                )
            except ValueError as e:
                if self._cloud_config_path:
                    raise ConfigInvalidFieldValueError(
                        f"Invalid {self._cloud_config_path.name}. " + str(e)
                    ).with_traceback(e.__traceback__) from None

    @classmethod
    def _filter_dict(
        cls,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Filters a dictionary to only include fields defined in the Config class.

        Args:
            data: The dictionary to filter.

        Returns:
            dict[str, Any]: A filtered dictionary containing only valid Config fields.

        """
        fields_keys = {field.name for field in dataclasses.fields(cls)}
        return {
            key: value
            for key, value in data.items()
            if key in fields_keys and value is not None
        }

    @classmethod
    def from_yaml(
        cls,
        yaml_path: Path = Path.cwd() / constants.Dirs.CLOUD_YAML,
        env: str | None = None,
    ) -> Config:
        """Creates a Config instance from a YAML file.

        Args:
            yaml_path: The path to the YAML file. Defaults to "cloud.yml" in the current directory.
            env: The environment to load the config for.

        Returns:
            Config: A Config instance with the values from the YAML file.

        Raises:
            ConfigError: If the YAML file is not found.

        """
        if not yaml_path.exists():
            raise ConfigError(f"Config file not found at {yaml_path}.")

        try:
            import yaml
        except ImportError as e:
            raise ConfigError(
                "YAML support is not available. Please install PyYAML to use this feature."
            ) from e

        with yaml_path.open() as file:
            data = yaml.safe_load(file)
            if env:
                data = data.get("env", {}).get(env, {})
            data = cls._filter_dict(data)
        return cls(_cloud_config_path=yaml_path, **data)

    @classmethod
    def from_toml(
        cls,
        pyproject_path: Path = Path.cwd() / "pyproject.toml",
        env: str | None = None,
    ) -> Config:
        """Creates a Config instance from a TOML file.

        Args:
            pyproject_path: The path to the TOML file. Defaults to "pyproject.toml" in the current directory.
            env: The environment to load the config for.

        Returns:
            Config: A Config instance with the values from the TOML file.

        Raises:
            ConfigError: If the TOML file is not found.

        """
        if not pyproject_path.exists():
            raise ConfigError(f"Config file not found at {pyproject_path}.")

        try:
            import tomllib
        except ImportError as e:
            raise ConfigError(
                "TOML support is not available. Please use Python 3.11 or later."
            ) from e

        with pyproject_path.open("rb") as file:
            pyproject_data = tomllib.load(file)
            if not isinstance(pyproject_data, dict):
                raise ConfigError(
                    f"Invalid TOML file format at {pyproject_path}. Expected a dictionary."
                )
            tools = pyproject_data.get("tool", {})
            if not isinstance(tools, dict):
                raise ConfigError(
                    f"Invalid TOML file format at {pyproject_path}. Expected 'tool' to be a dictionary."
                )
            if "reflex-cloud" not in tools:
                raise ConfigError(
                    f"Invalid TOML file format at {pyproject_path}. Expected 'tool.reflex-cloud' to be present."
                )
            data = tools["reflex-cloud"]
            if env:
                data = data.get("env", {}).get(env, {})
            data = cls._filter_dict(data)
        return cls(_cloud_config_path=pyproject_path, **data)

    @classmethod
    def from_yaml_or_toml_or_default(cls) -> Config:
        """Creates a Config instance from either a YAML or TOML file, or returns a default instance.

        Returns:
            Config: A Config instance with values from the YAML or TOML file, or a default instance if neither file exists.

        """
        return cls.from_yaml_or_toml_or_none() or cls()

    @classmethod
    def from_yaml_or_toml_or_none(cls, env: str | None = None) -> Config | None:
        """Attempts to create a Config instance from either a YAML or TOML file.

        Args:
            env: The environment to load the config for. If provided, it will look for environment

        Returns:
            Config | None: A Config instance with values from the YAML or TOML file, or None if neither file exists or is valid.

        """
        try:
            return cls.from_yaml(env=env)

        except ConfigError:
            try:
                return cls.from_toml(env=env)
            except ConfigError:
                return None

    def with_overrides(self, **kwargs: Any) -> Config:
        """Creates a new Config instance with overrides.

        Args:
            **kwargs: Key-value pairs of fields to override. The values take
                      precedence over the existing instance values.

        Returns:
            Config: A new Config instance with updated values.

        """
        return dataclasses.replace(self, **kwargs)

    def exists(self) -> bool:
        """Check if the config file exists.

        Returns:
            bool: True if the config file exists, False otherwise.

        """
        return bool(self._cloud_config_path) and self._cloud_config_path.exists()
