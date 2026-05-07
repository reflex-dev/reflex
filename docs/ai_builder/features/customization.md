# App Style Customization

## Overview

The App Style feature allows you to customize the visual appearance of your AI-generated applications. You can choose from predefined design themes or create custom styling to match your brand and preferences.

## How to Use

1. **Access the Feature**: Click on the App Style option to open the customization panel
2. **Choose Your Approach**:
   - **Custom**: Manually configure individual design elements
   - **Themes**: Select from professionally designed templates

## Custom Styling Options

```python exec
import reflex as rx
```

```python eval
rx.el.div(
    rx.image(
        src=rx.color_mode_cond(
            "https://web.reflex-assets.dev/ai_builder/features/style_light.webp",
            "https://web.reflex-assets.dev/ai_builder/features/style_dark.webp",
        ),
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

When using Custom mode, you can adjust:

- **Primary Color**: Choose your main brand color from 20+ preset options
- **Secondary Color**: Select a complementary color for accents
- **Typography**: Pick a font family for your app
- **Border Radius**: Control how rounded corners appear
- **Shadows**: Add depth with shadow effects
- **Spacing**: Adjust the spacing between elements

## Themes

These options are predefined popular themes you can choose for your app. Below are some of the available themes you can choose from

```python eval
rx.el.div(
    rx.image(
        src=rx.color_mode_cond(
            "https://web.reflex-assets.dev/ai_builder/features/theme_light.webp",
            "https://web.reflex-assets.dev/ai_builder/features/theme_dark.webp",
        ),
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

- **Minimal Design**: Clean, geometric design with no shadows or gradients
- **Modern UI**: Sleek, contemporary interface optimized for performance
- **Carbon Design**: Enterprise-grade design following IBM's Carbon system
- **Material Design**: Google's design language with elevation and semantic colors
