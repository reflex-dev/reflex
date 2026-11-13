# reflex-hosting-cli
Hosting CLI for Reflex.

When an app is still scaling, `reflex deploy` waits 15 seconds between confirmed
scaling refusals, for up to 7 retries to update instance bounds and 11 retries
to submit the deployment. The CLI reports each wait, and you can cancel
with Ctrl-C. Submission retries reuse the uploaded build. The SDK's usual safe
retries can add two more submission attempts, for up to 14 attempts in total;
they do not restart the scaling wait budget. The scaling sleeps total at most
165 seconds for submission; requests and SDK backoff add to elapsed time.
Other failures, including a lost submission response, are reported without
replaying an uncertain write.
If an instance-bounds write has an uncertain outcome, including a server error,
the CLI warns that the bounds may have changed.
A success response that cannot be decoded also stops deployment with a separate
warning about bounds left changed.

If an access token is expired or rejected, run `reflex login` to authenticate
again. If you supply a token explicitly, replace it with a valid token or remove
the override before using the saved login: unset `REFLEX_ACCESS_TOKEN` or omit
`--token`. Logging in does not replace an environment variable or command-line
token. Noninteractive commands exit on rejection without opening a browser.
