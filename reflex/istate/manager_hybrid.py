import dataclasses
import uuid

import aiosqlite

from reflex.istate.manager import StateManagerDisk
from reflex.state import BaseState, _substate_key


@dataclasses.dataclass
class StateManagerHybridSqlite(StateManagerDisk):
    """Hybrid state manager that uses SQLite for storage."""

    _db: aiosqlite.Connection | None = None

    _instance_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4, init=False)

    async def db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self.states_directory / "states.db")
            await self._init_db(self._db)
        return self._db

    @staticmethod
    async def _init_db(db: aiosqlite.Connection):
        async with db.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS states (
                    token TEXT PRIMARY KEY,
                    state_pkl BLOB NOT NULL,
                    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );""")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS lease (
                    token TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL
                );""")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS lease_queue (
                    token TEXT NOT NULL,
                    instance_id TEXT NOT NULL,
                    PRIMARY KEY (token, instance_id)
                );
            """)
            await db.commit()

    async def load_state(self, token: str) -> BaseState | None:
        """Load a state object based on the provided token.

        Args:
            token: The token used to identify the state object.

        Returns:
            The loaded state object or None.
        """
        db = await self.db()
        async with db.cursor() as cursor:
            await cursor.execute(
                "SELECT state_pkl FROM states WHERE token = ?", (token,)
            )
            row = await cursor.fetchone()
            if row:
                try:
                    return BaseState._deserialize(data=row[0])
                except Exception:
                    pass
        return None

    async def set_state_for_substate(self, client_token: str, substate: BaseState):
        """Set the state for a substate.

        Args:
            client_token: The client token.
            substate: The substate to set.
        """
        substate_token = _substate_key(client_token, substate)

        if substate._get_was_touched():
            substate._was_touched = False  # Reset the touched flag after serializing.
            pickle_state = substate._serialize()
            if pickle_state:
                db = await self.db()
                async with db.cursor() as cursor:
                    await cursor.execute(
                        "REPLACE INTO states (token, state_pkl, last_update) VALUES (?, ?, CURRENT_TIMESTAMP)",
                        (substate_token, pickle_state),
                    )
                    await db.commit()
        for substate_substate in substate.substates.values():
            await self.set_state_for_substate(client_token, substate_substate)

    async def close(self):
        if self._db:
            await self._db.close()
        self._db = None
