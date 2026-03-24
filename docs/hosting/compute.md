```python exec
import reflex as rx
from reflex_image_zoom import image_zoom
from pcweb.pages.pricing.calculator import compute_table_base
```

## Compute Usage

Reflex Cloud is billed on a per second basis so you only pay for when your app is being used by your end users. When your app is idle, you are not charged. 

This allows you to deploy your app on larger sizes and multiple regions without worrying about paying for idle compute. We bill on a per second basis so you only pay for the compute you use.

By default your app stays alive for 5 minutes after the no users are connected. After this time your app will be considered idle and you will not be charged. Start up times usually take less than 1 second for you apps to come back online.

#### Warm vs Cold Start
- Apps below `c2m2` are considered warm starts and are usually less than 1 second.
- If your app is larger than `c2m2` it will be a cold start which takes around 15 seconds. If you want to avoid this you can reserve a machine.

## Compute Pricing Table

```python eval
compute_table_base()
```

## Reserved Machines (Coming Soon)

If you expect your apps to be continuously receiving users, you may want to reserve a machine instead of having us manage your compute. 

This will be a flat monthly rate for the machine.

## Monitoring Usage

To monitor your projects usage, you can go to the billing tab in the Reflex Cloud UI on the project page.

Here you can see the current billing and usage for your project.


## Real Life Examples of compute charges on the paid tiers


```md alert
# Single Application - Single Region

Anna, a hobbyist game developer, built a pixel art generator and hosted it on Reflex Cloud so fellow artists could use it anytime. She deployed her app in the San Francisco region, where she lives. If her users use the site for an hour a day, how much would Anna pay?

**Facts:**

- **Machine size:** `c1m1` (1 CPU, 1 GB Memory) - `$0.083` per hour
- **Regions:** `1` (SJC)
- **Avg usage per day per region:** `1 Hour`

**Maths:**

`1 region * 1 hour * 30 days = 30 compute hours`

`30 * 0.083 = 2.49`

(assuming a 30 day month)

Anna's total cost for compute would be `$2.49` for the month. However, since paid users receive a `$10` credit, her compute cost is fully covered.

**Charge for compute:**

`$0.00 dollars`
```



```md alert
# Single Application - Multi Region

Bob created a social media application and decided to host it on Reflex Cloud. Bob has users in Paris, London, San Jose and Sydney. Bob decided to deploy his application to all those region as well as additional one in Paris since that where Bob lives. If users use the site in each region for 30 minutes a day how much would Bob pay?

**Facts:**

- **Machine size:** `c1m1` (1 CPU, 1 GB Memory) - `$0.083` Cost per hour
- **Regions:** `5` (CDG x 2, LHR x 1, SJC x 1, SYD x 1)
- **Avg usage per day per region:** `0.5 Hours`

**Maths:**

`5 regions * 0.5 hours * 30 days = 75 compute hours` 

`75 * 0.083 = 6.23`

(assuming a 30 day month)

Bob would owe `$6.23` for this month. However since Bob is a paid user they receive a `$10` credit which brings Bob's bill down to `$0`.

**Charge for compute:**

`$0.00 dollars`
```




```md alert
# Single Growing Application - Multi Region

Charlie, a small startup founder, built a finance tracking app that allows users to create and share finance insights in real time. As his user base expanded across different regions, he needed a multi-region setup to reduce latency and improve performance. To ensure a smooth experience, he deployed his app on Reflex Cloud using a `c1m2` machine in four regions.

If users access the app on average for **16 hours per week** in each region, how much would Charlie pay?

**Facts:**
- **Machine size:** `c1m2` (1 CPU, 2 GB Memory) - `$0.157` per hour  
- **Regions:** `4`  
- **Avg usage per week per region:** `16 Hours`

**Maths:**

`4 regions * 16 hours * 4 weeks = 256 compute hours` 

`256 * 0.157 = 40.19`

(assuming 4 weeks in a month)

Charlie would owe `$40.19` for this month. However since Charlie is a paid user they receive a `$10` credit which brings Bob's bill down to `$30.19`.

**Charge for compute:**

`$30.19 dollars`

```



```md alert
# Single Application High-Performance App - Single Region

David, an **AI enthusiast**, developed a **real-time image enhancement tool** that allows photographers to upscale and enhance their images using machine learning. Since his app requires more processing power, he deployed it on a **`c2m2` machine**, which offers increased CPU and memory to handle the intensive AI workloads.  

With users accessing the app **2 hours per day** over a **30-day month**, how much would David pay?

**Facts:**
- **Machine size:** `c2m2` (2 CPU, 2 GB Memory) - `$0.166` per hour  
- **Regions:** `1`  
- **Avg usage per day:** `2 Hours` 


**Maths:**

`1 region * 2 hours * 30 days = 60 compute hours` 

`60 * 0.166 = 9.96`

(assuming a 30 day month)

David would owe `$9.96` for this month. However since David is a paid user they receive a `$10` credit, he will not be charged for compute for this month.

**Charge for compute:**

`$0.00 dollars`

```


```md alert
# Single Fast Scaling App - Multiple Regions 
 
Emily, a **productivity app developer**, built a **real-time team collaboration tool** that helps remote teams manage tasks and communicate efficiently. With users spread across multiple locations, she needed **low-latency performance** to ensure a seamless experience. To achieve this, Emily deployed her app using a `c1m1` machine in **three regions**.  

With users actively using the app **6 hours per day in each region** over a **30-day month**, how much would Emily pay?


**Facts:**
- **Machine size:** `c1m1` (1 CPU, 1 GB Memory) - `$0.083` per hour  
- **Regions:** `3`  
- **Avg usage per day per region:** `6 Hours`


**Maths:**

`3 regions * 6 hours * 30 days = 540 compute hours` 

`540 * 0.083 = 44.82`

(assuming a 30 day month)

Emily would owe `$44.82` for this month. However since Emily is a paid user they receive a `$10` credit which brings Emily's bill down to `$34.82`.

**Charge for compute:**

`$34.82 dollars`

```


```md alert
# Multiple Apps - Multiple Regions 

Fred, a **freelance developer**, built a **portfolio of web applications** that cater to different clients across the globe. He has built **5 apps** where **4 apps** have a small amount of traffic with an average of **0.5 hours a day** and **1 app** that has a high amount of traffic with an average of **6 hours** a day. He has deployed the 4 small traffic apps on a `c1m1` machine in **1 region** each and the high traffic app on a `c1m1` machine in **2 regions**. How much would Fred pay?


**Facts for 4 small traffic apps:**
- **Machine size:** `c1m1` (1 CPU, 1 GB Memory) - `$0.083` per hour  
- **Regions:** `1`  
- **Avg usage per day per region:** `0.5 Hours`


**Facts for 1 large traffic app:**
- **Machine size:** `c1m1` (1 CPU, 1 GB Memory) - `$0.083` per hour  
- **Regions:** `2`  
- **Avg usage per day per region:** `6 Hours`


**Maths:**

4 small traffic apps:

`4 apps * 1 region * 0.5 hours * 30 days = 60 compute hours` 

1 large traffic apps:

`2 regions * 6 hours * 30 days = 360 compute hours` 

Total compute hours = `60 + 360 = 420 compute hours`

`420 * 0.083 = 34.86`

(assuming a 30 day month)

Fred would owe `$34.86` for this month. However since Fred is a paid user they receive a `$10` credit which brings Fred's bill down to `$24.86`.

**Charge for compute:**

`$24.82 dollars`
```

One thing that is important to note is that in the hypothetical example where you have `50 people` using your app `continuously for 24 hours` or if you have `1 person` using your app `continuously for 24 hours`, you `will be charged the same amount` as the charge is based on the amount of time your app up and not the number of users using your app. In `both these examples` your `app is up for 24 hours` and therefore you will be `charged for 24 hours of compute`.