Begin opening the websocket transport before React mounts, then hydrate with a single `hydrate_and_load` event sent along with the websocket connect to save a round trip.
