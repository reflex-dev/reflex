# Examples

Worked workflows, each rebuilt on `reflex-workflow` and tested against the pass
condition it has to meet. They live beside the package rather than inside it:
they are read and run from the repository, and are not part of the published
wheel.

| | Example | Has to hold |
| --- | --- | --- |
| 01 | [Route new leads](ex01_leads.py) | The same lead twice updates one contact; a lead matching no rule reaches a fallback owner. |
| 02 | [Weekly business update](ex02_weekly_update.py) | The report uses its own timezone and week, marks missing days, and is published once however often the send is retried. |
| 03 | [Client setup after a sale](ex03_client_setup.py) | A folder service outage is retried without a second project or a second welcome. |
| 04 | [Support triage](ex04_support_triage.py) | Urgent requests escalate, uncertain ones wait for a person, and a redelivered webhook opens one ticket. |
| 05 | [Review and publish posts](ex05_social_posts.py) | A rejected post never publishes, an edit is the version that goes out, and a failing channel is retried without reposting to the others. |
| 06 | [Supplier invoices](ex06_invoices.py) | An approval arriving a week later is taken once, and neither a re-uploaded file nor a second click books a second bill. |
| 07 | [Approval with long waits](ex07_long_wait_approval.py) | A wait outlives the worker that started it, a delayed reply is accepted once, and the document is parsed once however often it is revalidated. |
| 08 | [Scheduled sweep](ex08_sweep.py) | Two sweepers at once start one collection per occurrence, a deadline moved forward holds work back, and a burst of signals becomes one collection that still counts them. |
| 09 | [Webhook synchronization](ex09_webhook_sync.py) | A late event does not undo a newer one, a callback outlives the worker that asked for it, and a destination that is down does not erase the ones already written. |
| 10 | [Parallel research](ex10_research.py) | Every company is looked up at once, a failing one retries without rerunning the others, one nobody can research does not hold up the report, and one customer's large import does not stop another's. |
| 11 | [Background job with progress](ex11_background_job.py) | The id is good the moment it is returned, a client that closed the tab reads the same progress as one that watched, and a late stage retries without redoing the finished ones. |
| 12 | [Media pipeline](ex12_media_pipeline.py) | Chunks finish in any order and are assembled in index order exactly once, one chunk retries alone, a chunk nobody can process leaves a gap rather than a hang, and the decoding runs only on workers started for it. |
| 13 | [Conversational agent](ex13_conversation.py) | A burst of messages after a restart is answered in order, one arriving mid-turn gets the next turn, a confirmation clicked twice is one transfer, a failed model call does not repeat the tool before it, and a reply racing the reminder stops it. |

Progress is read from the rows rather than pushed: workers hear about new work
from each other, but nothing tells a connected browser that a row changed.

External services are [a fake provider](services.py) that is idempotent on a key
and can be broken or held back on demand, so outages, slow providers and duplicate
deliveries are exercised rather than described.

Run them against a Postgres the tests may wipe:

```bash
REFLEX_TEST_POSTGRES=postgresql://postgres@127.0.0.1:5432/workflow_examples uv run pytest tests/units/reflex_workflow/examples
```
