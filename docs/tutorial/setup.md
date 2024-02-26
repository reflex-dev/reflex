```python exec
from pcweb import constants
import reflex as rx
```

# Setting up Your Project

We will start by creating a new project and setting up our development environment. First, create a new directory for your project and navigate to it.

```bash
~ $ mkdir chatapp
~ $ cd chatapp
```

Next, we will create a virtual environment for our project. This is optional, but recommended. In this example, we will use [venv]({constants.VENV_URL}) to create our virtual environment.

```bash
chatapp $ python3 -m venv venv
$ source venv/bin/activate
```

Now, we will install Reflex and create a new project. This will create a new directory structure in our project directory.

```bash
chatapp $ pip install reflex
chatapp $ reflex init
────────────────────────────────── Initializing chatapp ───────────────────────────────────
Success: Initialized chatapp
chatapp $ ls
assets          chatapp         rxconfig.py     venv
```

```python eval
rx.box(height="20px")
```

You can run the template app to make sure everything is working.

```bash
chatapp $ reflex run
─────────────────────────────────── Starting Reflex App ───────────────────────────────────
Compiling:  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 1/1 0:00:00
─────────────────────────────────────── App Running ───────────────────────────────────────
App running at: http://localhost:3000
```

```python eval
rx.box(height="20px")
```

You should see your app running at [http://localhost:3000]({"http://localhost:3000"}).

Reflex also starts the backend server which handles all the state management and communication with the frontend. You can test the backend server is running by navigating to [http://localhost:8000/ping]({"http://localhost:8000/ping"}).

Now that we have our project set up, in the next section we will start building our app!
