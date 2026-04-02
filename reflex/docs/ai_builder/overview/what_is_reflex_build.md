# What Is Reflex Build

Reflex Build is an AI-powered platform that lets anyone create full-stack web apps just by describing ideas in plain English—no coding needed. It includes a full-fledged built-in IDE, real-time collaboration, and project sharing—all in your browser, no installation required.

```python exec
import reflex as rx


landing_features = [
    {
        "title": "Database Integration",
        "description": "Automatically integrate your database\ninto your application with ease",
        "icon": "database",
    },
    {
        "title": "Secure Secrets",
        "description": "Safely manage your API keys and tokens\nwith a built in secrets manager",
        "icon": "shield",
    },
    {
        "title": "Live Preview",
        "description": "See all application changes in real-time\nwith our interactive preview tab",
        "icon": "eye",
    },
    {
        "title": "Quick Download",
        "description": "Download your complete project files\nwith just a single click operation",
        "icon": "download",
    },
    {
        "title": "Easy Deployment",
        "description": "Deploy your application to production\nwith just a single click process",
        "icon": "rocket",
    },
    {
        "title": "Manual File Editing",
        "description": "Edit your project files directly\nwith our intuitive code editor",
        "icon": "code",
    },
    {
        "title": "AI Package Manager",
        "description": "Let AI handle your package installations\nvia natural prompting",
        "icon": "sparkles",
    },
    {
        "title": "Smart Prompting",
        "description": "Get better development results\nwith AI-optimized prompt templates",
        "icon": "message-circle",
    },
]


features_data = [
    {
        "title": "Project Menu Bar",
        "subtitle": "Browse previously built applications, create new sessions, store database variables, and much more!",
        "img": "https://web.reflex-assets.dev/ai_builder/what_is_reflex_build/project_bar_light.avif",
    },
    {
        "title": "Chat Area",
        "subtitle": "See your prompts in action with visual cues, editing notifications, and file generations every step of the way.",
        "img": "https://web.reflex-assets.dev/ai_builder/what_is_reflex_build/chat_light.avif",
    },
    {
        "title": "Application Workspace",
        "subtitle": "Your workspace contains all the folders and files of your application. You can add new files and folders as well!",
        "img": "https://web.reflex-assets.dev/ai_builder/what_is_reflex_build/file_tree_light.avif",
    },
    {
        "title": "Code Editor",
        "subtitle": "The code editor displays the current selected file. You can edit the code directly and save it instantly.",
        "img": "https://web.reflex-assets.dev/ai_builder/what_is_reflex_build/code_light.avif",
    },
    {
        "title": "Integrations",
        "subtitle": "Easily connect with the tools your team already uses or extend your app with any Python SDK, library, or API.",
        "img": "https://web.reflex-assets.dev/ai_builder/what_is_reflex_build/integrations_light.avif",
    },
    {
        "title": "Plan",
        "subtitle": "Plan your application's development with the AI Builder. You can add or remove phases and tasks as you go.",
        "img": "https://web.reflex-assets.dev/ai_builder/what_is_reflex_build/plan_light.avif",
    },
    {
        "title": "Top Menu Bar",
        "subtitle": "This menu contains the main views of the application. Preview, Code, Plan, Integrations, Knowledge, Secrets and Settings. You can also see the current workspace RAM and CPU usage. Deploy, copy or share your application with the buttons in the top right corner.",
        "img": "https://web.reflex-assets.dev/ai_builder/what_is_reflex_build/top_light.avif",
    },
    {
        "title": "Preview Tab",
        "subtitle": "The preview tab showcases a live application. You can navigate to other applications directly from this tab, refresh the app, and even view it in full screen.",
        "img": "https://web.reflex-assets.dev/ai_builder/what_is_reflex_build/preview_light.avif",
    },
]


def feature_card(feature: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                rx.icon(
                    tag=feature["icon"],
                    size=15,
                    class_name="inline-block mr-2 text-primary-11",
                ),
                rx.el.span(f"{feature['title']}"),
                class_name="text-sm font-semibold flex flex-row items-center pt-5 px-2 text-secondary-12",
            ),
            rx.el.span(
                feature["description"],
                class_name="text-sm font-medium block align-center px-2 text-secondary-11",
            ),
            class_name="flex flex-col gap-2",
        ),
        class_name="w-full rounded-md",
    )


def _docs_features() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.foreach(landing_features, feature_card),
            class_name="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-2 gap-4",
        ),
        class_name="flex flex-col w-full h-full justify-start align-start items-start py-4 gap-x-4 z-[99]",
    )


def _docs_app_section_features_small_screen(feature: dict):
    return rx.el.div(
        rx.image(
            src=feature["img"],
            class_name="rounded-md h-auto",
            border=f"0.81px solid {rx.color('slate', 5)}",
        ),
        rx.el.div(
            rx.el.label(
                feature["title"], class_name="text-sm font-bold cursor-pointer"
            ),
            rx.el.label(
                feature["subtitle"], class_name="text-sm font-light cursor-pointer"
            ),
            class_name="flex flex-col px-1 py-2",
        ),
        class_name="w-full flex flex-col rounded-md",
    )


def _docs_app_section_toggles(feature: dict):
    return rx.el.div(
        rx.el.label(feature["title"], class_name="text-sm font-bold"),
        rx.el.label(feature["subtitle"], class_name="text-sm font-light"),
        class_name="w-full flex flex-col max-w-md rounded-md p-4",
    )


def _docs_app_sections():
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.label(
                    "Small details, big impact", class_name="text-sm font-light"
                ),
                rx.el.label(
                    "Made With Exceptional Care", class_name="text-3xl font-bold"
                ),
                rx.el.label(
                    "Every feature in Reflex Build is carefully crafted to set new standards. Mediocre isn't an option.",
                    class_name="text-md font-regular",
                ),
                class_name="flex flex-col w-full max-w-lg gap-y-1",
            ),
            rx.foreach(
                features_data[:5],
                lambda feature: _docs_app_section_toggles(feature),
            ),
            class_name="flex flex-col gap-y-4 justify-start max-w-sm",
        ),
        rx.el.div(
            rx.image(
                src=features_data[0]["img"],
                class_name="rounded-md h-auto",
                border=f"0.81px solid {rx.color('slate', 5)}",
            ),
            class_name="w-full max-w-4xl",
        ),
        class_name="flex flex-row w-full h-full justify-between align-center items-center py-4 gap-x-4 z-[99]",
        display=["none" if i <= 4 else "flex" for i in range(6)],
    )


def _docs_app_sections_small_screen():
    return rx.el.div(
        rx.el.div(
            rx.grid(
                rx.foreach(
                    features_data,
                    lambda feature: _docs_app_section_features_small_screen(feature),
                ),
                class_name="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-10 w-full",
            ),
            class_name="flex flex-col gap-y-4 justify-start py-4",
        ),
    )


screen_normalization = "z-[99] w-full"
```


## Feature Overview

Reflex Build provides a streamlined interface for building AI applications. The **Project Menu Bar** helps you manage sessions and stored variables, while the **Chat Area** displays real-time prompts, edits, and file generations. The **Application Workspace** organizes your project structure, and the **Code Editor** allows direct, instant code editing. Key actions like deploy and share are accessible via the **Bottom Menu Bar**, and the **Preview Tab** lets you view and interact with your live app at any time.

```python eval
rx.el.div(
    _docs_app_sections_small_screen(),
)
```

## Interface Highlights

Reflex Build’s interface is designed for clarity and efficiency. The **Project Menu Bar** helps you manage sessions, apps, and variables. The **Chat Area** shows prompts in action with visual feedback and file generation. In the **Application Workspace**, you can view and organize your project files. The **Code Editor** allows quick, direct edits with instant saving. Use the **Bottom Menu Bar** for key actions like deploy and download. The **Preview Tab** lets you interact with a live version of your app, including refresh and full-screen options.

```python eval
rx.el.div(
    rx.el.div(_docs_features(), class_name=screen_normalization),
)
```
