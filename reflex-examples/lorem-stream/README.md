# `lorem_stream`

This example uses background tasks to concurrently generate and stream lorem
text, simulating how an app might make multiple API calls and display the
results as they become available.

The state keeps track of several dicts that are keyed on the task id:

  * `running: bool` if the task should keep processing data
  * `progress: int` how many iterations the task has completed
  * `end_at: int` the task stops after this many iterations
  * `text: str` the actual generated text

## `LoremState.stream_text`

This is the background task that does most of the work. When starting, if a
`task_id` is not provided, it assigns the next available task id to itself;
otherwise it will assume the values of the given `task_id`.

The task then proceeds to iterate a random number of times, generating 3 lorem
words on each iteration.

## UI

The page initially only shows the "New Task" button. Each time it is clicked, a
new `stream_text` task is started.

The tasks are presented as a grid of cards, each of which shows the progress of
the task, a play/pause/restart button, and a kill/delete button. Below the
controls, the text streams as it is available.


https://github.com/reflex-dev/reflex-examples/assets/1524005/09c832ff-ecbd-4a9d-a8a5-67779c673045


