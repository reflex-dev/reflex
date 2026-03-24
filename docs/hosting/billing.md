```python exec
import reflex as rx
from reflex_image_zoom import image_zoom
from pcweb.pages.pricing.calculator import compute_table_base
from pcweb.pages.docs import hosting 
```

## Overview 

Billing for Reflex Cloud is monthly per project. Project owners and admins are able to view and manage the billing page. 

The billing for a project is comprised of two parts - number of `seats` and `compute`. 

## Seats

Projects on a paid plan can invite collaborators to join their project. 

Each additional collaborator is considered a `seat` and is charged on a flat monthly rate. Project owners and admins can manage permissions and roles for each seat in the settings tab on the project page. 

## Compute

Reflex Cloud is billed on a per second basis so you only pay for when your app is being used by your end users. When your app is idle, you are not charged. 

For more information on compute pricing, please see the [compute]({hosting.compute.path}) page.

## Manage Billing

To manage your billing, you can go to the `Billing` tab in the Cloud UI on the project page.

## Setting Billing Limits

If you want to set a billing limit for your project, you can do so by going to the `Billing` tab in the Cloud UI on the project page.
