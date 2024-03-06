import asyncio
import contextlib
import json
import traceback
from types import SimpleNamespace

from fastapi import FastAPI

from reflex.state import State, StateUpdate, _split_substate_key, _substate_key
from reflex.utils import prerequisites

state_op = SimpleNamespace(
    Channels=SimpleNamespace(
        STATE_UPDATE="state_update",
        BROADCAST_UPDATE="broadcast_update",
    ),
    Actions=SimpleNamespace(
        MESSAGE="message",
        SUBSCRIBE="subscribe",
    ),
)


async def _handle_state_update(full_token, delta):
    app = prerequisites.get_app().app

    token, _ = _split_substate_key(full_token)

    if token in app.event_namespace.client_mapping:
        sid = app.event_namespace.client_mapping[token]
        state = await app.state_manager.get_state(full_token)

        # apply the delta to the state and save it
        state.apply_delta(delta)
        await app.state_manager.set_state(full_token, state)

        # emit the update to the client
        await app.event_namespace.emit_update(
            update=StateUpdate(delta=delta),
            sid=sid,
        )


async def _handle_broadcast_update(delta):
    app = prerequisites.get_app().app
    for token in app.event_namespace.client_mapping:
        sid = app.event_namespace.client_mapping[token]
        state = await app.state_manager.get_state(_substate_key(token, State))

        # apply the delta to the state and save it
        state.apply_delta(delta)
        await app.state_manager.set_state(_substate_key(token, State), state)

        # emit the update to the client
        await app.event_namespace.emit_update(
            update=StateUpdate(delta=delta),
            sid=sid,
        )


async def _handle_pubsub_message(msg):
    channel = msg["channel"].decode()
    action = msg["type"]
    if action == state_op.Actions.MESSAGE:
        data = json.loads(msg["data"])
        try:
            if channel == state_op.Channels.STATE_UPDATE:
                await _handle_state_update(data["token"], data["delta"])
            elif channel == state_op.Channels.BROADCAST_UPDATE:
                # worker_output(f"broadcast update {data['delta']}")
                await _handle_broadcast_update(data["delta"])
        except Exception:
            traceback.print_exc()
    elif action == state_op.Actions.SUBSCRIBE:
        pass


async def _state_update_background():
    redis = prerequisites.get_redis()
    if not redis:
        return
    pubsub = redis.pubsub()
    await pubsub.subscribe(state_op.Channels.STATE_UPDATE)
    await pubsub.subscribe(state_op.Channels.BROADCAST_UPDATE)

    async for msg in pubsub.listen():
        try:
            await _handle_pubsub_message(msg)
        except Exception as e:
            print(e)
            traceback.print_exc()


@contextlib.asynccontextmanager
async def _state_lifespan(app: FastAPI):
    task = asyncio.create_task(_state_update_background())
    yield
    task.cancel()
