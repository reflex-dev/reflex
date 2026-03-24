```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
from reflex_image_zoom import image_zoom
from pcweb.pages.docs import hosting 
from pcweb.pages import docs
from pcweb.styles.styles import get_code_style, cell_style
```

## View Logs

To view the app logs follow the arrow in the image below and press on the `Logs` dropdown.

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/view_logs.webp", padding_bottom="20px"))
```

```md alert info
# CLI Command to view logs
`reflex cloud apps logs [OPTIONS] [APP_ID]`
```

## View Deployment Logs and Deployment History

To view the deployment history follow the arrow in the image below and press on the `Deployments`.

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/view_deployment_logs.webp"))
```

This brings you to the page below where you can see the deployment history of your app. Click on deployment you wish to explore further.

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/view_deployment_logs_2.webp", padding_bottom="20px"))
```

```md alert info
# CLI Command to view deployment history
`reflex cloud apps history [OPTIONS] [APP_ID]`
```

This brings you to the page below where you can view the deployment logs of your app by clicking the `Build logs` dropdown.

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/view_deployment_logs_3.webp"))
```