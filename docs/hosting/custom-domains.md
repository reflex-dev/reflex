```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
from reflex_image_zoom import image_zoom
```

# Custom Domains


With the Enterprise tier of Reflex Cloud you can use your own custom domain to host your app. 

## Prerequisites

You must purchase a domain from a domain registrar such as GoDaddy, Cloudflare, Namecheap, or AWS. 

For this tutorial we will use GoDaddy and the example domain `tomgotsman.us`.


## Steps

Once you have purchased your domain, you can add it to your Reflex Cloud app by following these steps:

1 - Ensure you have deployed your app to Reflex Cloud.

2 - Once your app is deployed click the `Custom Domain` tab and add your custom domain to the input field and press the Add domain button. You should now see a page like below:

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/custom-domains-DNS-inputs.webp"))
```

```python eval
rx.box(height="20px")
```

3 - On the domain registrar's website, navigate to the DNS settings for your domain. It should look something like the image below:

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/custom-domains-DNS-before.webp"))
```

```python eval
rx.box(height="20px")
```

4 - Add all four of the DNS records provided by Reflex Cloud to your domain registrar's DNS settings. If there is already an A name record, delete it and replace it with the one provided by Reflex Cloud. Your DNS settings should look like the image below:

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/custom-domains-DNS-after.webp"))
```

```md alert warning
# It may alert you that this record will resolve on ######.tomgotsman.us.tomgotsman.us.
If this happens ensure that you select to only have the record resolve on ######.tomgotsman.us.
```

```md alert warning
# Your domain provider may not support an Apex CNAME record, in this case just use an A record.
![Image showing failed CNAME record](/custom-domains-CNAME-fail.png)
```

```python eval
rx.box(height="20px")
```

5 - Once you have added the DNS records, refresh the page on the Reflex Cloud page (it may take a few minutes to a few hours to update successfully). If the records are correct, you should see a success message like the one below:

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/custom-domains-success.webp"))
```

```python eval
rx.box(height="20px")
```

6 - Now redeploy your app using the `reflex deploy` command and your app should now be live on your custom domain!