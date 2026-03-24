# Reflex Cloud - Quick Start

```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
from reflex_image_zoom import image_zoom
from pcweb.pages import docs
```

So far, we have been running our apps locally on our own machines.
But what if we want to share our apps with the world? This is where
the hosting service comes in.

## Quick Start

Reflex’s hosting service makes it easy to deploy your apps without worrying about configuring the infrastructure.

### Prerequisites

1. Hosting service requires `reflex>=0.6.6`.
2. This tutorial assumes you have successfully `reflex init` and `reflex run` your app.
3. Also make sure you have a `requirements.txt` file at the top level app directory that contains all your python dependencies! (To create a `requirements.txt` file, run `pip freeze > requirements.txt`.)


### Authentication

First run the command below to login / signup to your Reflex Cloud account: (command line)

```bash
reflex login
```

You will be redirected to your browser where you can authenticate through Github or Gmail.

### Web UI

Once you are at this URL and you have successfully authenticated, click on the one project you have in your workspace. You should get a screen like this:

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/cloud_project_page.webp", alt="Reflex Cloud Dashboard"))
```

This screen shows the login command and the deploy command. As we are already logged in, we can skip the login command.

### Deployment

Now you can start deploying your app.

In your cloud UI copy the `reflex deploy` command similar to the one shown below.

```bash
reflex deploy --project 2a432b8f-2605-4753-####-####0cd1####
```

In your project directory (where you would normally run `reflex run`) paste this command.

The command is by default interactive. It asks you a few questions for information required for the deployment.


1. The first question will compare your `requirements.txt` to your python environment and if they are different then it will ask you if you want to update your `requirements.txt` or to continue with the current one. If they are identical this question will not appear. To create a `requirements.txt` file, run `pip freeze > requirements.txt`.
2. The second question will search for a deployed app with the name of your current app, if it does not find one then it will ask if you wish to proceed in deploying your new app.
3. The third question is optional and will ask you for an app description.


That’s it! You should receive some feedback on the progress of your deployment and in a few minutes your app should be up. 🎉

For detailed information about the deploy command and its options, see the [Deploy API Reference]({docs.cloud.deploy.path}) and the [CLI Reference](https://reflex.dev/docs/api-reference/cli/).


```md alert info
# Once your code is uploaded, the hosting service will start the deployment. After a complete upload, exiting from the command **does not** affect the deployment process. The command prints a message when you can safely close it without affecting the deployment.
```

If you go back to the Cloud UI you should be able to see your deployed app and other useful app information.


```md alert info
# Setup a Cloud Config File
To create a `config.yml` file for your app to set your app configuration check out the [Cloud Config Docs]({docs.hosting.config_file.path}).
```

```md alert info
# Moving around the Cloud UI
To go back, i.e. from an app to a project or from a project to your list of projects you just click the `REFLEX logo` in the top left corner of the page.
```

```md alert info
# All flag values are saved between runs
All your flag values, i.e. environment variables or regions or tokens, are saved between runs. This means that if you run a command and you pass a flag value, the next time you run the same command the flag value will be the same as the last time you ran it. This means you should only set the flag values again if you want to change them.
```
