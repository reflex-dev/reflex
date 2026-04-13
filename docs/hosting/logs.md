```python exec
import reflex as rx
```

## View Logs

To view the app logs follow the arrow in the image below and press on the `Logs` dropdown.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/other/view_logs.webp", padding_bottom="20px"
)
```

```md alert info
# CLI Command to view logs
`reflex cloud apps logs [OPTIONS] [APP_ID]`
```

## View Deployment Logs and Deployment History

To view the deployment history follow the arrow in the image below and press on the `Deployments`.

```python eval
rx.image(src="https://web.reflex-assets.dev/other/view_deployment_logs.webp")
```

This brings you to the page below where you can see the deployment history of your app. Click on deployment you wish to explore further.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/other/view_deployment_logs_2.webp",
    padding_bottom="20px",
)
```

```md alert info
# CLI Command to view deployment history
`reflex cloud apps history [OPTIONS] [APP_ID]`
```

This brings you to the page below where you can view the deployment logs of your app by clicking the `Build logs` dropdown.

```python eval
rx.image(src="https://web.reflex-assets.dev/other/view_deployment_logs_3.webp")
```