---
meta_description: Build internal tools and business apps with Reflex Build, an AI app builder for Python. Explore vibe coding, editable source, integrations, testing, and deployment.
---

# What Is Reflex Build?

Reflex Build is an AI app builder for creating full-stack web apps with natural language and Python. It combines an AI agent, a running preview, a code workspace, testing, integrations, and deployment in one browser-based workflow.

This workflow is often called **vibe coding**: describing what you want in plain language, then reviewing and refining the generated app. Use it to build internal tools, dashboards, and business apps with editable Python code.

The result is a standard Reflex app with source code you can inspect, edit, connect to Git, download, and deploy.

## Key takeaways

- Turn a natural-language description into a running, editable full-stack app.
- Keep the standard Reflex project, with Python source you can inspect, download, and extend.
- Connect business tools to databases, authentication providers, APIs, storage, and AI models.
- Start as a nontechnical founder or operator, then work with a developer on the same codebase.
- Test, debug, and customize the first version before deploying it for real users.

## Vibe coding vs. traditional development

| Workflow | Reflex Build (vibe coding) | Traditional development |
| --- | --- | --- |
| Starting point | Describe the app or change in natural language | Write code, starting from a template or existing project |
| First version | The agent generates code and a running preview | A developer implements and runs the app |
| Code ownership | Downloadable, editable Reflex project | Source code in your project |
| Who can start | Nontechnical founders, operators, and developers | Developers working in their preferred tools |
| Iteration | Follow-up prompts, direct code edits, and tests | Code edits, developer tools, and tests |

## Describe, Build, Test, and Ship

Start with a prompt that describes the app or change you need. Builder can then plan the work, update the source, run the app, and show the result in **Preview**.

When a task needs more context, the agent can search the web, run Python, or generate an image. See [Agent Tools](/docs/ai/features/agent-tools/) for when and how those tools are used.

A typical workflow is:

1. Describe one clear outcome and include any useful screenshots, files, or constraints.
2. Review the plan when the work spans several pages, systems, or files.
3. Let the agent implement the change and follow its progress.
4. Test the result in **Preview** and send focused follow-up instructions.
5. Add or run tests for the workflows that matter.
6. Deploy, share, download, or continue developing the app locally.

For a guided example, follow [Your First Reflex Build App](/docs/ai/overview/tutorial/). For prompting and review guidance, see [Reflex Build Best Practices](/docs/ai/overview/best-practices/).

## Production Python Code You Own

Builder generates a regular Reflex project rather than an opaque hosted artifact. The project contains the Python application code, assets, dependency definitions, and Reflex configuration needed to run it.

Use **Code** to browse, search, and edit the source. You can also:

- Connect the app to GitHub or connect its project to another Git provider.
- Download the source and continue development with your own tools.
- Install Python packages when the app needs an external library.
- Use checkpoints and Git history to understand or recover earlier changes.

See [Code and Review](/docs/ai/features/editor-modes/), [Connecting to GitHub](/docs/ai/features/connect-to-github/), and [Download App](/docs/ai/app-lifecycle/download-app/) for the relevant workflows.

## Testing Is Built In

Ask the agent to create unit or browser tests in plain language. You can run one test or the full suite, inspect failures, and ask the agent to fix the underlying behavior.

Tests help catch regressions as the app changes, but they do not replace checking the primary workflow with realistic data in **Preview**. See [Automated Testing](/docs/ai/features/automated-testing/).

Before deployment, the [Security Scanner](/docs/ai/features/security-scanner/) can check the source and dependencies for common security issues.

## Connect to Your Systems

Builder can work with databases, authentication providers, APIs, storage services, AI models, and other external systems.

- Use a packaged integration for a supported service.
- Create a custom integration for internal APIs, shared context, or credentials.
- Add MCP servers when the agent needs access to another tool.
- Install an ordinary Python package when no dedicated integration is required.
- Store credentials in integrations or **Secrets**, not in prompts or source code.

Only enable the services an app needs. See [Integrations](/docs/ai/features/integration-shortcut/), [Installing External Packages](/docs/ai/features/installing-external-packages/), and [Secrets](/docs/ai/features/secrets/).

## Work with Your Team

An organization contains projects, and each project contains apps. This structure keeps apps, integrations, knowledge, repositories, deployments, and access controls together for a team.

Organizations and projects support members, teams, standard and custom roles, deployment approvals, and audit logs. Developers can work in Builder or through a connected repository while using the same app source.

Start with [Organizations](/docs/ai/organization/overview/) for the hierarchy, [Project Overview](/docs/ai/overview/project-overview/) for project-level resources, and [Roles and Permissions](/docs/ai/organization/roles-and-permissions/) for access control.

## Review Every Change

Use **Preview** after every meaningful step. When feedback applies to a specific part of the interface, use **Review mode** to draw on the page, add comments, and send the annotations to the agent.

For larger changes, review the plan before implementation. If a result moves in the wrong direction, inspect the changed files or restore an earlier checkpoint instead of asking the agent to rebuild the entire app.

See [Planning](/docs/ai/features/planning/), [Generation Controls and Collaboration](/docs/ai/features/generation-controls/), and [Restore a Checkpoint](/docs/ai/features/restore-checkpoint/).

## Deploy Where You Need It

Deploy an app to Reflex Cloud from Builder, deploy from the command line, or follow the supported cloud and self-hosting workflows. After deployment, you can monitor status and logs, manage domains and settings, review deployment history, and roll back when necessary.

See [Deploy an App](/docs/ai/app-lifecycle/deploy-app/), [Manage a Deployed App](/docs/hosting/app-management/), and [Cloud Providers](/docs/hosting/cloud-providers/).

<!-- faqs-start -->
<!-- faqs-visible -->

## FAQ

### What is the best AI app builder for a nontechnical founder building a business tool?

Reflex Build is an option for founders who want to describe a business tool in plain language and keep an editable Python app. It supports connections to real data and services, and a developer can extend the standard Reflex codebase later. Review and test the generated workflows before using them in production.

### Can an AI app builder modify an app it already generated, not just create new ones?

Yes. Reflex Build supports iterating on a generated app after the first version: refining logic, adding features, and adjusting the UI through the same natural-language workflow, with full code access at every step.

### How does Reflex compare with other AI app-building platforms?

Reflex Build combines natural-language development with a standard, exportable Reflex project. Teams can inspect and edit the Python source, connect Git, download the app, and continue development locally. Compare platforms on their source access, integrations, testing, and deployment options for your workflow.

<!-- faqs-end -->
