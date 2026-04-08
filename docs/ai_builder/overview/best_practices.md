# Reflex Build: Best Practices

> A comprehensive guide to working effectively with AI Builder. This guide outlines how to get the most reliable and efficient results when working with the AI Builder inside Reflex Build. The key to success is clarity, structure, and iteration.

---

## Core Workflow

### Foundation: Planning Before You Build

Before jumping into the AI Builder, take time to plan your approach. Good preparation leads to better results and fewer iterations.

- **Define your core purpose and users** — Write a 2-3 sentence app description and identify your target users and their needs.
- **Prioritize 3-5 key features** — Focus on the most important functionality first, then expand from there.
- **Gather visual references** — Collect screenshots, wireframes, or sketches of layouts you want to emulate.
- **Structure your data** — List what information each page needs to display and how users will interact with it.
- **Start with your most important page** — Usually your main dashboard, home screen, or primary workflow. Get this right first.

### Auto-Generate Prompts from App Specs

To save time and get higher-quality prompts, you can feed your full app spec into the AI Builder and ask it to break the spec into structured, build-ready prompts.

The AI Builder can translate your vision into:

- Layout instructions
- UI component definitions
- Data model requirements
- Styling preferences
- Follow-up test plans

**Example workflow:**

1. Paste your full app specification into the AI Builder
2. Ask **"Break this into a series of buildable prompts."**
3. Execute each generated prompt in sequence
4. Build iteratively using the structured prompts

### Working with Text Specifications

If you have a structured app specification, don't paste the entire document into the builder at once. Break it down into logical sections and feed them in sequence.

**Pro tip:** Let the AI Builder help prepare prompts:

Paste your full app spec and ask:

  - **"Break this into buildable prompts."**
  - **"Write one prompt per feature/page to build this app."**

This approach — planning first, then building iteratively — lets you move faster and build smarter.

### Writing Clear, Task-Oriented Prompts

The AI performs best when it receives **specific, outcome-driven instructions**. Avoid vague, broad prompts.


```diff
- Build me an admin dashboard. # <- Bad
+ Create a 2-column layout with a sidebar for navigation and a top navbar. # <- Good
```

Whenever possible, split large tasks into smaller steps:

- Define the layout first (columns, rows, sidebar)
- Add UI components (buttons, inputs, modals)
- Handle data models and states later
- Use follow-ups to style and polish

Use precise styling language, for example:

```diff
- Grid items have small spacing and sharp corners.
+ Add medium spacing between grid items and use large rounded corners on cards.
```

Avoid subjective terms like "**nice**," "**modern**," or "**clean**." Treat your prompt as interface documentation for the builder.

### Working with Images and Visual References

You can drop in screenshots of websites, dashboards, apps, or even hand-drawn wireframes. The builder will extract layout, design, and functionality ideas from these images.

**Tips for images:**

- Clear screenshots work best
- Include any elements you want: forms, tables, nav, charts
- You can annotate them with arrows, notes, or labels

**Get UI/UX feedback:**

Upload a screenshot and ask: **"What are 5 things I could do to improve the UI/UX of this?"**

Follow up with: **Implement items 1, 2, and 4.**

Or request specific improvements: **Make this more minimal and mobile-first.**

---

## Optimizing Your Workflow

### Building Iteratively

Trying to generate your full app in a single prompt almost never works well. Instead, approach your build in clear stages:

1. **Layout** — Grid, Flex, responsive columns/rows
2. **Components** — Tables, buttons, modals, charts, etc.
3. **State** — Bindings, stores, mock data
4. **Refinement** — Tweaks, visual polish, edge case handling

At each stage, give feedback and iterate. If the AI builder makes something close, you can say:

```diff
- Modal is included and sidebar is static.
+ Remove modal and make sidebar collapsible.

- Buttons vary across pages.
+ Use same button style from home page.

- Card layout differs across sections.
+ Repeat card layout from dashboard section.
```


### Improving UI/UX

To improve your design, ask the builder for more polished layouts, better structure, or more modern styles.

```diff
- Layout feels cluttered with small headings and dense sections.
+ Increase heading sizes and spacing between sections for better hierarchy.

- Navigation buttons are inconsistent.
+ Standardize button sizes and colors for consistent UX.
```

**Suggested workflow:**

1. Upload an image or describe the layout.
2. Ask: **"Tell me 5 things that would improve the UI/UX of this page."**
3. Review the suggestions and decide which ones you want to apply.
4. Implement: **"Improve visual hierarchy by increasing heading sizes and adding more spacing between sections."**

### Using Knowledge to Guide the Build

The **Knowledge** panel lets you provide long-form references that influence how the agent builds your app. Add design systems, style guides, brand guidelines, or architecture rules.

Once added, the builder will try to honor these rules throughout the session, ensuring consistency without repeating instructions.

Try combining Knowledge with your prompts:

  - **Use the style guide in Knowledge to improve this page.**

  - **Is the current layout aligned with our design system in Knowledge?**


### Local Development Integration

We have an MCP server available for enterprise customers to connect local AI development tools such as Claude Desktop, Windsurf, or Codex.

This enables a hybrid workflow: generate your app and make major changes in the App Builder, then move to local development for detailed refinements and custom functionality.

> **Enterprise Feature:** The Reflex MCP integration is currently only available for enterprise customers. [Book a demo](https://reflex.dev/pricing/) to discuss access.

#### Quick Setup

**Prerequisites:**

- MCP-compatible AI tool (Claude Desktop, Windsurf, Codex)
- Valid Reflex account for OAuth authentication
- Internet connection to the hosted MCP server

**Benefits:**

- **Seamless handoff** — Move between web builder and local development
- **AI-powered local development** — Use your preferred AI tools with Reflex projects
- **No local installation** — Hosted MCP server requires no additional Python packages
- **Secure authentication** — OAuth 2.1 integration with your Reflex account

For complete setup instructions for Claude Desktop, Windsurf, Codex, and other MCP clients, visit our [MCP integration](https://reflex.dev/docs/ai-builder/integrations/mcp-installation/) documentation.

---

## Key Takeaways

- **Plan before you build**. A few minutes of preparation saves hours of iteration.
- **Think modularly**. Focus on atomic parts before the full system.
- **Write like a designer-developer**. Clear, structural, and functional language wins.
- **Iterate continuously**. Let each prompt get you 80% there, then refine.

With these techniques, the AI Builder becomes a reliable extension of your creative and technical intent.
