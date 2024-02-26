```python exec
from pcweb import constants
import reflex as rx
app_name = "my_app_name"
default_url = "http://localhost:3000"
```

# Installation

Reflex requires Python 3.8+.

## Virtual Environment

We **highly recommend** creating a virtual environment for your project.

[venv]({constants.VENV_URL}) is the standard option. [conda]({constants.CONDA_URL}) and [poetry]({constants.POETRY_URL}) are some alternatives.

## Install on macOS/Linux

We will go with [venv]({constants.VENV_URL}) here.


### Prerequisites
macOS (Apple Silicon) users should install [Rosetta 2](https://support.apple.com/en-us/HT211861). Run this command:
    
`/usr/sbin/softwareupdate --install-rosetta --agree-to-license`


### Create the project directory 

Replace `{app_name}` with your project name. Switch to the new directory.

```bash
mkdir {app_name}
cd {app_name}
```

### Setup virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

```md alert warning
# Error `No module named venv`

While Python typically ships with `venv` it is not installed by default on some systems.
If so, please install it manually. E.g. on Ubuntu Linux, run `sudo apt-get install python3-venv`.
```

### Install Reflex package

Reflex is available as a [pip](constants.PIP_URL) package.

```bash
pip install reflex
```

```md alert warning
# Error `command not found: pip`

While Python typically ships with `pip` as the standard package management tool, it is not installed by default on some systems.
You may need to install it manually. E.g. on Ubuntu Linux, run `apt-get install python3-pip`
```

### Initialize the project

```bash
reflex init
```

```md alert warning
# Error `command not found: reflex`
If you install Reflex with no virtual environment and get this error it means your `PATH` cannot find the reflex package. 
A virtual environment should solve this problem, or you can try running `python3 -m` before the reflex command.
```


## Install on Windows

### Prerequisites
For Windows users, we recommend using [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/about) for optimal performance.

WSL users should refer to instructions for Linux above.

For the rest of this section we will work with native Windows (non-WSL).

We will go with [venv]({constants.VENV_URL}) here, for virtual environments.

### Create a new project directory

```bash
mkdir {app_name}
cd {app_name}
```

### Setup virtual environment

```bash
py -3 -m venv .venv
.venv\\Scripts\\activate
```

### Install Reflex package

```bash
pip install reflex
```

### Initialize the project

```bash
reflex init
```

```md alert warning
# Error `command not found: reflex`

The Reflex framework includes the `reflex` command line (CLI) tool. Using a virtual environment is highly recommended for a seamless experience (see below).",
```

## Run the App

Run it in development mode:

```bash
reflex run
```

Your app runs at [http://localhost:3000](http://localhost:3000).

Reflex prints logs to the terminal. To increase log verbosity to help with debugging, use the `--loglevel` flag:

```bash
reflex run --loglevel debug
```

Reflex will *hot reload* any code changes in real time when running in development mode. Your code edits will show up on [http://localhost:3000](http://localhost:3000) automatically.

## (Optional) Run the demo app

The demo app showcases some of Reflex's features.

```bash
reflex demo
```
