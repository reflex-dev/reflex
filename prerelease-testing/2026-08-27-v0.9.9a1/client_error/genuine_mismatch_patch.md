# Genuine stale-frontend mismatch repro (backend gains a substate)

1. Build+run the app once cleanly (creates `.web` compiled for `State`).
2. Set `api_url="http://localhost:8220"` in `rxconfig.py` (so the stale frontend
   build points at the backend port; env.json is regenerated from config).
3. Edit `client_error/client_error.py`: add a NEW substate the frontend build
   does not know, and have `bump` mutate it:

   ```python
   class Extra(rx.State):
       extra_val: int = 0

   class State(rx.State):
       counter: int = 0
       log: list[str] = []

       @rx.event
       async def bump(self):
           self.counter += 1
           self.log = [*self.log, f"bump -> {self.counter}"]
           extra = await self.get_state(Extra)
           extra.extra_val += 1
   ```
4. Serve the stale build + changed backend as two processes, both with
   `REFLEX_SKIP_COMPILE=1` so the frontend is NOT recompiled:
   - `reflex run --frontend-only --frontend-port 3220`   (serves stale `.web`)
   - `reflex run --backend-only  --backend-port  8220`   (loads State + Extra)
5. Load http://localhost:3220 in a browser. On hydration the backend pushes a
   delta including the unknown `Extra` substate -> the stale frontend reports the
   client_error (browser console + backend terminal), session goes fatal.

Note: merely RENAMING the `State` class does not trigger it on load — the base
rx.State router still hydrates and a default-valued renamed substate emits no
delta. The mismatch is only reported once the diverged substate actually pushes
an update.
