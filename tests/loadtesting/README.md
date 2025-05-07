

# Load testing for Reflex using Locust

Steps to build locally -

Install locust and locust plugin
```
uv pip install locust
uv pip install 'locust-plugins[websocket]'
```

Start the reflex app
```
uv run reflex run
```

Start locust in a new terminal window
```
uv run locust
```

This will start a web app on `http://localhost:8089`

Configure the number of user and the ramp up. Watch results flow in. When done, terminate the locust process and get aggregate data in the terminal.