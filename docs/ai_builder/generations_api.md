---
tags: AI Builder
description: Create apps and follow-up changes from code with the generations API, then poll or stream each run, read the thread's messages, and stop a run.
---

# Generations API

The generations API runs the AI Builder agent from your own code. One request creates a new app or sends a follow-up prompt to an existing one. You then follow the run by polling or over server-sent events, read what the agent wrote, and stop the run if you need to.

A **generation** is one agent run, started by one prompt. A **thread** is the conversation behind one app. Every generation belongs to a thread, and a thread runs at most one generation at a time.

## Base URL and authentication

Every path on this page is relative to `$REFLEX_URL/api/v1`. On Reflex-hosted, `$REFLEX_URL` is `https://build.reflex.dev`. On a self-hosted install it is the origin your users reach the product at.

Send an API token in the `X-API-Token` header. `Authorization: Bearer <token>` is accepted too, and `X-API-Token` wins if both are present. A missing or invalid token is refused with 401.

```bash
export REFLEX_URL=https://build.reflex.dev
export REFLEX_TOKEN=<your token>
```

- **Personal token.** Create one in account settings, or use the one `reflex login` stores. It acts as you.
- **Service account token.** For automation, use a [service account](/docs/ai/organization/service-accounts/) and mint its token as shown in [Automated Provisioning](/docs/ai/organization/automated-provisioning/). It acts as the service account, so the account needs a role on each project it builds in.

A token restricted with `access` needs write access to both projects and threads to create a generation, for example `{"permissions": {"project": "write", "thread": "write"}}`. The token's organization is the one that is billed, and a project in another organization is refused with 403.

An app's own platform token, the one a deployed app receives, is refused on every endpoint here.

## Create a generation

`POST /generations` starts a run and answers 201 with the new generation.

### A new app

Omit `thread_id` and give the `project_id` the app is created in. `name` is optional.

```bash
curl -X POST "$REFLEX_URL/api/v1/generations" \
  -H "X-API-Token: $REFLEX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Build a dashboard that tracks weekly signups by plan.",
    "project_id": "<project-uuid>",
    "name": "Signups dashboard"
  }'
```

```json
{
  "id": "6f1c0a52-...",
  "thread_id": "b3e2d9a0-...",
  "status": "queued",
  "detail": null,
  "app_id": null,
  "error_type": null,
  "stop_reason": null,
  "app_has_errors": null,
  "started_at": null,
  "ended_at": null
}
```

Keep `thread_id`. It names the new app's thread, and every follow-up and every transcript read uses it.

### A follow-up

Send `thread_id` and the prompt. Do not send `project_id` or `name`: both describe a new app, so a follow-up that includes either is refused with 422 rather than having it ignored.

```bash
curl -X POST "$REFLEX_URL/api/v1/generations" \
  -H "X-API-Token: $REFLEX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Add a filter for the date range.",
    "thread_id": "<thread-uuid>"
  }'
```

If the thread already has a live generation, the request is refused with 409 and the running generation's id. See [Errors](#errors).

### Body fields

- `prompt` (required): what to build or change. Prompts that are too short or too long are refused with 422, and the message states the limit.
- `project_id`: the project a new app is created in. Required without `thread_id`, refused with it. The older name `project` is still accepted; sending both with different values is refused with 422.
- `thread_id`: the thread to continue. Omit it to create a new app.
- `name`: the new app's name. Refused with `thread_id`.
- `attachments`: files you uploaded first. See [Attachments](#attachments).

### Attachments

Attaching files takes two steps: upload each file to a signed URL, then name it in the create request.

**1. Request upload URLs.** Declare every file with its exact byte size.

```bash
curl -X POST "$REFLEX_URL/api/v1/generations/attachments" \
  -H "X-API-Token: $REFLEX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "attachments": [
      {"name": "mockup.png", "mime_type": "image/png", "size": 48213},
      {"name": "signups.csv", "mime_type": "text/csv", "size": 1290}
    ]
  }'
```

The response has one target per file, in the order declared:

```json
{
  "attachments": [
    {
      "key": "<staging key>",
      "url": "<signed PUT url>",
      "headers": {"Content-Type": "image/png", "...": "..."},
      "name": "mockup.png",
      "mime_type": "image/png",
      "expires_in_ms": 300000
    }
  ]
}
```

The whole batch is checked against the per-message limits on file count, image count, and file size before any URL is issued. A batch over a limit is refused with 422, and the message names the limit.

**2. Upload each file.** `PUT` the file's bytes to `url`, sending every entry in `headers` exactly as given. The signature covers them, and a body whose length differs from the declared `size` is refused by storage. Upload before `expires_in_ms` runs out; the URLs are short-lived, a few minutes by default.

```bash
curl -X PUT "<signed PUT url>" \
  -H "Content-Type: image/png" \
  --data-binary @mockup.png
```

Add any other headers the response listed.

**3. Reference the files.** Pass each file's `key`, `name`, `mime_type`, and `size` in `attachments` on `POST /generations`. A file that does not match what was declared, or was never uploaded, is refused rather than attached.

```json
{
  "prompt": "Build the page in this mockup, using the CSV as sample data.",
  "project_id": "<project-uuid>",
  "attachments": [
    {"key": "<staging key>", "name": "mockup.png", "mime_type": "image/png", "size": 48213}
  ]
}
```

An image reaches the agent as an image. Any other file is written into the app under `assets/`, and the agent is told its path.

### Retries and the Idempotency-Key header

A create request that times out may still have started a run. To retry safely, send an `Idempotency-Key` header with a value you choose, up to 255 characters, and reuse it on every retry of the same request.

```bash
curl -X POST "$REFLEX_URL/api/v1/generations" \
  -H "X-API-Token: $REFLEX_TOKEN" \
  -H "Idempotency-Key: signups-dashboard-2026-11-20" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Build a dashboard that tracks weekly signups by plan.", "project_id": "<project-uuid>"}'
```

- A repeat with the same key and the same body answers the generation the first request made, with its status as it stands now. That may no longer be `queued`.
- A repeat that arrives while the first request is still being processed is refused with 409. Retry shortly.
- A repeat with the same key and a different body is refused with 422. Send the original body, or a new key.
- Keys are scoped to the token's user and organization and kept for 24 hours. A key whose record has expired cannot be reused and is refused with 422.

Use a new key for each new request you mean to make, such as each follow-up prompt.

## Get a generation

`GET /generations/{id}` returns the generation in the same shape the create request answers.

```bash
curl "$REFLEX_URL/api/v1/generations/$GENERATION_ID" \
  -H "X-API-Token: $REFLEX_TOKEN"
```

To wait for a run without a stream, poll this endpoint every few seconds until `status` is no longer a live status. Or use the [event stream](#stream-events).

### Statuses

Live statuses, while the run is in progress:

- `preparing`: the app's sandbox is being set up.
- `queued`: waiting for a worker.
- `running`: the agent is working.
- `pushing`: the agent is saving its changes.

Terminal statuses, once the run has ended:

- `finished`: the run completed.
- `failed`: the run failed. `error_type` says why.
- `stopped`: the run was stopped. `stop_reason` says who stopped it.

Waiting statuses, where the agent stopped to ask something. Each has a `detail` object describing what it asked:

- `awaiting_question`: the agent asked a question. `detail` is `{"questions": [{"question": "...", "options": ["..."]}]}`.
- `awaiting_permission`: the agent asked to run an action that needs approval. `detail` is `{"action", "reason", "category", "code"}`.
- `awaiting_plan`: the agent proposed a plan for approval. `detail` is `{"title": "...", "items": ["..."], "summary": "..."}`.
- `awaiting_integration`: the agent needs an integration connected. `detail` is `{"integrations": ["..."]}`.
- `awaiting_env_vars`: the agent needs environment variables set. `detail` is `{"env_vars": ["..."]}`.
- `awaiting_usage`: the run paused because the organization ran out of usage. `detail` is `{"reason": "..."}`.

Treat `status` as an open set of strings. A future release can add a new `awaiting_` status with its own `detail` shape, so handle any status starting with `awaiting_` as a run waiting for input, and read `detail` by key.

`detail` is null when the run is not waiting. It can also be null on a waiting run whose question could not be read back, so decide on `status`, and treat `detail` as extra information when present.

### Answer a question

Only `awaiting_question` can be answered through this API. Answer it by creating a follow-up generation on the same `thread_id`, with the answer as the prompt:

```bash
curl -X POST "$REFLEX_URL/api/v1/generations" \
  -H "X-API-Token: $REFLEX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Use the Pro and Team plans only.", "thread_id": "<thread-uuid>"}'
```

A prompt sent while the run is in any other `awaiting_` status ends in that same status again. A text reply is not treated as a permission grant, and an integration has to be connected rather than described. Resolve those in the AI Builder.

### Other fields

- `app_id`: the app the thread builds. Null for a thread with no app yet.
- `error_type`: on a `failed` run, a short machine-readable reason. An open set of values, like `status`.
- `stop_reason`: on a `stopped` run, `user` when somebody asked for the stop, otherwise the platform's own reason, such as `queue_timeout`, `worker_lost`, or `superseded`. It is also set on a live run that has been asked to stop and has not stopped yet.
- `app_has_errors`: whether the app the run left behind still has compile errors. Null until the run ends.
- `started_at`: when a worker picked the run up. Null for a run stopped while still queued.
- `ended_at`: when the run reached a terminal status. Null while it is live.

## List a thread's generations

`GET /generations?thread_id=<thread-uuid>` lists the thread's generations, newest first. `limit` defaults to 20 and can be at most 100.

```bash
curl "$REFLEX_URL/api/v1/generations?thread_id=$THREAD_ID&limit=5" \
  -H "X-API-Token: $REFLEX_TOKEN"
```

```json
{"generations": [{"id": "...", "thread_id": "...", "status": "running", "detail": null, "...": "..."}]}
```

Use this when you hold a thread and not a generation id. A thread has at most one live run, so the first entry with a status of `preparing`, `queued`, `running`, or `pushing` is the live one.

`detail` is null on every entry in a list. To read what a waiting run asked, get that generation by id.

## Stream events

`GET /generations/{id}/events` follows a run over [server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html) instead of polling.

```bash
curl -N "$REFLEX_URL/api/v1/generations/$GENERATION_ID/events" \
  -H "X-API-Token: $REFLEX_TOKEN"
```

```text
retry: 3000

event: generation
data: {"id": "...", "thread_id": "...", "status": "running", ...}

event: message
data: {"id": "...", "created_at": "2026-11-20T17:02:11Z", "text": "I'll start with the data model."}

: heartbeat

event: generation
data: {"id": "...", "thread_id": "...", "status": "finished", ...}
```

The stream sends three kinds of item:

- `generation`: the generation, in the same shape `GET /generations/{id}` answers. Sent first, then whenever any field changes.
- `message`: text the agent wrote, in order, as `{"id", "created_at", "text"}`. Tool calls, tool results, and reasoning are not included.
- `: heartbeat`: a comment sent at least every 15 seconds while nothing else is.

On connect, the messages written so far are sent before anything new.

When the run reaches a terminal or waiting status (`finished`, `failed`, `stopped`, or any `awaiting_*`), the stream sends that `generation` event and then closes, so its last event is the run's final state.

The server also closes a stream after 30 minutes, whatever the run is doing. That close comes without a final event, so a stream that ends while the last `generation` event you saw has a live status is not a finished run. Reconnect: the current state is sent first, and a message `id` is stable, so drop messages you already have.

A generation you cannot read is refused with 404 before the stream opens.

## Read a thread's messages

`GET /threads/{thread_id}/messages` returns the thread's transcript, oldest first, one page at a time. It contains the prompts that were sent and the text the agent wrote back, the same messages a person sees in the AI Builder chat.

```bash
curl "$REFLEX_URL/api/v1/threads/$THREAD_ID/messages?limit=50" \
  -H "X-API-Token: $REFLEX_TOKEN"
```

```json
{
  "messages": [
    {"id": "...", "role": "user", "created_at": "...", "text": "Build a dashboard that tracks weekly signups by plan."},
    {"id": "...", "role": "agent", "created_at": "...", "text": "I'll start with the data model."}
  ],
  "next_cursor": "..."
}
```

- `role` is `user` for a prompt and `agent` for the agent's text.
- A prompt that started a generation has that generation's id as its `id`.
- `limit` defaults to 50 and can be at most 200.
- Pass `next_cursor` as `after` to read the next page. A page can be shorter than `limit`, or empty, and still carry a cursor, so keep reading until `next_cursor` is null. An `after` that does not name a message in the thread is refused with 400.

Prompts the platform sends for you, such as an automatic error fix, are left out, as they are in the AI Builder chat. Tool calls, tool results, and file contents are left out too.

Read the transcript after the run has ended. Paging while a generation is still writing can miss a message that lands behind your cursor. To follow a live run, use the [event stream](#stream-events), and read the transcript again from the start once the run ends.

## Stop a generation

`POST /generations/{id}/stop` asks a run to stop and answers the generation as it stands once the stop is recorded.

```bash
curl -X POST "$REFLEX_URL/api/v1/generations/$GENERATION_ID/stop" \
  -H "X-API-Token: $REFLEX_TOKEN"
```

- A queued run is `stopped` at once.
- A running run stops at the worker's next checkpoint, usually within about a second. Poll, or keep following the event stream, until the status is `stopped`. Until then, `stop_reason` is already `user`.
- A run that has already ended is answered with its status rather than an error, so stopping twice is safe.

Stopping needs edit access to the thread. A caller who can see the run but not edit it is refused with 403.

## Errors

Refusals answer a JSON body with a `detail` field, and an `X-Reflex-Error-Code` header with a stable code for the condition.

### 401 and 403

- 401: the token is missing or invalid.
- 403: the token's user may not do this, for example create in that project, stop a run they can only view, or act in a project that belongs to another organization.

### 404: anything you cannot read

A generation or thread that does not exist and one you are not allowed to read get the same 404, so the API does not reveal which ids exist. The same applies to a follow-up on a thread you cannot edit.

```json
{"detail": "No generation with that id was found."}
```

### 409: conflicts

The thread already has a live generation. `detail` is an object, and `generation_id` names the run holding the thread, so you can follow it or stop it. It is null in the rare case the run could not be identified.

```json
{"detail": {"message": "A generation is already running for this thread.", "generation_id": "6f1c0a52-..."}}
```

Every other 409 has a string `detail`:

- A request with the same `Idempotency-Key` is still being processed. Retry shortly.
- An earlier request with the same `Idempotency-Key` left an app this request cannot continue. The message names that app's thread id; send follow-ups to it, or use a new key.
- The thread is archived.
- A browser test is running on the app. Retry when it finishes.

### 422: invalid requests

Two shapes, depending on where the request was refused:

- **Schema validation**, such as a missing `prompt`, a malformed id, or `project_id` sent with `thread_id`. `detail` is a list of errors, each with `loc`, `msg`, and `type`.

  ```json
  {"detail": [{"loc": ["body"], "msg": "Value error, `project_id` cannot be sent with `thread_id`: ...", "type": "value_error"}]}
  ```

- **Rule checks**, such as a prompt outside the length limits, an attachment over a limit, or an `Idempotency-Key` reused with a different body. `detail` is a string.

  ```json
  {"detail": "This Idempotency-Key was already used with a different request body. Send the original body, or a new key."}
  ```

### Other statuses

- 402: the organization is not entitled to run generations, or is out of usage for the current period.
- 503: a temporary failure, such as generations being paused or a sandbox that could not be provisioned. Retry later, with the same `Idempotency-Key` if you sent one.

## End-to-end example

This script creates an app and follows its events for up to 10 minutes. If the run is still going after that, it stops the run and waits for it to end. It then reads the whole transcript, once nothing more can be written to it.

```bash
set -euo pipefail
API="$REFLEX_URL/api/v1"
AUTH=(-H "X-API-Token: $REFLEX_TOKEN")
field() { python3 -c "import json,sys; v=json.load(sys.stdin)[\"$1\"]; print('' if v is None else v)"; }
is_live() { case "$1" in preparing|queued|running|pushing) return 0 ;; *) return 1 ;; esac; }

# 1. Create the app.
created=$(curl -sf -X POST "$API/generations" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d "{\"prompt\": \"Build a todo list app with due dates.\", \"project_id\": \"$PROJECT_ID\"}")
GENERATION_ID=$(echo "$created" | field id)
THREAD_ID=$(echo "$created" | field thread_id)

# 2. Follow the run. The stream ends on its own when the run ends or waits.
curl -sN --max-time 600 "$API/generations/$GENERATION_ID/events" "${AUTH[@]}" || true

# 3. Stop the run if it is still live, and wait until it has ended.
status=$(curl -sf "$API/generations/$GENERATION_ID" "${AUTH[@]}" | field status)
if is_live "$status"; then
  curl -sf -X POST "$API/generations/$GENERATION_ID/stop" "${AUTH[@]}" > /dev/null
  while is_live "$status"; do
    sleep 2
    status=$(curl -sf "$API/generations/$GENERATION_ID" "${AUTH[@]}" | field status)
  done
fi
echo "Run ended with status: $status"

# 4. Read the whole transcript, a page at a time, until next_cursor is null.
after=""
while :; do
  page=$(curl -sf "$API/threads/$THREAD_ID/messages?limit=200${after:+&after=$after}" "${AUTH[@]}")
  echo "$page" | python3 -c 'import json,sys
for m in json.load(sys.stdin)["messages"]:
    print("[%s] %s\n" % (m["role"], m["text"]))'
  after=$(echo "$page" | field next_cursor)
  [ -n "$after" ] || break
done
```

If the run ended in `awaiting_question`, read the questions from `detail` on `GET /generations/{id}` and answer with a follow-up on `$THREAD_ID`, as in [Answer a question](#answer-a-question).

## Related

- [Service Accounts](/docs/ai/organization/service-accounts/): an organization-owned identity for automation.
- [Automated Provisioning](/docs/ai/organization/automated-provisioning/): minting and scoping a service account token.
- [Generation Controls](/docs/ai/features/generation-controls/): what the agent's runs look like in the AI Builder.
