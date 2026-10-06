# reflex-hosting-cli
Hosting CLI for Reflex.

When an app is still scaling, `reflex deploy` waits 15 seconds between confirmed
scaling refusals, for up to 7 retries to update instance bounds and 11 retries
to submit the deployment. The CLI reports each wait, and you can cancel
with Ctrl-C. Submission retries reuse the uploaded build. The SDK's usual safe
retries can add two more submission attempts, for up to 14 attempts in total;
they do not restart the scaling wait budget. Other failures, including a lost
submission response, are reported without replaying an uncertain write.
If an instance-bounds write has an uncertain outcome, including a server error,
the CLI warns that the bounds may have changed.
