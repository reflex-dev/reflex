```python exec
import reflex as rx
from reflex_image_zoom import image_zoom
from pcweb.constants import REFLEX_ASSETS_CDN, REFLEX_CLOUD_URL
from pcweb.pages.docs import hosting 
from pcweb.pages import docs
from pcweb.styles.styles import get_code_style, cell_style


REGIONS_DICT = {
    "ams": "Amsterdam, Netherlands",
    "arn": "Stockholm, Sweden",
    "bom": "Mumbai, India",
    "cdg": "Paris, France",
    "dfw": "Dallas, Texas (US)",
    "ewr": "Secaucus, NJ (US)",
    "fra": "Frankfurt, Germany",
    "gru": "Sao Paulo, Brazil",
    "iad": "Ashburn, Virginia (US)",
    "jnb": "Johannesburg, South Africa",
    "lax": "Los Angeles, California (US)",
    "lhr": "London, United Kingdom",
    "nrt": "Tokyo, Japan",
    "ord": "Chicago, Illinois (US)",
    "sjc": "San Jose, California (US)",
    "sin": "Singapore, Singapore",
    "syd": "Sydney, Australia",
    "yyz": "Toronto, Canada",
}

COUNTRIES_CODES = {
    "ams": "NL",
    "arn": "SE",
    "bom": "IN",
    "cdg": "FR",
    "dfw": "US",
    "ewr": "US",
    "fra": "DE",
    "gru": "BR",
    "iad": "US",
    "jnb": "ZA",
    "lax": "US",
    "lhr": "GB",
    "nrt": "JP",
    "ord": "US",
    "sjc": "US",
    "sin": "SG",
    "syd": "AU",
    "yyz": "CA",
}


```

## Regions

To scale your app you can choose different regions. Regions are different locations around the world where your app can be deployed. 

To scale your app to multiple regions in the Cloud UI, click on the `Settings` tab in the Cloud UI on the app page, and then click on the `Regions` tab as shown below. Clicking on the `Add new region` button will allow you to scale your app to multiple regions.

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/scaling_regions.webp", padding_bottom="20px"))
```

The table below show all the regions that can be deployed in.

```python eval
rx.el.table(
    rx.el.thead(
        rx.el.tr(
            rx.el.th(
                rx.el.div(
                    "Region",
                ),
                class_name="px-6 py-3 text-left text-sm font-semibold text-secondary-12 text-nowrap",
            ),
            rx.el.th(
                rx.el.div(
                    "Country",
                ),
                class_name="px-6 py-3 text-left text-sm font-semibold text-secondary-12 text-nowrap",
            ),
        ),
        class_name="bg-slate-2",
    ),
    rx.el.tbody(
        *[
            rx.el.tr(
                rx.el.td(
                    rx.el.div(
                        region,
                        class_name="h-5 rounded-md border justify-start items-center inline-flex bg-slate-1 text-xs font-medium shrink-0 px-1.5 w-fit text-slate-12 border-slate-6"
                    ),
                    class_name="px-6 py-3",
                ),
                rx.el.td(
                    rx.el.div(
                        rx.image(
                            src=f"{REFLEX_CLOUD_URL.rstrip('/')}/flags/{COUNTRIES_CODES[region]}.svg",
                            class_name="rounded-[2px] mr-2 w-5 h-4",
                        ),
                        REGIONS_DICT[region],
                        class_name="flex flex-row items-center gap-2",
                    ),
                    class_name="px-6 py-3 text-sm font-medium text-slate-9"
                ),
                class_name="even:bg-slate-2 odd:bg-slate-1 hover:bg-secondary-3",
            )
            for region in REGIONS_DICT.keys()
        ],
        class_name="divide-y divide-slate-4",
    ),
    class_name="w-full table-fixed rounded-xl overflow-hidden divide-y divide-slate-4",
)
```

### Selecting Regions to Deploy in the CLI

Below is an example of how to deploy your app in several regions:

```bash
reflex deploy --project f88b1574-f101-####-####-5f########## --region sjc --region iad
```

By default all apps are deloyed in `sjc` if no other regions are given. If you wish to deploy in another region or several regions you can pass the `--region` flag (`-r` also works) with the region code. Check out all the regions that we can deploy to below:


## Config File

To create a `config.yml` file for your app run the command below:

```bash
reflex cloud config
```

This will create a yaml file similar to the one below where you can edit the app configuration:

```yaml
name: medo
description: ''
regions:
  sjc: 1
  lhr: 2
vmtype: c1m1
hostname: null
envfile: .env
project: null
packages:
- procps
```

