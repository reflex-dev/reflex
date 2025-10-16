"""Plugin to enable screenshot functionality."""

from typing import TYPE_CHECKING

from reflex.plugins.base import Plugin as BasePlugin

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from typing_extensions import Unpack

    from reflex.app import App
    from reflex.plugins.base import PostCompileContext
    from reflex.state import BaseState

ACTIVE_CONNECTIONS = "/_active_connections"
CLONE_STATE = "/_clone_state"


def _deep_copy(state: "BaseState") -> "BaseState":
    """Create a deep copy of the state.

    Args:
        state: The state to copy.

    Returns:
        A deep copy of the state.
    """
    import copy

    copy_of_state = copy.deepcopy(state)

    def copy_substate(substate: "BaseState") -> "BaseState":
        substate_copy = _deep_copy(substate)

        substate_copy.parent_state = copy_of_state

        return substate_copy

    copy_of_state.substates = {
        substate_name: copy_substate(substate)
        for substate_name, substate in state.substates.items()
    }

    return copy_of_state


class ScreenshotPlugin(BasePlugin):
    """Plugin to handle screenshot functionality."""

    def post_compile(self, **context: "Unpack[PostCompileContext]") -> None:
        """Called after the compilation of the plugin.

        Args:
            context: The context for the plugin.
        """
        app = context["app"]
        self._add_active_connections_endpoint(app)
        self._add_clone_state_endpoint(app)

    @staticmethod
    def _add_active_connections_endpoint(app: "App") -> None:
        """Add an endpoint to the app that returns the active connections.

        Args:
            app: The application instance to which the endpoint will be added.
        """
        if not app._api:
            return

        def active_connections(_request: "Request") -> "Response":
            from starlette.responses import JSONResponse

            if not app.event_namespace:
                return JSONResponse({})

            return JSONResponse(app.event_namespace.token_to_sid)

        app._api.add_route(
            ACTIVE_CONNECTIONS,
            active_connections,
            methods=["GET"],
        )

    @staticmethod
    def _add_clone_state_endpoint(app: "App") -> None:
        """Add an endpoint to the app that clones the current state.

        Args:
            app: The application instance to which the endpoint will be added.
        """
        if not app._api:
            return

        async def clone_state(request: "Request") -> "Response":
            import uuid

            from starlette.responses import JSONResponse

            from reflex.state import _substate_key

            if not app.event_namespace:
                return JSONResponse({})

            token_to_clone = await request.json()

            if not isinstance(token_to_clone, str):
                return JSONResponse(
                    {"error": "Token to clone must be a string."}, status_code=400
                )

            old_state = await app.state_manager.get_state(token_to_clone)

            new_state = _deep_copy(old_state)

            new_token = uuid.uuid4().hex

            all_states = [new_state]

            found_new = True

            while found_new:
                found_new = False

                for state in list(all_states):
                    for substate in state.substates.values():
                        substate._was_touched = True

                        if substate not in all_states:
                            all_states.append(substate)

                            found_new = True

            await app.state_manager.set_state(
                _substate_key(new_token, new_state), new_state
            )

            return JSONResponse(new_token)

        app._api.add_route(
            CLONE_STATE,
            clone_state,
            methods=["POST"],
        )
