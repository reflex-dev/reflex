```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
from reflex_image_zoom import image_zoom
```

# Secrets (Environment Variables)


## Adding Secrets through the CLI

Below is an example of how to use an environment variable file. You can pass the `--envfile` flag with the path to the env file. For example:

```bash
reflex deploy --project f88b1574-f101-####-####-5f########## --envfile .env
```

In this example the path to the file is `.env`.


If you prefer to pass the environment variables manually below is deployment command example:

```bash
reflex deploy --project f88b1574-f101-####-####-5f########## --env OPENAI_API_KEY=sk-proj-vD4i9t6U############################
```

They are passed after the `--env` flag as key value pairs. 

To pass multiple environment variables, you can repeat the `--env` tag. i.e. `reflex deploy --project f88b1574-f101-####-####-5f########## --env KEY1=VALUE1 --env KEY2=VALUE`. The `--envfile` flag will override any envs set manually.


```md alert info
# More information on Environment Variables
Environment variables are encrypted and safely stored. We recommend that backend API keys or secrets are entered as `envs`. Make sure to enter the `envs` without any quotation marks. We do not show the values of them in any CLI commands, only their names (or keys).

You access the values of `envs` by referencing `os.environ` with their names as keys in your app's backend. For example, if you set an env `ASYNC_DB_URL`, you are able to access it by `os.environ["ASYNC_DB_URL"]`. Some Python libraries automatically look for certain environment variables. For example, `OPENAI_API_KEY` for the `openai` python client. The `boto3` client credentials can be configured by setting `AWS_ACCESS_KEY_ID`,`AWS_SECRET_ACCESS_KEY`. This information is typically available in the documentation of the Python packages you use.
```

## Adding Secrets through the Cloud UI

To find the secrets tab, click on the `Settings` tab in the Cloud UI on the app page.

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/environment_variables.webp"))
```

Then click on the `Secrets` tab as shown below.

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/environment_variables_2.webp"))
```

From here you can add or edit your environment variables. You will need to restart your app for these changes to take effect.

This functionality in the UI can be disabled by an admin of the project.