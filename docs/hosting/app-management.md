```python exec
import reflex as rx
```

# App

In Reflex Cloud an "app" (or "application" or "website") refers to a web application built using the Reflex framework, which can be deployed and managed within the Cloud platform. 

You can deploy an app using the `reflex deploy` command.

There are many actions you can take in the Cloud UI to manage your app. Below are some of the most common actions you may want to take.


## Stopping an App

To stop an app follow the arrow in the image below and press on the `Stop app` button. Pausing an app will stop it from running and will not be accessible to users until you resume it. In addition, this will stop you being billed for your app.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/other/stopping_app.webp",
    alt="Stopping an app in Reflex Cloud",
    padding_bottom="20px",
)
```

```md alert info
# CLI Command to stop an app
`reflex cloud apps stop [OPTIONS] [APP_ID]`
```

## Deleting an App

To delete an app click on the `Settings` tab in the Cloud UI on the app page.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/other/environment_variables.webp",
    alt="App environment variables in Reflex Cloud",
)
```

Then click on the `Danger` tab as shown below.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/other/deleting_app.webp",
    alt="Deleting an app in Reflex Cloud",
)
```

Here there is a `Delete app` button. Pressing this button will delete the app and all of its data. This action is irreversible.

```md alert info
# CLI Command to delete an app
`reflex cloud apps delete [OPTIONS] [APP_ID]`
```


## Other app settings

Clicking on the `Settings` tab in the Cloud UI on the app page also allows a user to change the `app name`, change the `app description` and check the `app id`.

The other app settings also allows users to edit and add secrets (environment variables) to the app. For more information on secrets, see the [Secrets (Environment Variables)](/docs/hosting/secrets-environment-vars/) page.

## Deployment history

Every `reflex deploy` creates a new deployment. List an app's deployment history — each deployment's status, Python/Reflex versions, VM type, optional description, and whether it can be rolled back to — with:

```bash
reflex cloud apps history [APP_ID]
```

If you omit `APP_ID`, the app is resolved from the `appid` in your `cloud.yml`/`pyproject.toml`, or you can pass `--app-name`. Add `--json` for machine-readable output.

## Deployment descriptions

You can attach a short changelog note to a deployment so your history is easy to scan (for example, `"bump pricing page copy"`). Set it at deploy time:

```bash
reflex deploy --description "bump pricing page copy"
```

You can also set or replace the note on an existing deployment. Find the deployment id with `reflex cloud apps history`, then:

```bash
reflex cloud apps describe <DEPLOYMENT_ID> --app-id <APP_ID> --description "hotfix: revert checkout change"
```

Pass `--description ""` to clear the note. Descriptions show up in `reflex cloud apps history` and in the Cloud dashboard.

```md alert info
# CLI command to set a deployment description
`reflex cloud apps describe [OPTIONS] DEPLOYMENT_ID --description "<note>"`
```

## Rolling back a deployment

If a deploy introduces a regression, you can roll back to any previous deployment that still has a built image. A rollback redeploys that deployment's existing image — no rebuild from source — and makes it current again, demoting the currently running deployment to history.

```bash
reflex cloud apps rollback <DEPLOYMENT_ID> --app-id <APP_ID>
```

Use `reflex cloud apps history` to find rollback-eligible deployments: their `can rollback` value is `True`. A deployment can only be rolled back to on the provider whose registry holds its image, so after [switching an app's provider](/docs/hosting/cloud-providers/) the deployments built on the previous provider are no longer offered as rollback targets.

```md alert info
# CLI command to roll back
`reflex cloud apps rollback [OPTIONS] DEPLOYMENT_ID`
```
