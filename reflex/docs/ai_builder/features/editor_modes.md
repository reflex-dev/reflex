# Editor Modes

The AI Builder includes a powerful dual-mode editor that lets you view and edit your application code while tracking changes made by the AI. You can seamlessly switch between **Editor Mode** for manual code editing and **Diff Mode** for reviewing AI-generated changes.


```python exec
import reflex as rx


def render_image():
    return rx.el.div(
        rx.image(
            src="https://web.reflex-assets.dev/ai_builder/features/diff_light.avif",
            class_name="rounded-md h-auto",
            border=f"0.81px solid {rx.color('slate', 5)}",
        ),
        class_name="w-full flex flex-col rounded-md",
    )
```

```python eval
rx.el.div(render_image())
```
## Modes: Editor vs Diff

### Editor Mode
The standard code editor where you can:
- **Write and modify code** directly in the interface
- **Navigate through files** using the file tree
- **Make manual changes** to your application
- **Save your modifications** which persist across sessions

### Diff Mode
A specialized view that highlights changes from the last AI prompt:
- **Green highlights** show code additions made by the AI
- **Red highlights** show code deletions made by the AI
- **Side-by-side comparison** of what changed
- **Line-by-line tracking** of modifications

## Switching Between Modes

### Toggle Controls
Located in the editor toolbar, you'll find:
- **Editor** button - Switch to normal editing mode
- **Diff** button - Switch to change tracking mode

### When to Use Each Mode
- **Use Editor Mode when:**
  - Making manual code changes
  - Writing new functionality
  - Debugging or fixing issues
  - General code development

- **Use Diff Mode when:**
  - Reviewing what the AI changed after a prompt
  - Understanding modifications before accepting them
  - Tracking the impact of AI suggestions
  - Learning from AI-generated code patterns

## Understanding Diff Visualizations

### Code Highlighting
**Additions (Green):**
- New code lines added by the AI
- New functions, components, or logic
- Enhanced features and improvements

**Deletions (Red):**
- Code removed by the AI
- Replaced or refactored sections
- Deprecated functionality

### File Tree Indicators
The file tree shows change statistics for each modified file:

**Change Indicators:**
- **`+5`** - 5 lines added to this file
- **`-3`** - 3 lines removed from this file
- **`+12 -8`** - 12 lines added, 8 lines removed
- **No indicator** - File unchanged

**Visual Cues:**
- **Green `+` symbol** indicates files with additions
- **Red `-` symbol** indicates files with deletions
