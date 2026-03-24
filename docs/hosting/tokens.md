```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
from reflex_image_zoom import image_zoom
```

# Tokens

A token gives someone else all the permissions you have as a User or Admin. They can run any Reflex Cloud command from the CLI as if they were you, using the `--token` flag. A common use case is for GitHub Actions (you store this token in your secrets).

To access or create tokens, first click the avatar in the top-right corner to open the drop-down menu, then click `Account Settings`.

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/hosting_tokens_1.webp", alt="Adding tokens to Reflex Cloud", padding="1em 0em"))
```

Clicking `Account Settings` will redirect you to both the `Settings` and `Tokens` dashboards. Click the `Tokens` tab at the top to access your tokens or create new ones.


```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/hosting_tokens_2.webp", alt="Adding tokens to Reflex Cloud", padding="1em 0em"))
```
