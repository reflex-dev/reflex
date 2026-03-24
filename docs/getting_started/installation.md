```python exec
from pcweb import constants
import reflex as rx
from pcweb.pages.gallery import gallery
app_name = "my_app_name"
default_url = "http://localhost:3000"
```

# Installation

Reflex requires Python 3.10+.


```md video https://youtube.com/embed/ITOZkzjtjUA?start=758&end=1206
# Video: Installation
```


## Virtual Environment

We **highly recommend** creating a virtual environment for your project.

[uv]({constants.UV_URL}) is the recommended modern option. [venv]({constants.VENV_URL}), [conda]({constants.CONDA_URL}) and [poetry]({constants.POETRY_URL}) are some alternatives.


# Install Reflex on your system

---md tabs

--tab macOS/Linux
## Install on macOS/Linux

We will go with [uv]({constants.UV_URL}) here.


### Prerequisites

#### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installation, restart your terminal or run `source ~/.bashrc` (or `source ~/.zshrc` for zsh).

Alternatively, install via [Homebrew, PyPI, or other methods](https://docs.astral.sh/uv/getting-started/installation/).

**macOS (Apple Silicon) users:** Install [Rosetta 2](https://support.apple.com/en-us/HT211861). Run this command:
    
`/usr/sbin/softwareupdate --install-rosetta --agree-to-license`


### Create the project directory 

Replace `{app_name}` with your project name. Switch to the new directory.

```bash
mkdir {app_name}
cd {app_name}
```

### Initialize uv project

```bash
uv init
```

### Add Reflex to the project

```bash
uv add reflex
```

### Initialize the Reflex project

```bash
uv run reflex init
```


--
--tab Windows
## Install on Windows

For Windows users, we recommend using [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/about) for optimal performance.

**WSL users:** Refer to the macOS/Linux instructions above.

For the rest of this section we will work with native Windows (non-WSL).

We will go with [uv]({constants.UV_URL}) here.

### Prerequisites

#### Install uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, restart your terminal (PowerShell or Command Prompt).

Alternatively, install via [WinGet, Scoop, or other methods](https://docs.astral.sh/uv/getting-started/installation/).

### Create the project directory 

Replace `{app_name}` with your project name. Switch to the new directory.

```bash
mkdir {app_name}
cd {app_name}
```

### Initialize uv project

```bash
uv init
```

### Add Reflex to the project

```bash
uv add reflex
```

### Initialize the Reflex project

```bash
uv run reflex init
```

```md alert warning
# Error `Install Failed - You are missing a DLL required to run bun.exe` Windows
Bun requires runtime components of Visual C++ libraries to run on Windows. This issue is fixed by installing [Microsoft Visual C++ 2015 Redistributable](https://www.microsoft.com/en-us/download/details.aspx?id=53840).
```
--

---


Running `uv run reflex init` will return the option to start with a blank Reflex app, premade templates built by the Reflex team, or to try our [AI builder]({constants.REFLEX_BUILD_URL}).

```bash
Initializing the web directory.

Get started with a template:
(0) A blank Reflex app.
(1) Premade templates built by the Reflex team.
(2) Try our AI builder.
Which template would you like to use? (0): 
```

From here select an option. 


## Run the App

Run it in development mode:

```bash
uv run reflex run
```

Your app runs at [http://localhost:3000](http://localhost:3000).

Reflex prints logs to the terminal. To increase log verbosity to help with debugging, use the `--loglevel` flag:

```bash
uv run reflex run --loglevel debug
```

Reflex will *hot reload* any code changes in real time when running in development mode. Your code edits will show up on [http://localhost:3000](http://localhost:3000) automatically.
