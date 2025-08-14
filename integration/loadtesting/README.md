

# Load testing for Reflex using Locust

Steps to build locally -


Create virtual env
```
python3 -m venv env
```

Activate the virtual env
```
source env/bin/activate
```

Install dependencies
```
pip install -r requirements.txt
```

Also, install locust and locust plugin
```
pip install locust
pip install locust-plugins[websocket]
```

Start the reflex app using poetry
```
poetry run reflex run
```

Start locust in a new terminal window
```
locust
```

This will start a web app on `http://localhost:8089`

Configure the number of user and the ramp up. Watch results flow in. When done, terminate the locust process and get aggregate data in the terminal.