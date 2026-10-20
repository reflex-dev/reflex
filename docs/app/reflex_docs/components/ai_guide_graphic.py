"""An illustrated prompt and review cycle for the AI Builder guide."""

import reflex as rx


def ai_guide_graphic() -> rx.Component:
    """Show a focused prompt, its first result, and a specific follow-up."""
    return rx.el.figure(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        rx.icon("sparkles", size=16),
                        rx.el.span("Your prompt"),
                        class_name="flex items-center gap-2 text-xs text-muted-foreground",
                    ),
                    rx.el.div(
                        "Create an employee directory with name, team, and status. Start with sample data.",
                        class_name="mt-5 text-base font-book leading-7 tracking-tight text-foreground",
                    ),
                    class_name="min-w-0 self-center rounded-xl border border-border bg-background p-5 sm:p-6",
                ),
                rx.el.div(
                    rx.el.div(
                        rx.el.div(
                            *[
                                rx.el.span(
                                    class_name="size-1 rounded-full bg-subtle-foreground"
                                )
                                for _ in range(3)
                            ],
                            class_name="flex gap-1",
                        ),
                        rx.el.span(
                            "Preview", class_name="text-xs text-muted-foreground"
                        ),
                        rx.icon(
                            "panel-top", size=13, class_name="text-subtle-foreground"
                        ),
                        class_name="flex items-center justify-between border-b border-border px-4 py-3",
                    ),
                    rx.el.div(
                        rx.el.div(
                            "Our team",
                            class_name="text-lg font-book tracking-tight text-foreground",
                        ),
                        rx.el.div(
                            "People across your organization",
                            class_name="mt-1 text-xs leading-5 text-muted-foreground",
                        ),
                        rx.el.div(
                            *[
                                rx.el.div(
                                    rx.el.span(
                                        initials,
                                        class_name="flex size-8 shrink-0 items-center justify-center rounded-full bg-[var(--fw-tint)] text-[10px] font-book text-[var(--fw-accent)]",
                                    ),
                                    rx.el.div(
                                        rx.el.div(
                                            name,
                                            class_name="text-xs font-book text-foreground",
                                        ),
                                        rx.el.div(
                                            team,
                                            class_name="mt-1 text-[11px] text-muted-foreground",
                                        ),
                                        class_name="min-w-0 flex-1",
                                    ),
                                    rx.el.span(
                                        "Active",
                                        class_name="text-[10px] text-[var(--fw-accent)]",
                                    ),
                                    class_name="flex items-center gap-3 border-t border-border py-3",
                                )
                                for initials, name, team in (
                                    ("AM", "Alex Morgan", "Engineering"),
                                    ("JC", "Jamie Chen", "Design"),
                                    ("SR", "Sam Rivera", "Operations"),
                                )
                            ],
                            class_name="mt-5",
                        ),
                        class_name="p-4 sm:p-5",
                    ),
                    class_name="min-w-0 overflow-hidden rounded-xl border border-border bg-background",
                ),
                style={
                    "grid_template_columns": "repeat(auto-fit, minmax(min(100%, 220px), 1fr))"
                },
                class_name="grid w-full items-center gap-5 sm:gap-6",
            ),
            rx.el.div(
                rx.icon(
                    "corner-up-right",
                    size=16,
                    class_name="shrink-0 text-[var(--fw-accent)]",
                ),
                rx.el.div(
                    rx.el.span(
                        "Next prompt", class_name="block text-xs text-muted-foreground"
                    ),
                    rx.el.span(
                        "Keep the layout. Add a filter for each team.",
                        class_name="mt-1 block text-sm leading-6 text-foreground",
                    ),
                ),
                class_name="mt-5 flex w-full items-center gap-3 rounded-xl border border-border bg-background px-5 py-4 sm:mt-6",
            ),
            aria_hidden=True,
            class_name="docs-framework-stage flex-col !p-4 sm:!p-7",
        ),
        role="img",
        aria_label="Build in focused steps: ask for an employee directory with sample data, review the first version, then ask to add a team filter while keeping the layout.",
        custom_attrs={"data-tone": "lavender"},
        class_name="docs-ai-guide-graphic docs-framework-panel my-8 min-w-0 overflow-hidden rounded-panel border border-border",
    )
