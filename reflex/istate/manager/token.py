"""Representation of a StateManager token."""

from __future__ import annotations

import dataclasses
import pickle
from typing import TYPE_CHECKING, BinaryIO, Generic, TypeVar

from typing_extensions import Self

from reflex.utils import console

if TYPE_CHECKING:
    from reflex.state import BaseState

TOKEN_TYPE = TypeVar("TOKEN_TYPE")


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class StateToken(Generic[TOKEN_TYPE]):
    """Token for looking referencing a state instance in the StateManager."""

    # Identifier, usually the client_token, but could be a linked / shared token.
    ident: str

    # The class associated with the state instance.
    cls: type[TOKEN_TYPE]

    def with_cls(self, cls: type[TOKEN_TYPE]) -> Self:
        """Return a new token with the cls field updated to the provided class.

        Args:
            cls: The class to update the cls field to.

        Returns:
            A new StateToken instance with the updated cls field.
        """
        return dataclasses.replace(self, cls=cls)

    @property
    def cache_key(self) -> str:
        """The key used for caching state instances in the StateManager.

        Returns:
            A string key combining ident and class path.
        """
        return str(self)

    @property
    def lock_key(self) -> str:
        """The key used for locking and session-level bookkeeping.

        Returns:
            The token ident.
        """
        return self.ident

    def __str__(self) -> str:
        """The key used in the underlying StateManager store.

        Returns:
            A string representation of the token, which is a combination of the ident and cls name.
        """
        # urlencode the redis token to escape the slash delimiter.
        clean_ident = self.ident.replace("/", "%2F")
        clean_cls_name = f"{self.cls.__module__}.{self.cls.__name__}".replace(
            "/", "%2F"
        )
        return f"{clean_ident}/{clean_cls_name}"

    @classmethod
    def serialize(cls, state: TOKEN_TYPE) -> bytes:
        """Serialize the state for redis/disk storage.

        Args:
            state: The state to serialize.

        Returns:
            The serialized state.
        """
        return pickle.dumps(state)

    @classmethod
    def deserialize(
        cls, data: bytes | None = None, fp: BinaryIO | None = None
    ) -> TOKEN_TYPE:
        """Deserialize the state from redis/disk.

        data and fp are mutually exclusive, but one must be provided.

        Args:
            data: The serialized state data.
            fp: The file pointer to the serialized state data.

        Returns:
            The deserialized state instance.
        """
        if data is not None and fp is not None:
            msg = "Only one of `data` or `fp` may be provided, not both."
            raise ValueError(msg)
        if data is not None:
            return pickle.loads(data)
        if fp is not None:
            return pickle.load(fp)
        msg = "At least one of `data` or `fp` must be provided."
        raise ValueError(msg)

    @classmethod
    def get_and_reset_touched_state(cls, state: TOKEN_TYPE) -> bool:
        """Get the touched state and reset the touched flag.

        This is used to determine if a state has been modified since it was last serialized.

        Args:
            state: The state to check for modifications.

        Returns:
            The touched state of the state.
        """
        # Default implementation is always to write the state.
        return True


class BaseStateToken(StateToken["BaseState"]):
    """A token for the accessing reflex BaseState instances.

    This token type implies subtree hierarchy population and other semantic checks.
    """

    @property
    def cache_key(self) -> str:
        """The key used for caching state instances in the StateManager.

        BaseState tokens use just the ident because the entire state hierarchy
        lives under a single root state instance per session.

        Returns:
            The token ident.
        """
        return self.ident

    def with_cls(self, cls: type[BaseState]) -> Self:
        """Return a new token with the cls field updated to the provided class.

        Args:
            cls: The class to update the cls field to.

        Returns:
            A new StateToken instance with the updated cls field.
        """
        return super().with_cls(cls)

    def __str__(self) -> str:
        """The key used in the underlying StateManager store.

        Returns:
            A string representation of the token, which is a combination of the ident and cls name.
        """
        # urlencode the redis token to escape the slash delimiter.
        return f"{self.ident}_{self.cls.get_full_name()}"

    @classmethod
    def serialize(cls, state: BaseState) -> bytes:
        """Serialize the BaseState for redis/disk storage.

        Args:
            state: The BaseState to serialize.

        Returns:
            The serialized state.
        """
        return state._serialize()

    @classmethod
    def deserialize(
        cls, data: bytes | None = None, fp: BinaryIO | None = None
    ) -> BaseState:
        """Deserialize the BaseState from redis/disk.

        data and fp are mutually exclusive, but one must be provided.

        Args:
            data: The serialized state data.
            fp: The file pointer to the serialized state data.

        Returns:
            The deserialized BaseState instance.
        """
        from reflex.state import BaseState

        return BaseState._deserialize(data, fp)

    @classmethod
    def get_and_reset_touched_state(cls, state: BaseState) -> bool:
        """Get the touched state and reset the touched flag.

        This is used to determine if a state has been modified since it was last serialized.

        Args:
            state: The BaseState to check for modifications.

        Returns:
            The touched state of the BaseState.
        """
        was_touched = state._get_was_touched()
        state._was_touched = False  # Reset the touched flag after serializing.
        return was_touched

    @classmethod
    def from_legacy_token(
        cls, legacy_token: str, root_state: type[BaseState] | None
    ) -> Self:
        """Create a BaseStateToken from a legacy token string.

        The legacy token format is "{ident}_{module_path}.{class_name}".

        Args:
            legacy_token: The legacy token string to convert.
            root_state: The root state instance.

        Returns:
            A BaseStateToken instance created from the legacy token.

        Raises:
            ValueError: If the legacy token format is invalid or if the state class cannot be found
        """
        from reflex.state import _split_substate_key

        if root_state is None:
            msg = (
                "Root state must be provided to convert legacy token to BaseStateToken."
            )
            raise ValueError(msg)

        console.deprecate(
            feature_name="Passing a string to modify_state",
            reason="Use rx.BaseStateToken(token, state_cls) instead of the legacy string format",
            deprecation_version="0.9.0",
            removal_version="1.0",
        )

        client_token, state_path = _split_substate_key(legacy_token)
        state_cls = root_state.get_class_substate(tuple(state_path.split(".")))  # type: ignore[union-attr]
        return cls(ident=client_token, cls=state_cls)
