```python exec
import reflex as rx


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

# Regions

Regions are the locations where Reflex runs your app. Add regions closer to your users to improve latency and availability.

## Manage regions in Reflex Build

1. Open **Deployments** and select the app.
2. Open **Settings > Regions**.
3. Select **Add new region**.
4. Choose the region and number of instances, then review the resource change before confirming.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/hosting/settings_regions.webp",
    alt="Region settings with the current and available deployment regions",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

You can remove a region when the app has more than one. Removing it makes the app unavailable in that region.

The table below lists the Reflex Cloud region codes. A connected Google Cloud account uses the region chosen in the organization's Cloud Provider settings.

```python eval
rx.el.table(
    rx.el.thead(
        rx.el.tr(
            rx.el.th(
                rx.el.div(
                    "Region",
                ),
                class_name="px-6 py-3 text-left text-sm font-semibold text-foreground text-nowrap",
            ),
            rx.el.th(
                rx.el.div(
                    "Country",
                ),
                class_name="px-6 py-3 text-left text-sm font-semibold text-foreground text-nowrap",
            ),
        ),
        class_name="bg-muted",
    ),
    rx.el.tbody(
        *[
            rx.el.tr(
                rx.el.td(
                    rx.el.div(
                        region,
                        class_name="h-5 rounded-md border justify-start items-center inline-flex bg-background text-xs font-medium shrink-0 px-1.5 w-fit text-foreground border-border",
                    ),
                    class_name="px-6 py-3",
                ),
                rx.el.td(
                    rx.el.div(
                        rx.image(
                            src=f"https://build.reflex.dev/flags/{COUNTRIES_CODES[region]}.svg",
                            alt="Region country flag",
                            class_name="rounded-[2px] mr-2 w-5 h-4",
                        ),
                        REGIONS_DICT[region],
                        class_name="flex flex-row items-center gap-2",
                    ),
                    class_name="px-6 py-3 text-sm font-medium text-subtle-foreground",
                ),
                class_name="even:bg-muted odd:bg-background hover:bg-accent",
            )
            for region in REGIONS_DICT.keys()
        ],
        class_name="divide-y divide-border-subtle",
    ),
    class_name="w-full table-fixed rounded-xl overflow-hidden divide-y divide-border-subtle",
)
```

## Select regions from the CLI

Repeat `--region` to deploy to more than one Reflex Cloud region:

```bash
reflex deploy --project <PROJECT_ID> --region sjc --region iad
```

Apps use `sjc` by default when no region is configured. The `-r` short form is also supported. CLI arguments override the corresponding value in `cloud.yml` or `pyproject.toml`; see [Cloud Configuration File](/docs/hosting/config-file/).
