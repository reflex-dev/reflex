"""Overview of deploying and operating Reflex applications."""

from reflex_docs.docgen_pipeline import render_markdown
from reflex_docs.templates.docpage import docpage

CLOUD_OVERVIEW_MARKDOWN = """# Reflex Cloud Overview

Reflex Cloud hosts your Reflex application so other people can use it on the web.
Start with an app that runs locally, deploy it to a project, and use the hosting
tools to configure and monitor it.

## Deploy your first app

Follow the [deployment quick start](/docs/hosting/deploy-quick-start/) to sign in,
find your project's deploy command, and publish your app. The guide covers the
required Python dependencies and the interactive deployment workflow.

For command options and automation, use the [deploy command reference](/docs/hosting/cli/deploy/)
and the [GitHub Actions deployment guide](/docs/hosting/deploy-with-github-actions/).

## Configure your deployment

- [Secrets and environment variables](/docs/hosting/secrets-environment-vars/): configure API keys and other values used by your app.
- [Custom domains](/docs/hosting/custom-domains/): connect a domain to your deployment.
- [Regions](/docs/hosting/regions/): choose where to run your application.
- [Compute](/docs/hosting/compute/): choose resources for your workload.
- [Cloud configuration](/docs/hosting/config-file/): manage deployment settings in a configuration file.

## Monitor and manage your app

Use [application management](/docs/hosting/app-management/) to manage deployments
and [logs](/docs/hosting/logs/) to investigate application behavior. Run a
[security scan](/docs/hosting/security-scan/) to review your app source for
security and logic issues.

## Choose where to host

If you need to run in your own environment, compare
[bring your own cloud](/docs/hosting/bring-your-own-cloud/) with
[self-hosting](/docs/hosting/self-hosting/). These guides explain the available
workflows and the setup each requires.
"""

cloud_overview = docpage(
    "overview/",
    "Cloud Overview",
    description="Deploy a Reflex app, configure secrets and domains, monitor logs, and compare Reflex Cloud with bring-your-own-cloud and self-hosting options.",
)(lambda: render_markdown(CLOUD_OVERVIEW_MARKDOWN))
cloud_overview.title = "Overview"
cloud_overview.seo_title = "Reflex Cloud Overview · Reflex Docs"
pages = [cloud_overview]
