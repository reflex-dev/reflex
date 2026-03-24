```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
from reflex_image_zoom import image_zoom
from pcweb.pages.docs import hosting 
from pcweb.pages import docs
from pcweb.styles.styles import get_code_style, cell_style
```

## Machine Types


To scale your app you can choose different VMTypes. VMTypes are different configurations of CPU and RAM.

To scale your VM in the Cloud UI, click on the `Settings` tab in the Cloud UI on the app page, and then click on the `Scale` tab as shown below. Clicking on the `Change VM` button will allow you to scale your app.

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/scaling_vms.webp", padding_bottom="20px"))
```

### VMTypes in the CLI

To get all the possible VMTypes you can run the following command:

```bash
reflex cloud vmtypes
```

To set which VMType to use when deploying your app you can pass the `--vmtype` flag with the id of the VMType. For example:

```bash
reflex deploy --project f88b1574-f101-####-####-5f########## --vmtype c2m4
```

This will deploy your app with the `c2m4` VMType, giving your app 2 CPU cores and 4 GB of RAM.