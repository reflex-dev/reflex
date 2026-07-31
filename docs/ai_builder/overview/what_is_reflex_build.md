# What Is Reflex Build

Reflex Build is an AI-powered workspace for creating full-stack web apps from natural-language prompts. You can plan an app, generate and edit its code, preview it, connect external services, test it, and share or deploy it from your browser.

```python exec
import reflex as rx
```

## Start in Builder

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/builder_dashboard.webp",
    alt="Reflex Build dashboard with the app creation prompt",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

Open a project and select **Builder**. From the create screen, describe the first useful version of your app. You can also:

- Attach screenshots or other reference files.
- Choose a design system and app visibility.
- Add an integration before generation starts.
- Adjust **Agent Effort** and whether the agent should **Plan first**.
- Use web search, Python, or image generation when the task needs them.
- Start from one of your existing apps or a template.

## The App Workspace

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/app_preview.webp",
    alt="A generated app open in the Reflex Build Preview workspace",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

After you create or open an app, the workspace keeps the conversation and the current app side by side.

| Area | What you can do |
| --- | --- |
| **Preview** | Run the current app, switch routes, and interact with the result. Use it after each meaningful change to check behavior, layout, and responsive states. |
| **Review mode** | Draw on the preview, add comments to specific UI areas, and send the annotated screenshots to the agent as one focused review. |
| **Code** | Browse, search, edit, and lock files; inspect generated diffs; and use Git, Terminal, and Debug tools. Manual editing requires the appropriate plan and app access. |
| **Plan** | Review and edit a task plan before or during generation. Use **Plan first** on the create screen or in chat controls to decide when the agent must prepare one. |
| **Integrations** | Connect databases, authentication, AI providers, business services, and other data sources used by the app. |
| **Testing** | Generate unit or browser tests from plain language, run one test or the full suite, and inspect failures. |
| **Deploy** | Configure a Reflex Cloud or connected-cloud deployment. If the project requires approval, submit the deployment to the approval queue. |

The more menu contains secondary app actions and settings, including [Knowledge](/docs/ai/features/knowledge/), [Secrets](/docs/ai/features/secrets/), app **Settings**, and actions to copy, download, share, or manage the app. The exact actions shown depend on your role and the app state.

## The Project Platform

Reflex Build also provides project-level tools outside an individual app:

| Area | What it manages |
| --- | --- |
| [Deployments](/docs/hosting/deploy-quick-start/) | Hosted apps, status, logs, history, domains, and providers |
| [Agent Toolkit](/docs/ai/features/agent-toolkit/) | MCP and Reflex Agent Skills for local coding assistants |
| [Security Scanner](/docs/ai/features/security-scanner/) | Pre-deployment security and dependency checks |
| [Integrations](/docs/ai/features/integration-shortcut/) | External services, private data connections, and MCP servers |
| [Knowledge](/docs/ai/features/knowledge/) | Project-wide context and conventions |
| [Design Systems](/docs/ai/features/design-systems/) | Shared visual rules generated from guidance and references |
| [Repos](/docs/ai/features/connect-to-git-providers/) | GitHub, GitLab, Bitbucket, Azure DevOps, and other Git remotes |
| [Members and Roles](/docs/ai/organization/roles-and-permissions/) | Project access and granular permissions |
| [Templates](/docs/ai/overview/templates/) | Reusable app starting points for projects and organizations |
| [Approvals](/docs/ai/organization/deployment-approvals/) | Required review before deployments or project membership changes |
| [Audit Logs](/docs/ai/organization/audit-logs/) | Searchable project and organization activity |

Projects belong to an [organization](/docs/ai/organization/overview/). Organization settings control members, seats, teams, roles, tokens, verified domains, single sign-on, shared templates, audit activity, billing, and connected cloud providers.

## A Typical Build Loop

1. Describe one clear outcome in the chat.
2. Let the agent plan when the task affects several pages, files, or systems.
3. Check the result in **Preview**. Use **Review mode** when feedback applies to a specific part of the interface.
4. Give or queue focused follow-up instructions instead of regenerating the whole app.
5. Add or rerun tests for the workflows that matter.
6. Use the menu next to **Deploy** to copy, download, or share the app, or deploy it when it is ready.

For a guided example, continue with [Your First Reflex Build App](/docs/ai/overview/tutorial/).
