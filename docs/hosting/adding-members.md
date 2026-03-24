```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
from reflex_image_zoom import image_zoom
```

# Project

A project is a collection of applications (apps / websites).

Every project has its own billing page that are accessible to Admins.



## Adding Team Members

To see the team members of a project click on the `Members` tab in the Cloud UI on the project page. 

If you are a User you have the ability to create, deploy and delete apps, but you do not have the power to add or delete users from that project. You must be an Admin for that.

As an Admin you will see the an `Add user` button in the top right of the screen, as shown in the image below. Clicking on this will allow you to add a user to the project. You will need to enter the email address of the user you wish to add.

```python eval
image_zoom(rx.image(src=f"{REFLEX_ASSETS_CDN}other/hosting_adding_team_members.webp", alt="Adding team members to Reflex Cloud"))
```

```python eval
rx.box(height="20px")
```

```md alert warning
# Currently a User must already have logged in once before they can be added to a project. 
At this time a User must be logged in to be added to a project. In future there will be automatic email invites sent to add new users who have never logged in before.
```


## Other project settings

Clicking on the `Settings` tab in the Cloud UI on the project page allows a user to change the `project name`, check the `project id` and, if the project is not your default project, delete the project.