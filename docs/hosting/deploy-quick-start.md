# Reflex Hosting Service

```python exec
import reflex as rx
from pcweb import constants
from pcweb.pages import docs
from pcweb.templates.docpage import doccmdoutput
```

So far, we have been running our apps locally on our own machines.
But what if we want to share our apps with the world? This is where
the hosting service comes in.

## Quick Start

Reflex’s hosting service makes it easy to deploy your apps without worrying about configuring the infrastructure.

### Prerequisites

1. Hosting service requires `reflex>=0.3.2`.
2. This tutorial assumes you have successfully `reflex init` and `reflex run` your app.
3. Also make sure you have a `requirements.txt` file at the top level app directory that contains all your python dependencies!

### Authentication

First, create an account or log into it using the following command.

```bash
reflex login
```

You will be redirected to your browser where you can authenticate through Github or Gmail.

### Deployment

Once you have successfully authenticated, you can start deploying your apps.

Navigate to the project directory that you want to deploy and type the following command:

```bash
reflex deploy
```

The command is by default interactive. It asks you a few questions for information required for the deployment.

**Name**: choose a name for the deployed app. This name will be part of the deployed app URL, i.e. `<app-name>.reflex.run`. The name should only contain domain name safe characters: no slashes, no underscores. Domain names are case insensitive. To avoid confusion, the name you choose here is also case insensitive. If you enter letters in upper cases, we automatically convert them to lower cases.

**Regions**: enter the region code here or press `Enter` to accept the default. The default code `sjc` stands for San Jose, California in the US west coast. Check the list of supported regions at [reflex deployments regions](#reflex-deployments-regions).

**Envs**: `Envs` are environment variables. You might not have used them at all in your app. In that case, press `Enter` to skip. More on the environment variables in the later section [Environment Variables](#environment-variables).

That’s it! You should receive some feedback on the progress of your deployment and in a few minutes your app should be up. 🎉

```md alert info
Once your code is uploaded, the hosting service will start the deployment. After a complete upload, exiting from the command **does not** affect the deployment process. The command prints a message when you can safely close it without affecting the deployment.
```

## See it in Action

Below is a video of deploying the [AI chat app]({docs.tutorial.intro.path}) to our hosting service.

```python eval
rx.center(
    rx.video(url="https://www.youtube.com/embed/pf3FKE26hx4"),
    rx.box(height="3em"),
    width="100%",
    padding_y="2em"
)
```
